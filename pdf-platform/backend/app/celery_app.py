"""Celery application instance for the PDF platform.

Enable Celery by providing REDIS_URL and importing this module
in the worker process.
"""

from app.core.config import settings
from workers.celery import celery_app

# Re-export the configured Celery app for import from app code
__all__ = ["celery_app"]
