from app.celery_app import celery_app
from app.crawlers.github_bulk import bulk_github_ingestion
from app.crawlers.osv_bulk import bulk_osv_ingestion
from app.crawlers.dependencies_bulk import bulk_dependency_ingestion


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


@celery_app.task
def run_osv_ingestion():
    """
    Run bulk OSV advisory ingestion in a Celery worker.
    """
    bulk_osv_ingestion()
    return "OSV bulk ingestion completed successfully"


@celery_app.task
def run_dependency_ingestion():
    """
    Run bulk dependency ingestion in a Celery worker.
    """
    bulk_dependency_ingestion()
    return "Dependency bulk ingestion completed successfully"