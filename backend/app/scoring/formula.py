
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.scoring.config import WEIGHTS
from app.scoring.signals import (
    bus_factor_score,
    contributor_churn_score,
    advisory_response_score,
    release_cadence_decay_score,
)

MIN_SCORE_COVERAGE = 0.70


@dataclass
class PackageRawStats:
    package_name: str
    commit_counts_by_author: dict[str, int]
    monthly_active_contributors: list[tuple[date, int]]
    advisories: list[dict] = field(default_factory=list)
    activity_dates: list[date] = field(default_factory=list)

    available_signals: dict[str, bool] = field(
        default_factory=lambda: {
            "bus_factor": True,
            "contributor_churn": True,
            "advisory_response": True,
            "release_cadence_decay": True,
        }
    )


@dataclass
class ScoreResult:
    package_name: str
    score: Optional[int]
    breakdown: dict


def compute_score(stats: PackageRawStats) -> ScoreResult:

    calculations = {
        "bus_factor": bus_factor_score(stats.commit_counts_by_author),
        "contributor_churn": contributor_churn_score(
            stats.monthly_active_contributors
        ),
        "advisory_response": advisory_response_score(stats.advisories),
        "release_cadence_decay": release_cadence_decay_score(
            stats.activity_dates
        ),
    }

    available = {
        name: bool(stats.available_signals.get(name, False))
        for name in WEIGHTS
    }

    available_weight = sum(
        WEIGHTS[name]
        for name in WEIGHTS
        if available[name]
    )

    signals = {}

    for name, (risk, detail) in calculations.items():
        signals[name] = {
            "available": available[name],
            "weight": WEIGHTS[name],
            "risk": round(risk, 2) if available[name] else None,
            **(
                detail
                if available[name]
                else {"reason": "Source data unavailable"}
            ),
        }

    unavailable = [
        name for name, is_available in available.items()
        if not is_available
    ]

    coverage_pct = round(available_weight * 100, 1)

    if available_weight < MIN_SCORE_COVERAGE:
        return ScoreResult(
            package_name=stats.package_name,
            score=None,
            breakdown={
                "signals": signals,
        "data_completeness": {
            "signals_with_data": signals_with_data,
            "total_signals": total_signals,
            "confidence": confidence,
        },
                "composite_risk": None,
                "data_coverage_pct": coverage_pct,
                "available_weight": round(available_weight, 4),
                "unavailable_signals": unavailable,
                "scoring_status": "insufficient_data",
            },
        )

    weighted_risk = sum(
        calculations[name][0] * WEIGHTS[name]
        for name in WEIGHTS
        if available[name]
    )

    composite_risk = weighted_risk / available_weight

    health_score = max(0, min(100, round(100 - composite_risk)))

    signal_has_data = {
        name: (
            calculations[name][1].get("has_data", True)
            if available[name]
            else False
        )
        for name in calculations
    }
    signals_with_data = sum(signal_has_data.values())
    total_signals = len(signal_has_data)

    if signals_with_data == total_signals:
        confidence = "high"
    elif signals_with_data >= total_signals / 2:
        confidence = "medium"
    else:
        confidence = "low"
    breakdown = {
        "signals": signals,
        "data_completeness": {
            "signals_with_data": signals_with_data,
            "total_signals": total_signals,
            "confidence": confidence,
        },
        "composite_risk": round(composite_risk, 2),
        "data_coverage_pct": coverage_pct,
        "available_weight": round(available_weight, 4),
        "unavailable_signals": unavailable,
        "scoring_status": (
            "complete" if not unavailable else "partial"
        ),
    }

    return ScoreResult(
        package_name=stats.package_name,
        score=health_score,
        breakdown=breakdown,
    )
