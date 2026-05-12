"""Run SQL files under migrations/ (idempotent). Used at API startup and by scripts/migrate.py."""

from __future__ import annotations

import os
from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def migrations_on_startup_enabled() -> bool:
    v = os.environ.get("RUN_MIGRATIONS_ON_STARTUP", "true").strip().lower()
    return v not in ("0", "false", "no", "off")


async def apply_all_migration_files(conn: asyncpg.Connection) -> int:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        raise RuntimeError(f"No .sql files under {MIGRATIONS_DIR}")
    async with conn.transaction():
        for path in files:
            sql = path.read_text(encoding="utf-8")
            await conn.execute(sql)
    return len(files)


async def run_startup_migrations(conn: asyncpg.Connection) -> None:
    if not migrations_on_startup_enabled():
        return
    n = await apply_all_migration_files(conn)
    print(f"migrations: applied {n} SQL file(s) from {MIGRATIONS_DIR.name}/.", flush=True)
