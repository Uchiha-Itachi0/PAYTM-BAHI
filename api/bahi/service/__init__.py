"""The HTTP layer. The only package that imports FastAPI."""

from bahi.service.app import app

__all__ = ["app"]
