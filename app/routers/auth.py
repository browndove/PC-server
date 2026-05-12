from __future__ import annotations

import re
import uuid

import asyncpg
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.config import get_settings
from app.deps import get_db, require_inspector, require_jwt_secret_configured
from app.jwt_util import sign_access_token
from app.password_util import hash_password, verify_password
from app.pg_errors import (
    error_message_chain,
    looks_like_db_transport_failure,
    looks_like_missing_relation,
    looks_like_unique_violation,
    postgres_error_code,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=8)
    firstName: str = Field(min_length=1, validation_alias=AliasChoices("firstName", "first_name"))
    lastName: str = Field(min_length=1, validation_alias=AliasChoices("lastName", "last_name"))


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class ProfileBody(BaseModel):
    firstName: str | None = Field(default=None, min_length=1)
    lastName: str | None = Field(default=None, min_length=1)
    phone: str | None = None
    email: EmailStr | None = None


class SignatureBody(BaseModel):
    signatureUrl: HttpUrl


def _first_row_id(rows: list[asyncpg.Record] | None) -> str | None:
    if not rows:
        return None
    r = rows[0]
    v = r.get("id")
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, str) and v:
        return v
    return None


@router.get("/login")
async def login_get() -> JSONResponse:
    return JSONResponse(
        status_code=405,
        content={
            "error": "Method not allowed",
            "hint": 'Use POST with JSON body: { "email": "…", "password": "…" } (e.g. curl or the mobile app).',
        },
    )


@router.post("/signup")
async def signup(
    body: SignupBody,
    _: None = Depends(require_jwt_secret_configured),
    conn: asyncpg.Connection = Depends(get_db),
) -> JSONResponse:
    settings = get_settings()
    email = body.email.lower()
    try:
        password_hash = hash_password(body.password)
        rows = await conn.fetch(
            """
            insert into inspectors (email, password_hash, first_name, last_name, created_at, updated_at)
            values ($1, $2, $3, $4, now(), now())
            returning id
            """,
            email,
            password_hash,
            body.firstName,
            body.lastName,
        )
        rid = _first_row_id(list(rows))
        if not rid:
            print("signup insert returned no id", rows)
            return JSONResponse(
                status_code=500,
                content={"error": "Account was not saved correctly. Redeploy the API or run database migrations."},
            )
        token = sign_access_token(settings, sub=rid, email=email)
        return JSONResponse(
            status_code=201,
            content={
                "token": token,
                "inspector": {"id": rid, "email": email, "firstName": body.firstName, "lastName": body.lastName},
            },
        )
    except Exception as e:
        code = postgres_error_code(e)
        chain = error_message_chain(e)
        if code == "23505" or looks_like_unique_violation(e):
            return JSONResponse(status_code=409, content={"error": "Email already registered"})
        if code == "23502":
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Database rejected signup (often missing timestamp defaults on an older DB). Run backend migrations, then try again. If it persists, re-enter first and last name on the previous screen.",
                },
            )
        if code == "42P01" or looks_like_missing_relation(e):
            return JSONResponse(
                status_code=503,
                content={
                    "error": (
                        "Database tables are missing for this DATABASE_URL. "
                        "Confirm Railway Variables → DATABASE_URL points at the Neon branch you expect. "
                        "The API applies SQL migrations on first startup when public.inspectors does not exist; "
                        "redeploy after fixing the URL, or run: cd backend && python scripts/migrate.py"
                    ),
                    "code": "DB_MISSING_TABLES",
                },
            )
        if code == "42703":
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Database schema is out of date. Run migrations against the database used by deployment.",
                    "code": "DB_SCHEMA_OUTDATED",
                },
            )
        if looks_like_db_transport_failure(e):
            return JSONResponse(
                status_code=503,
                content={
                    "error": "API cannot reach the database. Fix DATABASE_URL (Neon connection string) in environment.",
                    "code": "DB_UNREACHABLE",
                },
            )
        if "password authentication failed" in chain.lower():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Database URL password is wrong. Update DATABASE_URL in the server environment.",
                    "code": "DB_AUTH_FAILED",
                },
            )
        if "JWT_SECRET" in chain or re.search(r"secret.*jwt|jwt.*secret|secretOrPrivateKey", chain, re.I):
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Server cannot sign login tokens. Set a strong JWT_SECRET (e.g. openssl rand -base64 32).",
                    "code": "JWT_SIGN_FAILED",
                },
            )
        if re.search(r"bcrypt|hash.*password|password.*hash", chain, re.I):
            return JSONResponse(status_code=500, content={"error": "Could not secure your password. Try again in a moment."})

        print("signup error", chain, e)
        suffix = f" (database code {code})" if code else ""
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Could not create account{suffix}. Check deployment logs and DATABASE_URL.",
            },
        )


