"""Celery application and task routing configuration.

Queue topology:
  - `pdf-platform-default` (task_default_queue): catches any unrouted task.
  - `conversions`: receives `workers.tasks.perform_conversion` (see task_routes).

The worker **must** subscribe to both queues via `-Q conversions,pdf-platform-default`.
If started without `-Q`, Celery only listens on the implicit `celery` queue and
conversion tasks will never be picked up. See `infra/Dockerfile.worker` CMD.
"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "pdf_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["workers.tasks"],
)

# Optional Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="pdf-platform-default",
    task_routes={
        "workers.tasks.perform_conversion": {"queue": "conversions"},
    },
)
