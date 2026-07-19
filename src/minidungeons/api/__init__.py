"""Optional FastAPI adapter. Install the ``api`` project extra to run it."""

from .app import app, create_app

__all__ = ["app", "create_app"]
