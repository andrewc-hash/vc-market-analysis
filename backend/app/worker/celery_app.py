"""Celery application factory with Redis broker."""

from celery import Celery

from app.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "vc_market_analysis",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        result_extended=True,
        # A full 3-round analyst↔judge debate (two slow Gemini 2.5 Pro analysts + judge each
        # round) plus the 65K-token compile can legitimately run long; 40 min was too tight and
        # killed a max-debate run mid-compile. Give it headroom.
        task_soft_time_limit=3000,  # 50 min soft limit (rate-limit retries need time)
        task_time_limit=3900,       # 65 min hard limit
        # Stale-result hygiene via TTL — replaces the old routes-level wipe-all purge,
        # which clobbered concurrent in-flight runs' results. Completed reports live in
        # the durable History store; Redis results only need to outlive the UI poll.
        result_expires=259200,  # 3 days
        # An executing task must NEVER be redelivered on crash/restart (it would silently
        # re-burn LLM tokens + Tavily credits) — explicit early-ack, no reject-on-lost.
        task_acks_late=False,
        task_reject_on_worker_lost=False,
        # Don't prefetch a deep unacked buffer; killed-while-queued messages were the
        # source of the ghost-task redelivery incident (visibility_timeout restore).
        worker_prefetch_multiplier=1,
        broker_transport_options={"visibility_timeout": 4500},  # > hard time limit
    )
    app.autodiscover_tasks(["app.worker"])
    return app


celery_app = create_celery_app()
