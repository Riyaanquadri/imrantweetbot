"""Compatibility shim exposing the main application logger."""
from app.logger import logger  # noqa: F401

__all__ = ["logger"]
