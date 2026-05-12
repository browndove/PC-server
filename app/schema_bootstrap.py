"""Run SQL from migrations/ at startup when the DB is still empty.

On every full re-run, edge cases in legacy repair SQL can break production. So by
default we only apply migrations when ``public.inspectors`` is missing.

- ``FORCE_RUN_ALL_MIGRATIONS=1`` — always run every ``*.sql`` file (e.g. after adding a new migration).
- ``python scripts/migrate.py`` — always runs all files (deploy / one-off).

``RUN_MIGRATIONS_ON_STARTUP=0`` — skip startup migration logic entirely.
"""

from __future__ import annotations

import os
from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def migrations_on_startup_enabled() -> bool:
    v = os.environ.get("RUN_MIGRATIONS_ON_STARTUP", "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def force_run_all_migrations() -> bool:
    v = os.environ.get("FORCE_RUN_ALL_MIGRATIONS", "").strip().lower()
    return v in ("1", "true", "yes", "on")


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
    if not force_run_all_migrations():
        row = await conn.fetchrow("select to_regclass('public.inspectors') is not null as ok")
        if row and row.get("ok"):
            print("migrations: skipped (public.inspectors exists).", flush=True)
            return
    n = await apply_all_migration_files(conn)
    print(f"migrations: applied {n} SQL file(s) from {MIGRATIONS_DIR.name}/.", flush=True)
