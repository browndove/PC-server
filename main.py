"""Shim for PaaS that expect `main:app` at the repository root (Railpack, some Docker images)."""

from app.main import app

__all__ = ["app"]
