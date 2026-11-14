from app.celery_app import celery_app
from app.crawlers.github_bulk import bulk_github_ingestion

@celery_app.task
def test_task():
    return "SupplyRisk Celery task executed successfully"

@celery_app.task
def run_github_ingestion():
    """
    Run the bulk GitHub contributor ingestion in a Celery worker.
    """
    bulk_github_ingestion()
    return "GitHub bulk ingestion completed successfully"
