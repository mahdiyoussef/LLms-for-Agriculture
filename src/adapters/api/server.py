"""Compatibility entry point for the secured FastAPI application.

New deployments should use ``src.api.app:app`` directly. The legacy import path
is retained so existing scripts can migrate without a breaking module change.
"""

from src.api.app import app

__all__ = ["app"]
