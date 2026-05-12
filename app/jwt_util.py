from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from app.config import Settings


def _parse_expires(exp: str) -> timedelta:
    s = exp.strip().lower()
    if re.fullmatch(r"\d+d", s):
        return timedelta(days=int(s[:-1]))
    if re.fullmatch(r"\d+h", s):
        return timedelta(hours=int(s[:-1]))
    if re.fullmatch(r"\d+m", s):
        return timedelta(minutes=int(s[:-1]))
    if re.fullmatch(r"\d+s", s):
        return timedelta(seconds=int(s[:-1]))
    return timedelta(days=7)


def sign_access_token(settings: Settings, *, sub: str, email: str) -> str:
    if not settings.jwt_secret.strip():
        raise RuntimeError("JWT_SECRET is not set")
    delta = _parse_expires(settings.jwt_expires_in)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "iat": now,
        "exp": now + delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_access_token(settings: Settings, token: str) -> tuple[str, str]:
    if not settings.jwt_secret.strip():
        raise RuntimeError("JWT_SECRET is not set")
    try:
        decoded = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except InvalidTokenError as e:
        raise ValueError("Invalid token") from e
    sub = decoded.get("sub")
    email = decoded.get("email")
    if not isinstance(sub, str) or not isinstance(email, str):
        raise ValueError("Invalid token payload")
    return sub, email
