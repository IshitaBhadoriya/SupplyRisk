
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Package, ScoreHistory
from app.scoring.formula import ScoreResult


def write_score_history(
    session: Session,
    package_id: int,
    result: ScoreResult
) -> bool:

    package = session.get(Package, package_id)

    if package is None:
        return False

    # Clear outdated cached scores when data is insufficient.
    if result.score is None:
        package.current_score = None
        package.last_scored_at = None
        session.commit()
        return False

    signals = result.breakdown["signals"]
    scored_at = datetime.utcnow()

    history_row = ScoreHistory(
        package_id=package_id,
        scored_at=scored_at,
        score=result.score,
        bus_factor=(
            signals["bus_factor"]["risk"]
            if signals["bus_factor"]["available"]
            else None
        ),
        churn_rate=(
            signals["contributor_churn"]["risk"]
            if signals["contributor_churn"]["available"]
            else None
        ),
        advisory_gap_days=(
            signals["advisory_response"].get("worst_days_open")
            if signals["advisory_response"]["available"]
            else None
        ),
    )

    session.add(history_row)

    package.current_score = result.score
    package.last_scored_at = scored_at

    session.commit()
    return True
