import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from datetime import datetime
from sqlalchemy import inspect


def as_dict(obj):
    return {
        c.key: (getattr(obj, c.key).isoformat() if isinstance(getattr(obj, c.key), datetime) else getattr(obj, c.key))
        for c in inspect(obj).mapper.column_attrs
        if c.key != "embedding"
    }


def normalize_url(url: str) -> str:
    p = urlsplit(url.strip())
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise ValueError("Only public HTTP(S) source URLs are supported")
    host = p.hostname.lower().encode("idna").decode("ascii")
    port = p.port
    netloc = host + (f":{port}" if port and port not in (80, 443) else "")
    query = sorted((k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid"))
    return urlunsplit((p.scheme.lower(), netloc, p.path.rstrip("/") or "/", urlencode(query), ""))


def normalize_doi(doi):
    if not doi:
        return None
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", doi.strip(), flags=re.I).lower()


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_name(name: str):
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
