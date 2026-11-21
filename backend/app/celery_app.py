from celery import Celery
from celery.schedules import crontab

beat_schedule = {
    "nightly-github-ingestion": {
        "task": "app.tasks.run_github_ingestion",
        "schedule": crontab(hour=2, minute=0),
    },
    "nightly-osv-ingestion": {
        "task": "app.tasks.run_osv_ingestion",
        "schedule": crontab(hour=3, minute=0),
    },
    "nightly-dependency-ingestion": {
        "task": "app.tasks.run_dependency_ingestion",
        "schedule": crontab(hour=4, minute=0),
    },
}
celery_app = Celery(
    "supplyrisk",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
    include=["app.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=False,
    beat_schedule=beat_schedule,
)
