"""Run SQL from migrations/ at startup when the schema is incomplete.

We skip re-applying only when **all** core tables from ``001_init.sql`` exist
(``information_schema``), not just ``inspectors`` -- partial installs used to
leave the DB broken while startup incorrectly skipped migrations.

- ``FORCE_RUN_ALL_MIGRATIONS=1`` -- always run every ``*.sql`` file.
- ``python scripts/migrate.py`` -- always runs all files (one-off).

``RUN_MIGRATIONS_ON_STARTUP=0`` -- skip startup migration logic entirely.

``main.py`` runs ``001z_inspectors_auth_bridge.sql`` in the same **background**
task as ``run_startup_migrations`` (before the 6/6 skip check), so the server
binds immediately while legacy ``inspectors`` rows still get ``updated_at`` /
``signature_url``.

Each ``*.sql`` file runs in its **own** transaction so a failure in a later file
does not roll back DDL from earlier files (avoids stuck ``4/6`` partial schema).
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


INSPECTORS_AUTH_BRIDGE_FILE = "001z_inspectors_auth_bridge.sql"


async def inspectors_auth_columns_ready(conn: asyncpg.Connection) -> bool:
    """True when ``inspectors`` has columns required by ``/auth/me`` and ``PUT /auth/signature``."""
    reg = await conn.fetchrow("select to_regclass('public.inspectors') as t")
    if not reg or reg["t"] is None:
        return True
    row = await conn.fetchrow(
        """
        select
          exists(
            select 1 from information_schema.columns
            where table_schema = 'public'
              and table_name = 'inspectors'
              and column_name = 'signature_url'
          ) as has_signature_url,
          exists(
            select 1 from information_schema.columns
            where table_schema = 'public'
              and table_name = 'inspectors'
              and column_name = 'updated_at'
          ) as has_updated_at
        """,
    )
    if not row:
        return False
    return bool(row["has_signature_url"] and row["has_updated_at"])


async def apply_inspectors_auth_bridge(conn: asyncpg.Connection) -> None:
    """Add ``updated_at`` / ``signature_url`` on legacy ``inspectors`` (idempotent).

    When all six core *table names* exist, full startup migrations are skipped,
    but legacy rows may still lack columns the auth router expects (503 on signup).
    """
    row = await conn.fetchrow("select to_regclass('public.inspectors') as t")
    if not row or row["t"] is None:
        return
    path = MIGRATIONS_DIR / INSPECTORS_AUTH_BRIDGE_FILE
    if not path.is_file():
        print(f"migrations: missing {path.name}, skipping inspectors auth bridge.", flush=True)
        return
    sql = path.read_text(encoding="utf-8")
    async with conn.transaction():
        await conn.execute(sql)
    print("migrations: inspectors auth bridge applied (idempotent).", flush=True)


async def missing_core_public_tables(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch(
        """
        select table_name
        from information_schema.tables
        where table_schema = 'public'
          and table_type = 'BASE TABLE'
          and table_name = any($1::text[])
        """,
        list(CORE_PUBLIC_TABLE_NAMES),
    )
    present = {r["table_name"] for r in rows}
    return [name for name in CORE_PUBLIC_TABLE_NAMES if name not in present]


async def _core_public_tables_present(conn: asyncpg.Connection) -> bool:
    return len(await missing_core_public_tables(conn)) == 0


async def inspections_api_schema_complete(conn: asyncpg.Connection) -> bool:
    """True when ``inspections`` has columns required by POST/PUT ``/inspections``.

    Legacy databases often had ``inspections`` without ``type`` / ``data`` /
    ``submitted_at``. Startup used to skip *all* migrations once the six core
    *table names* existed, so ``004_legacy_api_columns.sql`` never ran and inserts
    failed with ``UndefinedColumnError`` (HTTP 500).
    """
    reg = await conn.fetchrow("select to_regclass('public.inspections') as t")
    if not reg or reg["t"] is None:
        return False
    row = await conn.fetchrow(
        """
        select
          exists(
            select 1 from information_schema.columns
            where table_schema = 'public' and table_name = 'inspections' and column_name = 'inspector_id'
          ) as has_inspector_id,
          exists(
            select 1 from information_schema.columns
            where table_schema = 'public' and table_name = 'inspections' and column_name = 'type'
          ) as has_type,
          exists(
            select 1 from information_schema.columns
            where table_schema = 'public' and table_name = 'inspections' and column_name = 'data'
          ) as has_data,
          exists(
            select 1 from information_schema.columns
            where table_schema = 'public'
              and table_name = 'inspections'
              and column_name = 'facility_id'
              and is_nullable = 'YES'
          ) as facility_id_nullable
        """,
    )
    if not row:
        return False
    has_legacy_insp_type = await conn.fetchval(
        """
        select exists(
          select 1 from information_schema.columns
          where table_schema = 'public' and table_name = 'inspections' and column_name = 'inspection_type'
        )
        """,
    )
    legacy_type_ok = True
    if has_legacy_insp_type:
        legacy_type_ok = bool(
            await conn.fetchval(
                """
                select exists(
                  select 1
                  from pg_trigger t
                  join pg_class c on c.oid = t.tgrelid
                  join pg_namespace n on n.oid = c.relnamespace
                  where n.nspname = 'public'
                    and c.relname = 'inspections'
                    and t.tgname = 'inspections_legacy_from_type_trg'
                    and not t.tgisinternal
                )
                """,
            ),
        )
    return bool(
        row["has_inspector_id"]
        and row["has_type"]
        and row["has_data"]
        and row["facility_id_nullable"]
        and legacy_type_ok,
    )


async def facilities_insert_api_ready(conn: asyncpg.Connection) -> bool:
    """True when legacy ``facility_type`` column is absent, or insert defaults trigger is installed."""
    reg = await conn.fetchrow("select to_regclass('public.facilities') as t")
    if not reg or reg["t"] is None:
        return True
    has_facility_type = await conn.fetchval(
        """
        select exists(
          select 1 from information_schema.columns
          where table_schema = 'public' and table_name = 'facilities' and column_name = 'facility_type'
        )
        """,
    )
    if not has_facility_type:
        return True
    return bool(
        await conn.fetchval(
            """
            select exists(
              select 1 from pg_trigger t
              join pg_class c on c.oid = t.tgrelid
              join pg_namespace n on n.oid = c.relnamespace
              where n.nspname = 'public'
                and c.relname = 'facilities'
                and t.tgname = 'facilities_legacy_insert_defaults_trg'
                and not t.tgisinternal
            )
            """,
        ),
    )


async def apply_all_migration_files(conn: asyncpg.Connection) -> int:
    """Run each ``*.sql`` in its **own** transaction so a failure in 002/003 does not roll back 001."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        raise RuntimeError(f"No .sql files under {MIGRATIONS_DIR}")
    n = len(files)
    for i, path in enumerate(files, 1):
        sql = path.read_text(encoding="utf-8")
        print(f"migrations: applying {i}/{n} {path.name} ...", flush=True)
        async with conn.transaction():
            await conn.execute(sql)
        print(f"migrations: committed {path.name}", flush=True)
    return n


async def run_startup_migrations(conn: asyncpg.Connection) -> None:
    if not migrations_on_startup_enabled():
        print("migrations: skipped (RUN_MIGRATIONS_ON_STARTUP disabled).", flush=True)
        return
    if not force_run_all_migrations():
        core_ok = await _core_public_tables_present(conn)
        insp_ok = await inspections_api_schema_complete(conn)
        fac_ok = await facilities_insert_api_ready(conn)
        auth_cols_ok = await inspectors_auth_columns_ready(conn)
        if core_ok and insp_ok and fac_ok and auth_cols_ok:
            print(
                f"migrations: skipped ({len(CORE_PUBLIC_TABLE_NAMES)} core tables present; inspections, facilities, and inspectors auth columns API-ready).",
                flush=True,
            )
            return
        if core_ok and (not insp_ok or not fac_ok or not auth_cols_ok):
            print(
                "migrations: core tables exist but schema is not fully API-ready (inspections, facilities, and/or inspectors auth); applying migration files.",
                flush=True,
            )
    n = await apply_all_migration_files(conn)
    print(f"migrations: applied {n} SQL file(s) from {MIGRATIONS_DIR.name}/.", flush=True)
