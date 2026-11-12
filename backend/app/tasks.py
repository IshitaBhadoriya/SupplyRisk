from app.celery_app import celery_app


@celery_app.task
def test_task():
    return "SupplyRisk Celery task executed successfully"
