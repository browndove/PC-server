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
    inspector_id, _ = auth
    if q and q.strip():
        like = f"%{q.strip()}%"
        rows = await conn.fetch(
            """
            select id, name, region, mmda, meta, created_at
            from facilities
            where inspector_id = $1::uuid
              and (lower(name) like lower($2) or lower(coalesce(region,'')) like lower($2))
            order by created_at desc
            limit 100
            """,
            inspector_id,
            like,
        )
    else:
        rows = await conn.fetch(
            """
            select id, name, region, mmda, meta, created_at
            from facilities
            where inspector_id = $1::uuid
            order by created_at desc
            limit 100
            """,
            inspector_id,
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
    rows = await conn.fetch(
        """
        insert into facilities (inspector_id, name, region, mmda, meta)
        values ($1::uuid, $2, $3, $4, $5::jsonb)
        returning id
        """,
        inspector_id,
        body.name,
        body.region,
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
    inspector_id, _ = auth
    try:
        fid = _uuid(facility_id)
    except ValueError:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    rows = await conn.fetch(
        """
        select id, name, region, mmda, meta, created_at, updated_at
        from facilities
        where id = $1::uuid and inspector_id = $2::uuid
        limit 1
        """,
        fid,
        inspector_id,
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
    inspector_id, _ = auth
    try:
        fid = _uuid(facility_id)
    except ValueError:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    cur = await conn.fetch(
        """
        select name, region, mmda, meta
        from facilities
        where id = $1::uuid and inspector_id = $2::uuid
        limit 1
        """,
        fid,
        inspector_id,
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
          name = $3,
          region = $4,
          mmda = $5,
          meta = $6::jsonb,
          updated_at = now()
        where id = $1::uuid and inspector_id = $2::uuid
        returning id
        """,
        fid,
        inspector_id,
        name,
        region,
        mmda,
        json.dumps(meta if isinstance(meta, (dict, list)) else {}),
    )
    if not rows:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    return JSONResponse(content={"ok": True, "id": str(rows[0]["id"])})
