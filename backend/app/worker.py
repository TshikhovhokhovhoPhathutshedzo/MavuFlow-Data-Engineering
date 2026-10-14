from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "mavuflow_studio",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker"],
)

celery_app.conf.update(task_track_started=True, task_time_limit=3600)


@celery_app.task(name="app.health")
def health_check_task() -> str:
    return "worker-ok"
