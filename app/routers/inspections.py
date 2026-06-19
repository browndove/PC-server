from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from app.deps import get_db, require_inspector

router = APIRouter(prefix="/inspections", tags=["inspections"])


def _map_insp(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "inspectorId": str(r["inspector_id"]),
        "facilityId": str(r["facility_id"]) if r["facility_id"] else None,
        "type": r["type"],
        "status": r["status"],
        "data": r["data"],
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        "submittedAt": r["submitted_at"].isoformat() if r["submitted_at"] else None,
    }


class InspCreate(BaseModel):
    facilityId: str | None = None
    type: str | None = Field(default=None, min_length=1)
    data: dict[str, Any] | None = None


class InspUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    facilityId: str | None = None
    type: str | None = Field(default=None, min_length=1)
    data: dict[str, Any] | None = None


class StatusBody(BaseModel):
    status: Literal["draft", "submitted", "signed"]


class StaffCreate(BaseModel):
    data: dict[str, Any]


class StaffUpdate(BaseModel):
    data: dict[str, Any]


class ResponseItem(BaseModel):
    questionKey: str = Field(min_length=1)
    value: Any | None = None
    flagged: bool | None = None


class ResponsesBulk(BaseModel):
    items: list[ResponseItem]


class FlagBody(BaseModel):
    flagged: bool


class SignoffBody(BaseModel):
    data: dict[str, Any]


async def _assert_facility_exists(conn: asyncpg.Connection, facility_id: str) -> bool:
    rows = await conn.fetch(
        "select id from facilities where id = $1::uuid limit 1",
        facility_id,
    )
    return bool(rows)


async def _get_insp(conn: asyncpg.Connection, inspector_id: str, iid: str) -> asyncpg.Record | None:
    rows = await conn.fetch(
        """
        select id, inspector_id, facility_id, type, status, data, created_at, updated_at, submitted_at
        from inspections
        where id = $1::uuid and inspector_id = $2::uuid
        limit 1
        """,
        iid,
        inspector_id,
    )
    return rows[0] if rows else None


@router.get("")
@router.get("/")
async def list_inspections(
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
    status: str | None = Query(default=None),
    facilityId: str | None = Query(default=None),
) -> dict:
    inspector_id, _ = auth
    allowed = {"draft", "submitted", "signed"}
    st = status.strip() if status else None
    status_filter = st if st in allowed else None
    fid = facilityId.strip() if facilityId else None

    if status_filter and fid:
        rows = await conn.fetch(
            """
            select id, inspector_id, facility_id, type, status, data, created_at, updated_at, submitted_at
            from inspections
            where inspector_id = $1::uuid and status = $2 and facility_id = $3::uuid
            order by created_at desc
            limit 200
            """,
            inspector_id,
            status_filter,
            fid,
        )
    elif status_filter:
        rows = await conn.fetch(
            """
            select id, inspector_id, facility_id, type, status, data, created_at, updated_at, submitted_at
            from inspections
            where inspector_id = $1::uuid and status = $2
            order by created_at desc
            limit 200
            """,
            inspector_id,
            status_filter,
        )
    elif fid:
        rows = await conn.fetch(
            """
            select id, inspector_id, facility_id, type, status, data, created_at, updated_at, submitted_at
            from inspections
            where inspector_id = $1::uuid and facility_id = $2::uuid
            order by created_at desc
            limit 200
            """,
            inspector_id,
            fid,
        )
    else:
        rows = await conn.fetch(
            """
            select id, inspector_id, facility_id, type, status, data, created_at, updated_at, submitted_at
            from inspections
            where inspector_id = $1::uuid
            order by created_at desc
            limit 200
            """,
            inspector_id,
        )
    return {"inspections": [_map_insp(r) for r in rows]}


