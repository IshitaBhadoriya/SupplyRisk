"""
Combines the four individual signals into one composite 0-100 risk score.

This is the single function the rest of the team will eventually call:
C's API wraps this, D's badge displays its output. That's why the return
shape (see `ScoreResult`) is worth keeping stable once others start
depending on it -- if you need to change it later, that's a "tell the team"
change, not a silent one.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date

from app.scoring.config import WEIGHTS
from app.scoring.signals import (
    bus_factor_score,
    contributor_churn_score,
    advisory_response_score,
    release_cadence_decay_score,
)


@dataclass
class PackageRawStats:
    """
    Everything the formula needs for one package, as plain data.

    This is the "contract" between B's crawled data and your formula.
    Today you'll fill this in by hand with made-up numbers in tests. Later,
    whoever writes the DB-reading code (you, in Week 3) builds one of these
    from real rows in `contributors` / `advisories` / commit history --
    but the formula itself never has to know or care where the numbers
    came from.
    """

    package_name: str
    commit_counts_by_author: dict[str, int]
    monthly_active_contributors: list[tuple[date, int]]
    advisories: list[dict] = field(default_factory=list)
    activity_dates: list[date] = field(default_factory=list)


@dataclass
class ScoreResult:
    """The full output of scoring one package."""

    package_name: str
    score: int  # 0 (max risk) - 100 (perfectly healthy), see note below
    breakdown: dict


def compute_score(stats: PackageRawStats) -> ScoreResult:
    """
    Turn raw stats into a single risk score plus a human-readable breakdown.

    Important convention: each *signal* function returns a RISK score where
    100 = worst. The final composite SCORE we report is inverted so it
    matches the product's framing ("72/100 -- higher is healthier"), which
    is what the badge and dashboard are designed to show. Keep this
    inversion in mind if you ever compare your internal risk math to the
    number a user actually sees.
    """
    bus_factor_risk, bus_factor_detail = bus_factor_score(
        stats.commit_counts_by_author
    )
    churn_risk, churn_detail = contributor_churn_score(
        stats.monthly_active_contributors
    )
    advisory_risk, advisory_detail = advisory_response_score(stats.advisories)
    cadence_risk, cadence_detail = release_cadence_decay_score(
        stats.activity_dates
    )

    composite_risk = (
        bus_factor_risk * WEIGHTS["bus_factor"]
        + churn_risk * WEIGHTS["contributor_churn"]
        + advisory_risk * WEIGHTS["advisory_response"]
        + cadence_risk * WEIGHTS["release_cadence_decay"]
    )

    # Invert: risk 0 -> health score 100, risk 100 -> health score 0.
    health_score = round(100 - composite_risk)
    health_score = max(0, min(100, health_score))  # clamp, just in case

    breakdown = {
        "signals": {
            "bus_factor": {
                "risk": bus_factor_risk,
                "weight": WEIGHTS["bus_factor"],
                **bus_factor_detail,
            },
            "contributor_churn": {
                "risk": churn_risk,
                "weight": WEIGHTS["contributor_churn"],
                **churn_detail,
            },
            "advisory_response": {
                "risk": advisory_risk,
                "weight": WEIGHTS["advisory_response"],
                **advisory_detail,
            },
            "release_cadence_decay": {
                "risk": cadence_risk,
                "weight": WEIGHTS["release_cadence_decay"],
                **cadence_detail,
            },
        },
        "composite_risk": round(composite_risk, 2),
    }

    return ScoreResult(
        package_name=stats.package_name,
        score=health_score,
        breakdown=breakdown,
    )