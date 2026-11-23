from app.scoring.bulk import bulk_score_all_packages
from app.celery_app import celery_app

from app.crawlers.github_bulk import bulk_github_ingestion
from app.crawlers.osv_bulk import bulk_osv_ingestion
from app.crawlers.dependencies_bulk import bulk_dependency_ingestion


@celery_app.task
def test_task():
    """Simple task to verify that Celery is working."""
    return "SupplyRisk Celery task executed successfully"


@celery_app.task
def run_github_ingestion():
    """Run bulk GitHub contributor ingestion in a Celery worker."""
    summary = bulk_github_ingestion()
    return summary


@celery_app.task
def run_osv_ingestion():
    """Run bulk OSV advisory ingestion in a Celery worker."""
    summary = bulk_osv_ingestion()
    return summary


@celery_app.task
def run_dependency_ingestion():
    """Run bulk dependency ingestion."""
    summary = bulk_dependency_ingestion()
    return summary

@celery_app.task
def run_bulk_scoring():
    return bulk_score_all_packages()