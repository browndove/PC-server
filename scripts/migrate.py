#!/usr/bin/env python3
"""Optional: run migrations manually. The API also auto-applies them on startup if tables are missing."""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import asyncpg

from app.schema_bootstrap import apply_all_migration_files


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
    conn = await asyncpg.connect(url, statement_cache_size=0)
    try:
        await apply_all_migration_files(conn)
        print("Done.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
