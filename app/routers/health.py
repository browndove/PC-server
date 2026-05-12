from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import Response

from app.config import get_settings
from app.db import get_pool
from app.pg_errors import (
    error_message_chain,
    looks_like_db_transport_failure,
    postgres_error_code,
)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    base: dict = {
        "ok": True,
        "runtime": "vercel" if os.environ.get("VERCEL") else "python",
        "env": os.environ.get("VERCEL_ENV") or os.environ.get("PYTHON_ENV") or "development",
        "database": {
            "reachable": False,
            "inspectorsTable": False,
            "hint": None,
        },
    }
    settings = get_settings()
    if not settings.database_url_normalized.strip():
        base["database"]["hint"] = "DATABASE_URL is not set on this deployment."
        base["time"] = datetime.now(timezone.utc).isoformat()
        return base
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("select 1 as ping")
            base["database"]["reachable"] = True
            row = await conn.fetchrow(
                "select to_regclass('public.inspectors') is not null as ready",
            )
            base["database"]["inspectorsTable"] = bool(row and row["ready"])
            if not base["database"]["inspectorsTable"]:
                base["database"]["hint"] = (
                    "Connected, but table public.inspectors is missing — run "
                    "migrations against this DATABASE_URL."
                )
    except Exception as e:
        code = postgres_error_code(e)
        chain = error_message_chain(e)
        if code == "42P01":
            base["database"]["hint"] = "Relation missing (run migrations)."
        elif looks_like_db_transport_failure(e):
            base["database"]["hint"] = "Cannot reach Neon (check DATABASE_URL host / network)."
        elif "password authentication failed" in chain.lower():
            base["database"]["hint"] = "Database rejected credentials (wrong password in URL)."
        else:
            base["database"]["hint"] = "Database check failed — see server logs."
        print("health db check", chain)
    base["time"] = datetime.now(timezone.utc).isoformat()
    return base


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@router.get("/favicon.png", include_in_schema=False)
async def favicon_png() -> Response:
    return Response(status_code=204)