@router.post("")
@router.post("/")
async def create_insp(
    body: InspCreate,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    fid = body.facilityId
    if fid:
        if not await _assert_facility_exists(conn, fid):
            return JSONResponse(status_code=404, content={"error": "Facility not found"})
    itype = body.type or "pharmacy_routine"
    data = body.data if body.data is not None else {}
    rows = await conn.fetch(
        """
        insert into inspections (inspector_id, facility_id, type, data)
        values ($1::uuid, $2, $3, $4::jsonb)
        returning id, inspector_id, facility_id, type, status, data, created_at, updated_at, submitted_at
        """,
        inspector_id,
        fid,
        itype,
        json.dumps(data),
    )
    if not rows:
        return JSONResponse(status_code=500, content={"error": "Create failed"})
    return JSONResponse(status_code=201, content=_map_insp(rows[0]))


@router.get("/{inspection_id}/export/pdf")
async def export_pdf(
    inspection_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    row = await _get_insp(conn, inspector_id, inspection_id)
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    return JSONResponse(
        status_code=501,
        content={
            "error": "PDF export not implemented yet",
            "inspectionId": inspection_id,
            "hint": "Wire a server-side renderer (e.g. pdfkit / puppeteer) and return application/pdf",
        },
    )


@router.patch("/{inspection_id}/submit")
async def submit_insp(
    inspection_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    row = await _get_insp(conn, inspector_id, inspection_id)
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    if row["status"] != "draft":
        return JSONResponse(status_code=400, content={"error": "Only draft inspections can be submitted"})
    rows = await conn.fetch(
        """
        update inspections
        set status = 'submitted', submitted_at = now(), updated_at = now()
        where id = $1::uuid and inspector_id = $2::uuid and status = 'draft'
        returning id, inspector_id, facility_id, type, status, data, created_at, updated_at, submitted_at
        """,
        inspection_id,
        inspector_id,
    )
    if not rows:
        return JSONResponse(status_code=409, content={"error": "Submit failed"})
    return JSONResponse(content=_map_insp(rows[0]))


@router.patch("/{inspection_id}/status")
async def patch_status(
    inspection_id: str,
    body: StatusBody,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    row = await _get_insp(conn, inspector_id, inspection_id)
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    submitted_at = None if body.status == "draft" else (row["submitted_at"] or datetime.now(timezone.utc))
    rows = await conn.fetch(
        """
        update inspections
        set status = $3, submitted_at = $4, updated_at = now()
        where id = $1::uuid and inspector_id = $2::uuid
        returning id, inspector_id, facility_id, type, status, data, created_at, updated_at, submitted_at
        """,
        inspection_id,
        inspector_id,
        body.status,
        submitted_at,
    )
    if not rows:
        return JSONResponse(status_code=500, content={"error": "Update failed"})
    return JSONResponse(content=_map_insp(rows[0]))


@router.delete("/{inspection_id}")
async def delete_insp(
    inspection_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> Response:
    inspector_id, _ = auth
    row = await _get_insp(conn, inspector_id, inspection_id)
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    if row["status"] != "draft":
        return JSONResponse(status_code=400, content={"error": "Only draft inspections can be deleted"})
    await conn.execute(
        """
        delete from inspections
        where id = $1::uuid and inspector_id = $2::uuid and status = 'draft'
        """,
        inspection_id,
        inspector_id,
    )
    return Response(status_code=204)


@router.post("/{inspection_id}/staff")
async def staff_create(
    inspection_id: str,
    body: StaffCreate,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    row = await _get_insp(conn, inspector_id, inspection_id)
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    rows = await conn.fetch(
        """
        insert into inspection_staff (inspection_id, data)
        values ($1::uuid, $2::jsonb)
        returning id
        """,
        inspection_id,
        json.dumps(body.data),
    )
    if not rows:
        return JSONResponse(status_code=500, content={"error": "Create failed"})
    return JSONResponse(status_code=201, content={"id": str(rows[0]["id"])})


@router.get("/{inspection_id}/staff", response_model=None)
async def staff_list(
    inspection_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse | dict:
    inspector_id, _ = auth
    row = await _get_insp(conn, inspector_id, inspection_id)
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    staff = await conn.fetch(
        """
        select id, data, created_at, updated_at
        from inspection_staff
        where inspection_id = $1::uuid
        order by created_at asc
        """,
        inspection_id,
    )
    return {
        "staff": [
            {
                "id": str(s["id"]),
                "data": s["data"],
                "created_at": s["created_at"].isoformat() if s["created_at"] else None,
                "updated_at": s["updated_at"].isoformat() if s["updated_at"] else None,
            }
            for s in staff
        ],
    }


@router.put("/{inspection_id}/staff/{sid}")
async def staff_put(
    inspection_id: str,
    sid: str,
    body: StaffUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    insp = await _get_insp(conn, inspector_id, inspection_id)
    if not insp:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    cur = await conn.fetch(
        """
        select data from inspection_staff
        where id = $1::uuid and inspection_id = $2::uuid
        limit 1
        """,
        sid,
        inspection_id,
    )
    if not cur:
        return JSONResponse(status_code=404, content={"error": "Staff row not found"})
    merged = {**(cur[0]["data"] or {}), **body.data}
    rows = await conn.fetch(
        """
        update inspection_staff
        set data = $3::jsonb, updated_at = now()
        where id = $1::uuid and inspection_id = $2::uuid
        returning id
        """,
        sid,
        inspection_id,
        json.dumps(merged),
    )
    if not rows:
        return JSONResponse(status_code=404, content={"error": "Update failed"})
    return JSONResponse(content={"ok": True, "id": str(rows[0]["id"])})


@router.delete("/{inspection_id}/staff/{sid}")
async def staff_delete(
    inspection_id: str,
    sid: str,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> Response:
    inspector_id, _ = auth
    insp = await _get_insp(conn, inspector_id, inspection_id)
    if not insp:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    await conn.execute(
        "delete from inspection_staff where id = $1::uuid and inspection_id = $2::uuid",
        sid,
        inspection_id,
    )
    return Response(status_code=204)


@router.post("/{inspection_id}/responses")
async def responses_post(
    inspection_id: str,
    body: ResponsesBulk,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    insp = await _get_insp(conn, inspector_id, inspection_id)
    if not insp:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    for item in body.items:
        existing = await conn.fetch(
            """
            select value, flagged from inspection_responses
            where inspection_id = $1::uuid and question_key = $2
            limit 1
            """,
            inspection_id,
            item.questionKey,
        )
        cur = existing[0] if existing else None
        next_val = item.value if item.value is not None else (cur["value"] if cur else None)
        next_flag = item.flagged if item.flagged is not None else (cur["flagged"] if cur else False)
        await conn.execute(
            """
            insert into inspection_responses (inspection_id, question_key, value, flagged, updated_at)
            values ($1::uuid, $2, $3::jsonb, $4, now())
            on conflict (inspection_id, question_key) do update
            set value = excluded.value, flagged = excluded.flagged, updated_at = now()
            """,
            inspection_id,
            item.questionKey,
            json.dumps(next_val),
            next_flag,
        )
    return JSONResponse(content={"ok": True, "count": len(body.items)})


@router.get("/{inspection_id}/responses", response_model=None)
async def responses_get(
    inspection_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse | dict:
    inspector_id, _ = auth
    insp = await _get_insp(conn, inspector_id, inspection_id)
    if not insp:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    responses = await conn.fetch(
        """
        select id, question_key, value, flagged, updated_at
        from inspection_responses
        where inspection_id = $1::uuid
        order by question_key asc
        """,
        inspection_id,
    )
    return {
        "responses": [
            {
                "id": str(r["id"]),
                "questionKey": r["question_key"],
                "value": r["value"],
                "flagged": r["flagged"],
                "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in responses
        ],
    }


@router.patch("/{inspection_id}/responses/{rid}/flag")
async def response_flag(
    inspection_id: str,
    rid: str,
    body: FlagBody,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    insp = await _get_insp(conn, inspector_id, inspection_id)
    if not insp:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    rows = await conn.fetch(
        """
        update inspection_responses
        set flagged = $3, updated_at = now()
        where id = $1::uuid and inspection_id = $2::uuid
        returning id, question_key, value, flagged, updated_at
        """,
        rid,
        inspection_id,
        body.flagged,
    )
    if not rows:
        return JSONResponse(status_code=404, content={"error": "Response not found"})
    r = rows[0]
    return JSONResponse(
        content={
            "id": str(r["id"]),
            "questionKey": r["question_key"],
            "value": r["value"],
            "flagged": r["flagged"],
            "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
        },
    )


@router.post("/{inspection_id}/signoff")
async def signoff_post(
    inspection_id: str,
    body: SignoffBody,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    insp = await _get_insp(conn, inspector_id, inspection_id)
    if not insp:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    await conn.execute(
        """
        insert into inspection_signoff (inspection_id, data)
        values ($1::uuid, $2::jsonb)
        on conflict (inspection_id) do update
        set data = excluded.data, updated_at = now()
        """,
        inspection_id,
        json.dumps(body.data),
    )
    return JSONResponse(content={"ok": True})


@router.put("/{inspection_id}/signoff")
async def signoff_put(
    inspection_id: str,
    body: SignoffBody,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    insp = await _get_insp(conn, inspector_id, inspection_id)
    if not insp:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    cur = await conn.fetch(
        "select data from inspection_signoff where inspection_id = $1::uuid limit 1",
        inspection_id,
    )
    base = (cur[0]["data"] or {}) if cur else {}
    merged = {**base, **body.data}
    await conn.execute(
        """
        insert into inspection_signoff (inspection_id, data)
        values ($1::uuid, $2::jsonb)
        on conflict (inspection_id) do update
        set data = excluded.data, updated_at = now()
        """,
        inspection_id,
        json.dumps(merged),
    )
    return JSONResponse(content={"ok": True})


@router.get("/{inspection_id}/signoff", response_model=None)
async def signoff_get(
    inspection_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> dict | JSONResponse:
    inspector_id, _ = auth
    insp = await _get_insp(conn, inspector_id, inspection_id)
    if not insp:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    rows = await conn.fetch(
        "select data, updated_at from inspection_signoff where inspection_id = $1::uuid limit 1",
        inspection_id,
    )
    if not rows:
        return {"data": None, "updatedAt": None}
    row = rows[0]
    return {
        "data": row["data"],
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


@router.get("/{inspection_id}")
async def get_insp(
    inspection_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    row = await _get_insp(conn, inspector_id, inspection_id)
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    return JSONResponse(content=_map_insp(row))


@router.put("/{inspection_id}")
async def put_insp(
    inspection_id: str,
    body: InspUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _ = auth
    cur = await _get_insp(conn, inspector_id, inspection_id)
    if not cur:
        return JSONResponse(status_code=404, content={"error": "Not found"})

    if "facilityId" in body.model_fields_set and body.facilityId:
        if not await _assert_facility_exists(conn, body.facilityId):
            return JSONResponse(status_code=404, content={"error": "Facility not found"})

    if "facilityId" in body.model_fields_set:
        facility_id = body.facilityId
    else:
        facility_id = cur["facility_id"]

    if "type" in body.model_fields_set and body.type is not None:
        itype = body.type
    else:
        itype = cur["type"]

    if "data" in body.model_fields_set:
        base = cur["data"] if isinstance(cur["data"], dict) else {}
        incoming = body.data if isinstance(body.data, dict) else {}
        data = {**base, **incoming}
    else:
        data = cur["data"]

    rows = await conn.fetch(
        """
        update inspections
        set facility_id = $3, type = $4, data = $5::jsonb, updated_at = now()
        where id = $1::uuid and inspector_id = $2::uuid
        returning id, inspector_id, facility_id, type, status, data, created_at, updated_at, submitted_at
        """,
        inspection_id,
        inspector_id,
        facility_id,
        itype,
        json.dumps(data if isinstance(data, (dict, list)) else {}),
    )
    if not rows:
        return JSONResponse(status_code=500, content={"error": "Update failed"})
    return JSONResponse(content=_map_insp(rows[0]))
