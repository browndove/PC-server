import asyncio
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import close_pool, get_pool
from app.schema_bootstrap import run_startup_migrations
from app.routers import auth, checklists, facilities, health, inspections


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.schema_migration_task = None
    if settings.database_url_normalized:
        norm = settings.database_url_normalized
        try:
            host = urlparse(norm).hostname
        except Exception:
            host = None
        src = "environment" if settings.uses_database_url_from_environment else "database_defaults.py"
        print(f"database: connecting via {src} pg_host={host!r}", flush=True)
        await get_pool()

        async def _run_schema_migrations() -> None:
            try:
                pool = await get_pool()
                async with pool.acquire() as conn:
                    await run_startup_migrations(conn)
                print("startup migrations task finished.", flush=True)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print("startup migrations failed:", repr(e), flush=True)

        app.state.schema_migration_task = asyncio.create_task(_run_schema_migrations())
    yield
    task = getattr(app.state, "schema_migration_task", None)
    if task is not None and not task.done():
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    await close_pool()


settings = get_settings()
app = FastAPI(title="Quik Inspect API", lifespan=lifespan)

_raw = settings.cors_origin.strip()
_allow = ["*"] if (not _raw or _raw == "*") else [x.strip() for x in _raw.split(",") if x.strip()]
_credentials = False if _allow == ["*"] else True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow,
    allow_credentials=_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(facilities.router)
app.include_router(inspections.router)
app.include_router(checklists.router)
