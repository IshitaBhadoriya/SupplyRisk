"""
Writes a ScoreResult to the real `score_history` table and updates the
`packages.current_score` / `packages.last_scored_at` cache columns.

Rewritten against the REAL schema in app/models.py (not a guess anymore):

    ScoreHistory columns actually available:
        package_id, scored_at, score, bus_factor, churn_rate, advisory_gap_days

    Package columns actually available (updated here too, since they exist
    and are clearly meant as a "latest score" cache for fast lookups):
        current_score, last_scored_at

One thing worth flagging to the team, not something to fix solo: the real
`score_history` table has no column for the 4th signal (release cadence
decay) and no generic JSON column for the full breakdown (the "why this
score" detail your formula computes). Right now that full breakdown is
only returned in memory (result.breakdown) and not persisted — fine for
Phase 1, but if D's badge detail panel or C's `/history` endpoint end up
needing the full breakdown later, that's a `models.py` change (a new
JSON `breakdown` column, or a new `release_cadence_decay` column) — and
per the team's rule, that's a group decision via a reviewed PR, not
something to add unilaterally here.
"""

from __future__ import annotations
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Package, ScoreHistory
from app.scoring.formula import ScoreResult


def write_score_history(session: Session, package_id: int, result: ScoreResult) -> None:
    """
    Insert one row into score_history for this package's freshly computed
    score, and update the package's cached current_score/last_scored_at.

    Pulls the specific raw values the real columns expect out of
    result.breakdown, rather than storing the whole breakdown blob (there's
    no column for that yet — see the module docstring above).
    """
    signals = result.breakdown["signals"]
    scored_at = datetime.utcnow()

    history_row = ScoreHistory(
        package_id=package_id,
        scored_at=scored_at,
        score=result.score,
        bus_factor=signals["bus_factor"]["risk"],
        churn_rate=signals["contributor_churn"]["risk"],
        advisory_gap_days=signals["advisory_response"].get("worst_days_open"),
    )
    session.add(history_row)

    package = session.get(Package, package_id)
    if package is not None:
        package.current_score = result.score
        package.last_scored_at = scored_at

    session.commit()