import os
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.database_defaults import DEFAULT_DATABASE_URL
from app.jwt_defaults import DEFAULT_JWT_SECRET


def _settings_config() -> SettingsConfigDict:
    # On Railway, never read a bundled .env from disk — it can override or blank DATABASE_URL.
    on_railway = bool(
        os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("RAILWAY_PROJECT_ID")
        or os.environ.get("RAILWAY_SERVICE_ID"),
    )
    return SettingsConfigDict(
        env_file=None if on_railway else ".env",
        env_ignore_empty=True,
        extra="ignore",
    )


def normalize_database_url(raw: str) -> str:
    """Strip channel_binding=require (can hang with some serverless drivers)."""
    raw = raw.strip()
    try:
        u = urlparse(raw)
        q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k.lower() != "channel_binding"]
        new_query = urlencode(q)
        out = urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))
        return out.rstrip("?")
    except Exception:
        return raw


class Settings(BaseSettings):
    model_config = _settings_config()

    database_url: str = ""
    jwt_secret: str = ""
    jwt_expires_in: str = "7d"
    cors_origin: str = "*"

    @property
    def effective_jwt_secret(self) -> str:
        return (self.jwt_secret or DEFAULT_JWT_SECRET).strip()

    @property
    def uses_database_url_from_environment(self) -> bool:
        return bool(self.database_url.strip())

    @property
    def effective_database_url(self) -> str:
        return (self.database_url or DEFAULT_DATABASE_URL).strip()

    @property
    def database_url_normalized(self) -> str:
        raw = self.effective_database_url
        if not raw:
            return ""
        return normalize_database_url(raw)


@lru_cache
def get_settings() -> Settings:
    return Settings()
