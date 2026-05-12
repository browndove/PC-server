#!/usr/bin/env python3
"""Run SQL migrations in backend/migrations/ against DATABASE_URL (same idea as server/scripts/migrate.mjs)."""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

import asyncpg


def _require_https_db_url(url: str) -> None:
    if not url.strip():
        print("DATABASE_URL is empty.", file=sys.stderr)
        sys.exit(1)
    if re.match(r"^postgres(ql)?://", url, re.I) and not re.search(r"(^|@)localhost\b", url, re.I):
        if "sslmode=require" not in url and "ssl=true" not in url.lower():
            print(
                "Refusing: remote DATABASE_URL should use TLS (add ?sslmode=require or sslmode=verify-full).",
                file=sys.stderr,
            )
            sys.exit(1)


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "").strip()
    _require_https_db_url(url)
    mig_dir = Path(__file__).resolve().parent.parent / "migrations"
    files = sorted(mig_dir.glob("*.sql"))
    if not files:
        print("No migrations found.", file=sys.stderr)
        sys.exit(1)
    conn = await asyncpg.connect(url)
    try:
        for f in files:
            sql = f.read_text(encoding="utf-8")
            print(f"Applying {f.name} …")
            await conn.execute(sql)
        print("Done.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
