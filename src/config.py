"""Compatibility shim that re-exports the application Config."""
from app.config import Config  # noqa: F401

__all__ = ["Config"]
