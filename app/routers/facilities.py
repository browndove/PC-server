from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.deps import get_db, require_inspector

router = APIRouter(prefix="/facilities", tags=["facilities"])
# Facilities are licensed premises in a shared council registry — not scoped to one inspector.
# ``inspector_id`` on INSERT is audit only (who recorded this row); list/get/put are council-wide.


class FacilityCreate(BaseModel):
    name: str = Field(min_length=1)
    region: str | None = None
    mmda: str | None = None
    meta: dict[str, Any] | None = None


class FacilityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    region: str | None = None
    mmda: str | None = None
    meta: dict[str, Any] | None = None


def _uuid(s: str) -> str:
    return str(uuid.UUID(s))


@router.get("")
@router.get("/")
async def list_facilities(
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
    q: str | None = Query(default=None),
) -> dict:
    _inspector_id, _ = auth
    if q and q.strip():
        like = f"%{q.strip()}%"
        rows = await conn.fetch(
            """
            select id, name, region, mmda, meta, created_at
            from facilities
            where lower(name) like lower($1)
               or lower(coalesce(region, '')) like lower($1)
            order by created_at desc
            limit 200
            """,
            like,
        )
    else:
        rows = await conn.fetch(
            """
            select id, name, region, mmda, meta, created_at
            from facilities
            order by created_at desc
            limit 200
            """,
        )
    out = []
    for r in rows:
        out.append(
            {
                "id": str(r["id"]),
                "name": r["name"],
                "region": r["region"],
                "mmda": r["mmda"],
                "meta": r["meta"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            },
        )
    return {"facilities": out}


@router.post("")
@router.post("/")
async def create_facility(
    body: FacilityCreate,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    meta = body.meta if body.meta is not None else {}
    # Legacy ``facilities.region`` may be NOT NULL; empty string satisfies constraint.
    region = body.region if body.region is not None and str(body.region).strip() else ""
    rows = await conn.fetch(
        """
        insert into facilities (inspector_id, name, region, mmda, meta)
        values ($1::uuid, $2, $3, $4, $5::jsonb)
        returning id
        """,
        inspector_id,
        body.name,
        region,
        body.mmda,
        json.dumps(meta),
    )
    if not rows:
        return JSONResponse(status_code=500, content={"error": "Create failed"})
    return JSONResponse(status_code=201, content={"id": str(rows[0]["id"])})


@router.get("/{facility_id}")
async def get_facility(
    facility_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    _inspector_id, _ = auth
    try:
        fid = _uuid(facility_id)
    except ValueError:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    rows = await conn.fetch(
        """
        select id, name, region, mmda, meta, created_at, updated_at
        from facilities
        where id = $1::uuid
        limit 1
        """,
        fid,
    )
    row = rows[0] if rows else None
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    return JSONResponse(
        content={
            "id": str(row["id"]),
            "name": row["name"],
            "region": row["region"],
            "mmda": row["mmda"],
            "meta": row["meta"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        },
    )


@router.put("/{facility_id}")
async def update_facility(
    facility_id: str,
    body: FacilityUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    _inspector_id, _ = auth
    try:
        fid = _uuid(facility_id)
    except ValueError:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    cur = await conn.fetch(
        """
        select name, region, mmda, meta
        from facilities
        where id = $1::uuid
        limit 1
        """,
        fid,
    )
    if not cur:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    c0 = cur[0]
    name = body.name if body.name is not None else c0["name"]
    region = body.region if body.region is not None else c0["region"]
    mmda = body.mmda if body.mmda is not None else c0["mmda"]
    meta = body.meta if body.meta is not None else c0["meta"]
    rows = await conn.fetch(
        """
        update facilities
        set
          name = $2,
          region = $3,
          mmda = $4,
          meta = $5::jsonb,
          updated_at = now()
        where id = $1::uuid
        returning id
        """,
        fid,
        name,
        region,
        mmda,
        json.dumps(meta if isinstance(meta, (dict, list)) else {}),
    )
    if not rows:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    return JSONResponse(content={"ok": True, "id": str(rows[0]["id"])})