@router.post("/login")
async def login(
    body: LoginBody,
    _: None = Depends(require_jwt_secret_configured),
    conn: asyncpg.Connection = Depends(get_db),
) -> JSONResponse:
    settings = get_settings()
    email = body.email.lower()
    rows = await conn.fetch(
        """
        select id, password_hash, first_name, last_name
        from inspectors
        where email = $1
        limit 1
        """,
        email,
    )
    row = rows[0] if rows else None
    if not row or not verify_password(body.password, row["password_hash"]):
        return JSONResponse(status_code=401, content={"error": "Invalid email or password"})
    rid = str(row["id"]) if isinstance(row["id"], uuid.UUID) else row["id"]
    token = sign_access_token(settings, sub=rid, email=email)
    return JSONResponse(
        content={
            "token": token,
            "inspector": {
                "id": rid,
                "email": email,
                "firstName": row["first_name"],
                "lastName": row["last_name"],
            },
        },
    )


@router.get("/me")
async def me(conn: asyncpg.Connection = Depends(get_db), auth: tuple[str, str] = Depends(require_inspector)) -> JSONResponse:
    inspector_id, _email = auth
    rows = await conn.fetch(
        """
        select id, email, first_name, last_name, phone, signature_url, created_at
        from inspectors
        where id = $1::uuid
        limit 1
        """,
        inspector_id,
    )
    row = rows[0] if rows else None
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    rid = str(row["id"]) if isinstance(row["id"], uuid.UUID) else row["id"]
    return JSONResponse(
        content={
            "id": rid,
            "email": row["email"],
            "firstName": row["first_name"],
            "lastName": row["last_name"],
            "phone": row["phone"],
            "signatureUrl": row["signature_url"],
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        },
    )


@router.put("/profile")
async def profile(
    body: ProfileBody,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _email = auth
    cur = await conn.fetch(
        """
        select id, email, first_name, last_name, phone
        from inspectors
        where id = $1::uuid
        limit 1
        """,
        inspector_id,
    )
    if not cur:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    c0 = cur[0]
    first_name = body.firstName if body.firstName is not None else c0["first_name"]
    last_name = body.lastName if body.lastName is not None else c0["last_name"]
    phone = body.phone if body.phone is not None else c0["phone"]
    new_email = body.email.lower() if body.email is not None else c0["email"]
    try:
        rows = await conn.fetch(
            """
            update inspectors
            set
              first_name = $2,
              last_name = $3,
              phone = $4,
              email = $5,
              updated_at = now()
            where id = $1::uuid
            returning id, email, first_name, last_name, phone
            """,
            inspector_id,
            first_name,
            last_name,
            phone,
            new_email,
        )
        row = rows[0] if rows else None
        if not row:
            return JSONResponse(status_code=404, content={"error": "Not found"})
        rid = str(row["id"]) if isinstance(row["id"], uuid.UUID) else row["id"]
        return JSONResponse(
            content={
                "id": rid,
                "email": row["email"],
                "firstName": row["first_name"],
                "lastName": row["last_name"],
                "phone": row["phone"],
            },
        )
    except asyncpg.UniqueViolationError:
        return JSONResponse(status_code=409, content={"error": "Email already in use"})
    except Exception as e:
        if getattr(e, "sqlstate", None) == "23505":
            return JSONResponse(status_code=409, content={"error": "Email already in use"})
        raise


@router.put("/signature")
async def signature(
    body: SignatureBody,
    conn: asyncpg.Connection = Depends(get_db),
    auth: tuple[str, str] = Depends(require_inspector),
) -> JSONResponse:
    inspector_id, _email = auth
    url = str(body.signatureUrl)
    rows = await conn.fetch(
        """
        update inspectors
        set signature_url = $2, updated_at = now()
        where id = $1::uuid
        returning id, signature_url
        """,
        inspector_id,
        url,
    )
    row = rows[0] if rows else None
    if not row:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    rid = str(row["id"]) if isinstance(row["id"], uuid.UUID) else row["id"]
    return JSONResponse(content={"id": rid, "signatureUrl": row["signature_url"]})
