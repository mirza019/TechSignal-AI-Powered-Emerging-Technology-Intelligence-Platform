from datetime import datetime, timedelta, timezone
import threading
import time
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db import get_db
from app.models import User

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
DUMMY_HASH = passwords.hash("not-a-real-account-password")


def token_for(user: User):
    return jwt.encode(
        {"sub": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=8), "iss": "techsignal"},
        get_settings().app_secret,
        algorithm="HS256",
    )


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    try:
        claims = jwt.decode(
            credentials.credentials if credentials else "",
            get_settings().app_secret,
            algorithms=["HS256"],
            issuer="techsignal",
            options={"require": ["sub", "exp", "iss"]},
        )
        user = db.get(User, claims["sub"])
        if user and user.active:
            return user
    except jwt.PyJWTError:
        pass
    raise HTTPException(401, "Authentication required")


def require(*roles):
    def guard(user: User = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, "This action requires " + " or ".join(roles))
        return user

    return guard


class RateLimiter:
    """Bounded per-process limiter; use a shared gateway/Redis with multiple replicas."""

    def __init__(self):
        self.events = {}
        self.lock = threading.Lock()

    def check(self, key: str, limit: int = 12, period: int = 60):
        with self.lock:
            cutoff = time.monotonic() - period
            self.events = {k: [t for t in v if t > cutoff] for k, v in self.events.items() if v and v[-1] > cutoff}
            values = self.events.setdefault(key, [])
            if len(values) >= limit:
                raise HTTPException(429, "Rate limit reached; retry in a minute")
            values.append(time.monotonic())


limiter = RateLimiter()


def authenticate(db, email, password):
    user = db.scalar(select(User).where(User.email == email.lower()))
    verified = passwords.verify(password, user.password_hash if user else DUMMY_HASH)
    if not user or not verified or not user.active:
        raise HTTPException(401, "Invalid email or password")
    return user
