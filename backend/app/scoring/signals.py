"""
The four raw signal calculations.

Design choice worth keeping: every function here takes plain Python data
(dicts, lists, dates) and returns plain Python data. None of them touch the
database or know anything about SQLAlchemy models. That's deliberate -- it's
what lets you write and fully test this file today, using made-up numbers,
without waiting on B's crawlers or the real `contributors` / `advisories`
tables to have real rows in them. Once B's data exists, the only thing that
changes is *where the input dicts come from* (a real DB query instead of a
hand-written test fixture) -- this file itself doesn't need to change.

Each function returns a tuple: (risk_score: float 0-100, detail: dict).
The detail dict is what eventually powers the badge's "why this score"
panel on the frontend, so keep it human-readable, not just raw numbers.
"""

from __future__ import annotations
from datetime import date
from typing import Optional

from app.scoring.config import (
    ADVISORY_MAX_RISK_DAYS,
    CHURN_LOOKBACK_MONTHS,
    CADENCE_WINDOW_MONTHS,
)


def bus_factor_score(commit_counts_by_author: dict[str, int]) -> tuple[float, dict]:
    """
    How concentrated commits are among contributors.

    Input: {"alice": 340, "bob": 12, "carol": 4}  (author -> total commits)
    Higher concentration in one person = higher risk.

    A project with zero commits is treated as maximum risk (nothing to
    evaluate is not the same as healthy).
    """
    total_commits = sum(commit_counts_by_author.values())

    if total_commits == 0 or not commit_counts_by_author:
        return 100.0, {
            "reason": "No commit history available",
            "top_contributor": None,
            "top_contributor_share_pct": None,
        }

    top_author, top_commits = max(
        commit_counts_by_author.items(), key=lambda pair: pair[1]
    )
    top_share = top_commits / total_commits  # 0.0 - 1.0

    # Risk scales directly with concentration: 100% from one person = 100 risk,
    # evenly split across many people = low risk.
    risk = round(top_share * 100, 2)

    return risk, {
        "reason": f"Top contributor '{top_author}' authored "
        f"{top_share:.0%} of all commits",
        "top_contributor": top_author,
        "top_contributor_share_pct": round(top_share * 100, 1),
        "total_contributors": len(commit_counts_by_author),
    }


def contributor_churn_score(
    monthly_active_contributors: list[tuple[date, int]]
) -> tuple[float, dict]:
    """
    How fast the active-contributor count is shrinking.

    Input: a list of (month_start_date, active_contributor_count) tuples,
    ideally covering the last CHURN_LOOKBACK_MONTHS, sorted oldest -> newest.
    e.g. [(date(2025,9,1), 8), (date(2025,10,1), 7), ..., (date(2026,8,1), 2)]

    We compare the earliest and latest values in the window to get a simple,
    explainable trend, rather than a more complex regression -- easy to
    defend in the Phase 4 interview ("we compare contributor count now vs.
    N months ago").
    """
    window = monthly_active_contributors[-CHURN_LOOKBACK_MONTHS:]

    if len(window) < 2:
        return 50.0, {
            "reason": "Not enough history to measure a trend yet",
            "data_points": len(window),
        }

    _, earliest_count = window[0]
    _, latest_count = window[-1]

    if earliest_count == 0:
        # Project already had no contributors at the start of the window --
        # can't measure decline from zero, treat as high risk if it's still zero.
        risk = 100.0 if latest_count == 0 else 40.0
    else:
        decline_pct = (earliest_count - latest_count) / earliest_count
        decline_pct = max(0.0, decline_pct)  # growth isn't "negative risk" here
        risk = round(min(decline_pct, 1.0) * 100, 2)

    return risk, {
        "reason": f"Active contributors went from {earliest_count} to "
        f"{latest_count} over the last {len(window)} months",
        "earliest_count": earliest_count,
        "latest_count": latest_count,
        "months_measured": len(window),
    }


def advisory_response_score(
    advisories: list[dict],
) -> tuple[float, dict]:
    """
    How slowly known security advisories get patched.

    Input: a list of dicts like:
        {"published_date": date(...), "patched_date": date(...) or None}
    `patched_date=None` means still unpatched as of today.

    Uses the single WORST (longest-open) advisory to drive the score --
    one severe, ignored vulnerability is disqualifying even if everything
    else about the project looks fine.
    """
    if not advisories:
        return 0.0, {
            "reason": "No known security advisories on record",
            "advisory_count": 0,
        }

    today = date.today()
    worst_days_open = 0
    worst_advisory_index = None

    for i, advisory in enumerate(advisories):
        published = advisory["published_date"]
        patched = advisory.get("patched_date")
        days_open = ((patched or today) - published).days
        if days_open > worst_days_open:
            worst_days_open = days_open
            worst_advisory_index = i

    risk = round(min(worst_days_open / ADVISORY_MAX_RISK_DAYS, 1.0) * 100, 2)

    return risk, {
        "reason": f"Longest-open advisory has been unresolved for "
        f"{worst_days_open} days",
        "worst_days_open": worst_days_open,
        "advisory_count": len(advisories),
        "worst_advisory_index": worst_advisory_index,
    }


def release_cadence_decay_score(
    activity_dates: list[date],
) -> tuple[float, dict]:
    """
    How much recent activity (commits or releases) has dropped compared to
    the project's own recent-past baseline.

    Input: a flat list of dates (commit dates or release dates), any order.
    We compare the count in the most recent CADENCE_WINDOW_MONTHS months
    against the count in the CADENCE_WINDOW_MONTHS months before that --
    a project is judged against its *own* history, not an absolute number,
    so a naturally quiet small project isn't unfairly penalized.
    """
    if not activity_dates:
        return 100.0, {
            "reason": "No commit or release activity on record at all",
            "recent_count": 0,
            "previous_count": 0,
        }

    today = date.today()
    window_days = CADENCE_WINDOW_MONTHS * 30

    recent_cutoff = today - _days(window_days)
    previous_cutoff = today - _days(window_days * 2)

    recent_count = sum(1 for d in activity_dates if d >= recent_cutoff)
    previous_count = sum(
        1 for d in activity_dates if previous_cutoff <= d < recent_cutoff
    )

    if previous_count == 0:
        # No prior baseline to compare against.
        risk = 0.0 if recent_count > 0 else 100.0
    else:
        drop_pct = (previous_count - recent_count) / previous_count
        drop_pct = max(0.0, drop_pct)  # more recent activity isn't negative risk
        risk = round(min(drop_pct, 1.0) * 100, 2)

    return risk, {
        "reason": f"Activity went from {previous_count} events to "
        f"{recent_count} events over the last {CADENCE_WINDOW_MONTHS} months",
        "recent_count": recent_count,
        "previous_count": previous_count,
        "window_months": CADENCE_WINDOW_MONTHS,
    }


def _days(n: int):
    from datetime import timedelta

    return timedelta(days=n)