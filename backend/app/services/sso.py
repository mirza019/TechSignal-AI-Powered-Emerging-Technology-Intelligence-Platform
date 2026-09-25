"""Microsoft Entra authorization code flow with PKCE and validated ID tokens.

Only a configured tenant is accepted. Local accounts are never silently linked
by email. A short-lived one-time exchange code keeps bearer tokens out of URLs.
"""

import hashlib
import hmac
import secrets
import base64
from datetime import timedelta
from functools import lru_cache
from urllib.parse import urlencode
import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db import get_db
from app.models import User, Role, SSOExchange, AuditLog, now
from app.services.auth import passwords, token_for, limiter

router = APIRouter(prefix="/auth")
COOKIE = "grid-radar-sso-state"


def configured():
    cfg = get_settings()
    return bool(cfg.entra_tenant_id and cfg.entra_client_id and cfg.entra_client_secret)


@router.get("/providers")
def providers():
    return {"microsoft": configured(), "demo_available": get_settings().seed_demo and get_settings().environment != "production"}


@router.get("/sso/login")
def start_sso(request: Request):
    if not configured():
        raise HTTPException(503, "Microsoft Entra SSO is not configured. Set tenant ID, client ID, client secret and redirect URI.")
    limiter.check("sso-start:" + (request.client.host if request.client else "unknown"), 10)
    cfg = get_settings()
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state_cookie = jwt.encode(
        {"state": state, "nonce": nonce, "verifier": verifier, "exp": now() + timedelta(minutes=10), "iss": "grid-radar-sso"},
        cfg.app_secret,
        algorithm="HS256",
    )
    params = {
        "client_id": cfg.entra_client_id,
        "response_type": "code",
        "redirect_uri": cfg.entra_redirect_uri,
        "scope": "openid profile email",
        "response_mode": "query",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    response = RedirectResponse(
        f"https://login.microsoftonline.com/{cfg.entra_tenant_id}/oauth2/v2.0/authorize?{urlencode(params)}", status_code=302
    )
    response.set_cookie(
        COOKIE, state_cookie, max_age=600, httponly=True, secure=cfg.environment == "production", samesite="lax", path="/api/auth/sso"
    )
    return response


@lru_cache(maxsize=4)
def jwks_client(tenant):
    return jwt.PyJWKClient(f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys", cache_keys=True, timeout=15)


def validate_identity(id_token, nonce):
    cfg = get_settings()
    key = jwks_client(cfg.entra_tenant_id).get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        key.key,
        algorithms=["RS256"],
        audience=cfg.entra_client_id,
        issuer=f"https://login.microsoftonline.com/{cfg.entra_tenant_id}/v2.0",
        options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce", "tid"]},
    )
    if not hmac.compare_digest(str(claims["nonce"]), nonce) or claims["tid"] != cfg.entra_tenant_id:
        raise ValueError("SSO nonce or tenant mismatch")
    return claims


@router.get("/sso/callback")
def callback(request: Request, code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)):
    cfg = get_settings()
    failure = RedirectResponse(cfg.frontend_url.rstrip("/") + "/?sso_error=Sign-in%20could%20not%20be%20completed", status_code=302)
    failure.delete_cookie(COOKIE, path="/api/auth/sso")
    if not configured() or error or not code or len(code) > 10000:
        return failure
    try:
        signed = jwt.decode(
            request.cookies.get(COOKIE, ""),
            cfg.app_secret,
            algorithms=["HS256"],
            issuer="grid-radar-sso",
            options={"require": ["state", "nonce", "verifier", "exp", "iss"]},
        )
        if not hmac.compare_digest(signed["state"], state):
            return failure
        with httpx.Client(timeout=20) as client:
            result = client.post(
                f"https://login.microsoftonline.com/{cfg.entra_tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": cfg.entra_client_id,
                    "client_secret": cfg.entra_client_secret,
                    "code": code,
                    "redirect_uri": cfg.entra_redirect_uri,
                    "code_verifier": signed["verifier"],
                },
            )
            result.raise_for_status()
            claims = validate_identity(result.json()["id_token"], signed["nonce"])
        subject = f"{claims['tid']}:{claims['sub']}"
        user = db.scalar(select(User).where(User.external_subject == subject))
        email = str(claims.get("email") or claims.get("preferred_username") or "").lower()
        if "@" not in email:
            return failure
        if cfg.entra_allowed_domains and email.rsplit("@", 1)[1] not in cfg.entra_allowed_domains:
            return failure
        roles = claims.get("roles", [])
        mapped = "Admin" if "Radar.Admin" in roles else "Analyst" if "Radar.Analyst" in roles else "Viewer"
        if not user:
            if db.scalar(select(User).where(User.email == email)):
                # Explicit administrator-assisted linking is required for collisions.
                return failure
            if not db.get(Role, mapped):
                db.add(Role(name=mapped))
                db.flush()
            user = User(
                email=email,
                name=str(claims.get("name") or email)[:120],
                external_subject=subject,
                role=mapped,
                password_hash=passwords.hash(secrets.token_urlsafe(48)),
            )
            db.add(user)
            db.flush()
        elif not user.active:
            return failure
        else:
            user.role = mapped
        exchange = secrets.token_urlsafe(40)
        db.execute(delete(SSOExchange).where(SSOExchange.expires_at < now()))
        db.add(
            SSOExchange(code_hash=hashlib.sha256(exchange.encode()).hexdigest(), user_id=user.id, expires_at=now() + timedelta(seconds=60))
        )
        db.add(AuditLog(actor_id=user.id, action="auth.sso_login", entity_id=user.id, after={"provider": "Microsoft Entra"}))
        db.commit()
        response = RedirectResponse(cfg.frontend_url.rstrip("/") + "/?sso_code=" + exchange, status_code=302)
        response.delete_cookie(COOKIE, path="/api/auth/sso")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    except (jwt.PyJWTError, jwt.PyJWKClientError, httpx.HTTPError, ValueError, KeyError):
        db.rollback()
        return failure


class ExchangeInput(BaseModel):
    code: str = Field(min_length=20, max_length=100)


@router.post("/sso/exchange")
def exchange(body: ExchangeInput, request: Request, response: Response, db: Session = Depends(get_db)):
    limiter.check("sso-exchange:" + (request.client.host if request.client else "unknown"), 10)
    hashed = hashlib.sha256(body.code.encode()).hexdigest()
    # Atomic delete + RETURNING ensures the code cannot be replayed concurrently.
    user_id = db.scalar(
        delete(SSOExchange).where(SSOExchange.code_hash == hashed, SSOExchange.expires_at >= now()).returning(SSOExchange.user_id)
    )
    if not user_id:
        db.rollback()
        raise HTTPException(401, "SSO exchange expired or already used")
    user = db.get(User, user_id)
    if not user or not user.active:
        db.rollback()
        raise HTTPException(401, "Account unavailable")
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {
        "access_token": token_for(user),
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role},
    }
