"""Run SQL from migrations/ at startup when the schema is incomplete.

We skip re-applying only when **all** core tables from ``001_init.sql`` exist
(``information_schema``), not just ``inspectors`` — partial installs used to
leave the DB broken while startup incorrectly skipped migrations.

- ``FORCE_RUN_ALL_MIGRATIONS=1`` — always run every ``*.sql`` file.
- ``python scripts/migrate.py`` — always runs all files (one-off).

``RUN_MIGRATIONS_ON_STARTUP=0`` — skip startup migration logic entirely.
"""

from __future__ import annotations

import os
from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

# Tables created by migrations/001_init.sql (must all exist before we skip).
CORE_PUBLIC_TABLE_NAMES = (
    "inspectors",
    "facilities",
    "inspections",
    "inspection_staff",
    "inspection_responses",
    "inspection_signoff",
)


def migrations_on_startup_enabled() -> bool:
    v = os.environ.get("RUN_MIGRATIONS_ON_STARTUP", "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def force_run_all_migrations() -> bool:
    v = os.environ.get("FORCE_RUN_ALL_MIGRATIONS", "").strip().lower()
    return v in ("1", "true", "yes", "on")


async def _core_public_tables_present(conn: asyncpg.Connection) -> bool:
    row = await conn.fetchrow(
        """
        select count(*)::int as n
        from information_schema.tables
        where table_schema = 'public'
          and table_type = 'BASE TABLE'
          and table_name = any($1::text[])
        """,
        list(CORE_PUBLIC_TABLE_NAMES),
    )
    return bool(row and row["n"] == len(CORE_PUBLIC_TABLE_NAMES))


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
        print("migrations: skipped (RUN_MIGRATIONS_ON_STARTUP disabled).", flush=True)
        return
    if not force_run_all_migrations():
        if await _core_public_tables_present(conn):
            print(
                f"migrations: skipped ({len(CORE_PUBLIC_TABLE_NAMES)} core public tables already present).",
                flush=True,
            )
            return
    n = await apply_all_migration_files(conn)
    print(f"migrations: applied {n} SQL file(s) from {MIGRATIONS_DIR.name}/.", flush=True)
