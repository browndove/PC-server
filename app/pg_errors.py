from __future__ import annotations

import re
from typing import Any


def postgres_error_code(e: Any) -> str | None:
    cur: Any = e
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        code = getattr(cur, "sqlstate", None)
        if isinstance(code, str) and re.match(r"^[0-9A-Z]{5}$", code):
            return code
        nxt = getattr(cur, "__cause__", None)
        if nxt is None:
            nxt = getattr(cur, "__context__", None)
        cur = nxt
    return None


def error_message_chain(e: Any) -> str:
    parts: list[str] = []
    cur: Any = e
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, BaseException):
            parts.append(str(cur))
        elif isinstance(cur, dict) and isinstance(cur.get("message"), str):
            parts.append(cur["message"])
        nxt = getattr(cur, "__cause__", None)
        if nxt is None:
            nxt = getattr(cur, "__context__", None)
        cur = nxt
    uniq: list[str] = []
    s2 = set()
    for p in parts:
        if p and p not in s2:
            s2.add(p)
            uniq.append(p)
    return " | ".join(uniq) if uniq else "Unknown error"


def looks_like_db_transport_failure(e: Any) -> bool:
    m = error_message_chain(e).lower()
    return (
        "fetch failed" in m
        or "enotfound" in m
        or "econnrefused" in m
        or "getaddrinfo" in m
        or "error connecting to database" in m
        or "connection terminated" in m
        or ("ssl" in m and "wrong version number" in m)
        or "cannot assign requested address" in m
    )


def looks_like_unique_violation(e: Any) -> bool:
    m = error_message_chain(e).lower()
    return (
        "duplicate key" in m
        or "unique constraint" in m
        or ("already exists" in m and "inspectors" in m)
    )


def looks_like_missing_relation(e: Any) -> bool:
    m = error_message_chain(e).lower()
    return "relation" in m and "does not exist" in m
