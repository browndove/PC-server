"""
Apply SQL from migrations/ when the DB is empty — no separate migrate step required.

Opt out: set AUTO_APPLY_SCHEMA=0 (or false) in the environment.
"""

from __future__ import annotations

import os
from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def auto_apply_schema_enabled() -> bool:
    v = os.environ.get("AUTO_APPLY_SCHEMA", "true").strip().lower()
    return v not in ("0", "false", "no", "off")


async def apply_all_migration_files(conn: asyncpg.Connection) -> None:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        raise RuntimeError(f"No .sql files under {MIGRATIONS_DIR}")
    async with conn.transaction():
        for path in files:
            sql = path.read_text(encoding="utf-8")
            await conn.execute(sql)


async def ensure_schema_if_needed(conn: asyncpg.Connection) -> None:
    if not auto_apply_schema_enabled():
        return
    row = await conn.fetchrow("select to_regclass('public.inspectors') is not null as ok")
    if row and row.get("ok"):
        return
    await apply_all_migration_files(conn)
    print(
        "schema_bootstrap: applied SQL migrations (inspectors was missing).",
        flush=True,
    )
