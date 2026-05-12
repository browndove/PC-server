from __future__ import annotations

import asyncio

import asyncpg

from app.config import get_settings

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    global _pool
    async with _pool_lock:
        if _pool is not None:
            return _pool
        settings = get_settings()
        url = settings.database_url_normalized
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        _pool = await asyncpg.create_pool(dsn=url, min_size=1, max_size=5)
        return _pool


async def close_pool() -> None:
    global _pool
    async with _pool_lock:
        if _pool is not None:
            await _pool.close()
            _pool = None
