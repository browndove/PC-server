from __future__ import annotations

from collections.abc import AsyncGenerator

import asyncpg
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.db import get_pool
from app.jwt_util import verify_access_token

security = HTTPBearer(auto_error=False)


async def require_jwt_secret_configured() -> None:
    """Run before DB so signup/login fail fast with a clear 503 if Railway env is incomplete."""
    from fastapi import HTTPException

    if not get_settings().effective_jwt_secret.strip():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Missing JWT_SECRET. In Railway → Variables add JWT_SECRET (e.g. run: openssl rand -base64 32).",
                "code": "MISSING_JWT_SECRET",
            },
        )


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def require_inspector(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
) -> tuple[str, str]:
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials.strip():
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = creds.credentials.strip()
    if not token:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Missing token")
    try:
        return verify_access_token(get_settings(), token)
    except ValueError:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
