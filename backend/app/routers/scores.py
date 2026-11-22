
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Package
from app.scoring.build_stats import build_stats_for_package
from app.scoring.formula import compute_score

router = APIRouter(prefix="/packages", tags=["Package Scores"])


@router.get("/{package_id}/score")
def get_package_score(
    package_id: int,
    db: Session = Depends(get_db),
):
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

    stats = build_stats_for_package(db, package)
    result = compute_score(stats)

    return {
        "package": {
            "id": package.id,
            "name": package.name,
            "registry": package.registry,
            "repo_url": package.repo_url,
        },
        "health_score": result.score,
        "score_scale": "0-100, higher is healthier",
        "composite_risk": result.breakdown["composite_risk"],
        "scoring_status": result.breakdown["scoring_status"],
        "data_coverage_pct": result.breakdown["data_coverage_pct"],
        "unavailable_signals": result.breakdown["unavailable_signals"],
        "signals": result.breakdown["signals"],
        "calculated_at": datetime.now(timezone.utc),
        "data_notes": {
            "contributor_churn": (
                "Estimated from contributor first and last commit dates"
            ),
            "release_cadence_decay": (
                "Estimated using contributor last commit dates"
            ),
            "advisory_response": (
                "Based on available OSV advisory records"
            ),
        },
    }
