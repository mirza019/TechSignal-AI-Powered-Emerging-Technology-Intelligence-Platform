import hashlib
from datetime import timedelta
from urllib.parse import urlparse, parse_qs
from unittest.mock import MagicMock
import jwt
from sqlalchemy import select
from app.config import get_settings
from app.models import User, SSOExchange, now
from app.services import sso


def configure(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "entra_tenant_id", "12345678-1234-1234-1234-123456789012")
    monkeypatch.setattr(cfg, "entra_client_id", "test-client")
    monkeypatch.setattr(cfg, "entra_client_secret", "test-secret")
    return cfg


def test_unconfigured_sso(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "entra_client_secret", "")
    assert not client.get("/api/auth/providers").json()["microsoft"]
    assert client.get("/api/auth/sso/login").status_code == 503


def test_pkce_state_and_cookie(client, monkeypatch):
    cfg = configure(monkeypatch)
    response = client.get("/api/auth/sso/login", follow_redirects=False)
    query = parse_qs(urlparse(response.headers["location"]).query)
    cookie = jwt.decode(client.cookies.get(sso.COOKIE), cfg.app_secret, algorithms=["HS256"], issuer="techsignal-sso")
    assert query["state"] == [cookie["state"]]
    assert query["nonce"] == [cookie["nonce"]]
    assert query["code_challenge_method"] == ["S256"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "test-secret" not in response.headers["location"]
    response = client.get("/api/auth/sso/callback?code=test&state=wrong", follow_redirects=False)
    assert "sso_error=" in response.headers["location"]


def test_callback_role_mapping_and_single_use(client, monkeypatch):
    cfg = configure(monkeypatch)
    start = client.get("/api/auth/sso/login", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    mock = MagicMock()
    mock.__enter__.return_value.post.return_value.json.return_value = {"id_token": "mock-token"}
    monkeypatch.setattr(sso.httpx, "Client", lambda **kwargs: mock)
    monkeypatch.setattr(
        sso,
        "validate_identity",
        lambda *args: {
            "tid": cfg.entra_tenant_id,
            "sub": "external-user",
            "email": "analyst@example.com",
            "name": "External Analyst",
            "roles": ["Radar.Analyst"],
        },
    )
    callback = client.get("/api/auth/sso/callback", params={"code": "auth-code", "state": state}, follow_redirects=False)
    code = parse_qs(urlparse(callback.headers["location"]).query)["sso_code"][0]
    result = client.post("/api/auth/sso/exchange", json={"code": code})
    assert result.status_code == 200
    assert result.json()["user"]["role"] == "Analyst"
    assert result.headers["cache-control"] == "no-store"
    assert client.post("/api/auth/sso/exchange", json={"code": code}).status_code == 401


def test_expired_exchange(client, db):
    code = "expired-exchange-code-123456"
    db.add(
        SSOExchange(
            code_hash=hashlib.sha256(code.encode()).hexdigest(), user_id=db.scalar(select(User.id)), expires_at=now() - timedelta(seconds=1)
        )
    )
    db.commit()
    assert client.post("/api/auth/sso/exchange", json={"code": code}).status_code == 401


def test_real_signature_nonce_and_audience(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import rsa
    import pytest

    cfg = configure(monkeypatch)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    mocked = MagicMock()
    mocked.get_signing_key_from_jwt.return_value.key = key.public_key()
    monkeypatch.setattr(sso, "jwks_client", lambda tenant: mocked)
    claims = {
        "tid": cfg.entra_tenant_id,
        "sub": "subject",
        "aud": cfg.entra_client_id,
        "iss": f"https://login.microsoftonline.com/{cfg.entra_tenant_id}/v2.0",
        "nonce": "nonce",
        "iat": now(),
        "exp": now() + timedelta(minutes=5),
    }
    token = jwt.encode(claims, key, algorithm="RS256")
    assert sso.validate_identity(token, "nonce")["sub"] == "subject"
    with pytest.raises(ValueError):
        sso.validate_identity(token, "wrong")
    with pytest.raises(jwt.InvalidAudienceError):
        sso.validate_identity(jwt.encode({**claims, "aud": "other-app"}, key, algorithm="RS256"), "nonce")
