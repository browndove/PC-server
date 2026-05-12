from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    jwt_secret: str = ""
    jwt_expires_in: str = "7d"
    cors_origin: str = "*"

    @property
    def database_url_normalized(self) -> str:
        if not self.database_url:
            return ""
        return normalize_database_url(self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
