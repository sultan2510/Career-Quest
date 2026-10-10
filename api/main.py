"""Compatibility entry point for the integrated CareerQuest API.

Both ``uvicorn api.main:app`` and ``uvicorn backend.main:app`` now run the
same authenticated, database-backed application rather than placeholder routes.
"""
from backend.main import app


def create_app(config=None):
    """Return the configured CareerQuest application."""
    return app
