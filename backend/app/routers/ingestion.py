from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import IngestionStatus, Package

router = APIRouter(prefix="/ingestion", tags=["Ingestion Status"])


@router.get("/status")
def get_ingestion_overview(
    db: Session = Depends(get_db),
):
    """
    Return an overall summary of package ingestion across all sources.
    """

    statuses = db.query(IngestionStatus).all()

    summary = defaultdict(
        lambda: {
            "total_packages_tracked": 0,
            "status_counts": {},
            "total_records_found": 0,
            "last_success_at": None,
        }
    )

    for item in statuses:
        source_summary = summary[item.source]

        source_summary["total_packages_tracked"] += 1

        current_status = item.status
        source_summary["status_counts"][current_status] = (
            source_summary["status_counts"].get(current_status, 0) + 1
        )

        source_summary["total_records_found"] += item.records_found or 0

        if item.last_success_at:
            previous = source_summary["last_success_at"]

            if previous is None or item.last_success_at > previous:
                source_summary["last_success_at"] = item.last_success_at

    return {
        "total_packages": db.query(Package).count(),
        "total_ingestion_records": len(statuses),
        "sources": dict(summary),
    }


@router.get("/failed")
def get_failed_ingestions(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Return recently failed ingestion records.
    """

    results = (
        db.query(IngestionStatus, Package)
        .join(Package, Package.id == IngestionStatus.package_id)
        .filter(IngestionStatus.status == "failed")
        .order_by(IngestionStatus.last_attempt_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "count": len(results),
        "failed_ingestions": [
            {
                "package_id": package.id,
                "package_name": package.name,
                "registry": package.registry,
                "source": status.source,
                "status": status.status,
                "last_attempt_at": status.last_attempt_at,
                "last_success_at": status.last_success_at,
                "records_found": status.records_found,
                "error_message": status.error_message,
            }
            for status, package in results
        ],
    }


@router.get("/packages/{package_id}")
def get_package_ingestion_status(
    package_id: int,
    db: Session = Depends(get_db),
):
    """
    Return ingestion status for every source for one package.
    """

    package = (
        db.query(Package)
        .filter(Package.id == package_id)
        .first()
    )

    if package is None:
        raise HTTPException(
            status_code=404,
            detail=f"Package with ID {package_id} not found",
        )

    statuses = (
        db.query(IngestionStatus)
        .filter(IngestionStatus.package_id == package_id)
        .order_by(IngestionStatus.source)
        .all()
    )

    return {
        "package": {
            "id": package.id,
            "name": package.name,
            "registry": package.registry,
        },
        "ingestion_status": [
            {
                "source": item.source,
                "status": item.status,
                "last_attempt_at": item.last_attempt_at,
                "last_success_at": item.last_success_at,
                "records_found": item.records_found,
                "error_message": item.error_message,
            }
            for item in statuses
        ],
    }
