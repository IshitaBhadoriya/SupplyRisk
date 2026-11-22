
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Package,
    ScoreHistory,
    Contributor,
    Advisory,
)

router = APIRouter(prefix="/packages", tags=["Packages"])


@router.get("/")
def list_packages(
    registry: str | None = None,
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List packages with optional registry and name filters."""

    query = db.query(Package)

    if registry:
        query = query.filter(Package.registry == registry.lower())

    if search:
        query = query.filter(Package.name.ilike(f"%{search}%"))

    total = query.count()

    packages = (
        query.order_by(Package.name.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [
            {
                "id": p.id,
                "registry": p.registry,
                "name": p.name,
                "repo_url": p.repo_url,
                "current_score": p.current_score,
                "last_scored_at": p.last_scored_at,
            }
            for p in packages
        ],
    }


@router.get("/{package_id}")
def get_package(
    package_id: int,
    db: Session = Depends(get_db),
):
    """Get details for one package."""

    package = db.query(Package).filter(
        Package.id == package_id
    ).first()

    if not package:
        raise HTTPException(
            status_code=404,
            detail="Package not found",
        )

    return {
        "id": package.id,
        "registry": package.registry,
        "name": package.name,
        "repo_url": package.repo_url,
        "current_score": package.current_score,
        "last_scored_at": package.last_scored_at,
    }


@router.get("/{package_id}/history")
def get_score_history(
    package_id: int,
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get historical scores for a package."""

    package = db.query(Package).filter(
        Package.id == package_id
    ).first()

    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    history = (
        db.query(ScoreHistory)
        .filter(ScoreHistory.package_id == package_id)
        .order_by(ScoreHistory.scored_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "package_id": package_id,
        "count": len(history),
        "history": [
            {
                "score": item.score,
                "scored_at": item.scored_at,
                "bus_factor": item.bus_factor,
                "churn_rate": item.churn_rate,
                "advisory_gap_days": item.advisory_gap_days,
            }
            for item in history
        ],
    }


@router.get("/{package_id}/contributors")
def get_contributors(
    package_id: int,
    db: Session = Depends(get_db),
):
    """Get contributor statistics for a package."""

    package = db.query(Package).filter(
        Package.id == package_id
    ).first()

    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    contributors = (
        db.query(Contributor)
        .filter(Contributor.package_id == package_id)
        .order_by(Contributor.commit_count.desc())
        .all()
    )

    return {
        "package_id": package_id,
        "count": len(contributors),
        "contributors": [
            {
                "username": c.username,
                "commit_count": c.commit_count,
                "first_commit_at": c.first_commit_at,
                "last_commit_at": c.last_commit_at,
            }
            for c in contributors
        ],
    }


@router.get("/{package_id}/advisories")
def get_advisories(
    package_id: int,
    db: Session = Depends(get_db),
):
    """Get security advisories for a package."""

    package = db.query(Package).filter(
        Package.id == package_id
    ).first()

    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    advisories = (
        db.query(Advisory)
        .filter(Advisory.package_id == package_id)
        .order_by(Advisory.published_at.desc())
        .all()
    )

    return {
        "package_id": package_id,
        "count": len(advisories),
        "advisories": [
            {
                "severity": a.severity,
                "published_at": a.published_at,
                "patched_at": a.patched_at,
            }
            for a in advisories
        ],
    }
