"""
Builds a PackageRawStats object from B's REAL crawled data in `contributors`,
for one package. This is the piece that genuinely had to wait for B's PR
(feature/github-crawler) to be merged -- everything else in the scoring
engine was already done and tested against fake data.

What's real vs. approximated right now:

  - bus_factor: fully real. Built directly from Contributor.commit_count
    per contributor -- exactly what the formula needs, no approximation.

  - contributor_churn: APPROXIMATED. The formula wants a real monthly
    time series of "how many contributors were active that month," but
    B's crawler currently stores only first_commit_at/last_commit_at per
    contributor (a range), not individual commit dates. So "active in
    month X" here means "X falls between that contributor's first and
    last commit" -- a reasonable proxy, but not the same as true monthly
    activity. Worth raising with the team once/if commit-level dates
    become available (would need a new table or a richer crawl).

  - advisory_response: correctly empty for now. B hasn't crawled OSV.dev
    advisories yet (that's Phase 2, Weeks 7-8) -- so this returns 0 risk,
    which is accurate given what's actually known right now, not a bug.

  - release_cadence_decay: APPROXIMATED. Uses each contributor's
    last_commit_at as one activity "event" (one point per contributor,
    not per commit). This under-counts real activity volume, but still
    captures the right *trend* (recent vs. older last-commit dates),
    which is what the signal actually measures.

None of these approximations require touching signals.py or formula.py --
they only affect what goes INTO PackageRawStats, which was always the
intended seam (see formula.py's PackageRawStats docstring).
"""

from __future__ import annotations
from datetime import date

from sqlalchemy.orm import Session

from app.models import Package, Contributor, Advisory
from app.scoring import PackageRawStats


def build_stats_for_package(session: Session, package: Package) -> PackageRawStats:
    contributors = (
        session.query(Contributor).filter_by(package_id=package.id).all()
    )

    commit_counts_by_author = {
        c.username: c.commit_count for c in contributors if c.commit_count
    }

    monthly_active_contributors = _approx_monthly_active_contributors(contributors)

    activity_dates = [
        c.last_commit_at.date() for c in contributors if c.last_commit_at
    ]

    advisories = _load_advisories(session, package)

    return PackageRawStats(
        package_name=package.name,
        commit_counts_by_author=commit_counts_by_author,
        monthly_active_contributors=monthly_active_contributors,
        advisories=advisories,
        activity_dates=activity_dates,
    )


def _load_advisories(session: Session, package: Package) -> list[dict]:
    """Real query, correctly returns [] until B's OSV.dev crawler (Phase 2) exists."""
    rows = session.query(Advisory).filter_by(package_id=package.id).all()
    return [
        {
            "published_date": row.published_at.date(),
            "patched_date": row.patched_at.date() if row.patched_at else None,
        }
        for row in rows
        if row.published_at is not None
    ]


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _subtract_months(d: date, n: int) -> date:
    month = d.month - n
    year = d.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _approx_monthly_active_contributors(
    contributors: list[Contributor], months: int = 12
) -> list[tuple[date, int]]:
    """
    See module docstring's "APPROXIMATED" note on contributor_churn.
    A contributor counts as "active" in a given month if that month falls
    within their [first_commit_at, last_commit_at] range.
    """
    today = date.today()
    current_month = _month_start(today)

    result = []
    for i in range(months, 0, -1):
        month = _subtract_months(current_month, i)
        count = 0
        for c in contributors:
            if not c.first_commit_at or not c.last_commit_at:
                continue
            first_month = _month_start(c.first_commit_at.date())
            last_month = _month_start(c.last_commit_at.date())
            if first_month <= month <= last_month:
                count += 1
        result.append((month, count))
    return result