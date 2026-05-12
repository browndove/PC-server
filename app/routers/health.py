from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter
from fastapi.responses import Response

from app.config import get_settings
from app.db import get_pool
from app.schema_bootstrap import CORE_PUBLIC_TABLE_NAMES
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
    norm = settings.database_url_normalized.strip()
    if norm:
        try:
            base["database"]["pgHost"] = urlparse(norm).hostname
        except Exception:
            base["database"]["pgHost"] = None
        base["database"]["urlSource"] = (
            "environment"
            if settings.uses_database_url_from_environment
            else "database_defaults.py"
        )
    else:
        base["database"]["pgHost"] = None
        base["database"]["urlSource"] = None

    if not norm:
        base["database"]["hint"] = (
            "No database URL: set DATABASE_URL or DEFAULT_DATABASE_URL in app/database_defaults.py."
        )
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
            nrow = await conn.fetchrow(
                """
                select count(*)::int as n
                from information_schema.tables
                where table_schema = 'public'
                  and table_type = 'BASE TABLE'
                  and table_name = any($1::text[])
                """,
                list(CORE_PUBLIC_TABLE_NAMES),
            )
            base["database"]["coreTablesPresent"] = nrow["n"] if nrow else 0
            base["database"]["coreTablesExpected"] = len(CORE_PUBLIC_TABLE_NAMES)
            if base["database"]["coreTablesPresent"] < base["database"]["coreTablesExpected"]:
                base["database"]["hint"] = (
                    f"Incomplete schema ({base['database']['coreTablesPresent']}/"
                    f"{base['database']['coreTablesExpected']} core tables). "
                    "Redeploy the API or set FORCE_RUN_ALL_MIGRATIONS=1 once."
                )
            elif not base["database"]["inspectorsTable"]:
                base["database"]["hint"] = (
                    "Connected, but public.inspectors is missing — migrations may have failed at startup; "
                    "check logs or run python scripts/migrate.py."
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
        if code:
            base["database"]["errorCode"] = code
        print("health db check", chain)
    base["time"] = datetime.now(timezone.utc).isoformat()
    return base


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@router.get("/favicon.png", include_in_schema=False)
async def favicon_png() -> Response:
    return Response(status_code=204)
