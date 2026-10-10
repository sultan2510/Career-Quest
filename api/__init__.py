"""API module for the career guidance system."""

from .main import app, create_app
from .routes import router

__all__ = ["app", "create_app", "router"]