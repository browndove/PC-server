from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import close_pool
from app.routers import auth, checklists, facilities, health, inspections


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
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
