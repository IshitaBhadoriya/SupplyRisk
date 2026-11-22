
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models import (
    Package,
    Contributor,
    Advisory,
    IngestionStatus,
)
from app.scoring import PackageRawStats


def build_stats_for_package(
    session: Session,
    package: Package
) -> PackageRawStats:

    contributors = (
        session.query(Contributor)
        .filter_by(package_id=package.id)
        .all()
    )

    statuses = {
        row.source: row
        for row in (
            session.query(IngestionStatus)
            .filter_by(package_id=package.id)
            .all()
        )
    }

    github_status = statuses.get("github")
    osv_status = statuses.get("osv")

    github_available = (
        github_status is not None
        and github_status.status == "success"
    )

    osv_available = (
        osv_status is not None
        and osv_status.status == "success"
    )

    commit_counts_by_author = {
        c.username: c.commit_count
        for c in contributors
        if c.username and c.commit_count
    }

    monthly_active_contributors = (
        _approx_monthly_active_contributors(contributors)
    )

    activity_dates = [
        c.last_commit_at.date()
        for c in contributors
        if c.last_commit_at
    ]

    # An empty contributor result after successful ingestion
    # is measured data. Missing timestamps on existing records
    # are not sufficient evidence for churn/cadence calculations.
    has_contributor_timestamps = any(
        c.first_commit_at and c.last_commit_at
        for c in contributors
    )

    has_activity_timestamps = any(
        c.last_commit_at for c in contributors
    )

    bus_available = github_available

    churn_available = (
        github_available
        and (
            not contributors
            or has_contributor_timestamps
        )
    )

    cadence_available = (
        github_available
        and (
            not contributors
            or has_activity_timestamps
        )
    )

    advisories = _load_advisories(session, package)

    return PackageRawStats(
        package_name=package.name,
        commit_counts_by_author=commit_counts_by_author,
        monthly_active_contributors=monthly_active_contributors,
        advisories=advisories,
        activity_dates=activity_dates,
        available_signals={
            "bus_factor": bus_available,
            "contributor_churn": churn_available,
            "advisory_response": osv_available,
            "release_cadence_decay": cadence_available,
        },
    )


def _load_advisories(
    session: Session,
    package: Package
) -> list[dict]:

    rows = (
        session.query(Advisory)
        .filter_by(package_id=package.id)
        .all()
    )

    return [
        {
            "published_date": row.published_at.date(),
            "patched_date": (
                row.patched_at.date()
                if row.patched_at else None
            ),
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
    contributors: list[Contributor],
    months: int = 12
) -> list[tuple[date, int]]:

    today = date.today()
    current_month = _month_start(today)

    result = []

    for i in range(months, 0, -1):
        month = _subtract_months(current_month, i)
        count = 0

        for contributor in contributors:
            if (
                not contributor.first_commit_at
                or not contributor.last_commit_at
            ):
                continue

            first_month = _month_start(
                contributor.first_commit_at.date()
            )
            last_month = _month_start(
                contributor.last_commit_at.date()
            )

            if first_month <= month <= last_month:
                count += 1

        result.append((month, count))

    return result
