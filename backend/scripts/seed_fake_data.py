"""
Seeds two made-up packages (one healthy-looking, one clearly at-risk) and
runs the full scoring pipeline against your REAL local Postgres, using the
REAL Package/ScoreHistory models from app/models.py — not raw SQL guesses.

This is not real crawled data (it's invented on purpose), and it's not
meant to replace B's Week 4 hand-off. Its only job is to unblock YOUR
Phase 1 work so you can prove the whole pipeline (fake stats -> compute_score
-> write_score_history -> real row in Postgres) without waiting on B.

Run it with:
    docker exec -it supplyrisk_backend python scripts/seed_fake_data.py
"""

from datetime import date, timedelta
import random

from app.database import SessionLocal
from app.models import Package
from app.scoring import PackageRawStats, compute_score, write_score_history


FAKE_PACKAGES = [
    # (name, registry) — deliberately one healthy, one clearly at-risk case
    ("healthy-lib-example", "npm"),
    ("abandoned-lib-example", "pypi"),
]


def get_or_create_package(session, name: str, registry: str) -> Package:
    """Looks up a package by (name, registry), creates it if it doesn't exist yet."""
    package = (
        session.query(Package).filter_by(name=name, registry=registry).first()
    )
    if package is None:
        package = Package(name=name, registry=registry)
        session.add(package)
        session.commit()
        session.refresh(package)
    return package


def build_healthy_stats(package_name: str) -> PackageRawStats:
    """Realistic-shaped stats for a well-maintained project."""
    today = date.today()
    monthly_history = [
        (today - timedelta(days=30 * i), random.randint(6, 9))
        for i in range(12, 0, -1)
    ]
    activity_dates = [
        today - timedelta(days=random.randint(0, 180)) for _ in range(120)
    ]
    return PackageRawStats(
        package_name=package_name,
        commit_counts_by_author={
            "alice": 120,
            "bob": 110,
            "carol": 95,
            "dave": 80,
        },
        monthly_active_contributors=monthly_history,
        advisories=[
            {
                "published_date": today - timedelta(days=40),
                "patched_date": today - timedelta(days=35),
            }
        ],
        activity_dates=activity_dates,
    )


def build_abandoned_stats(package_name: str) -> PackageRawStats:
    """Realistic-shaped stats for a project that's clearly at risk."""
    today = date.today()
    monthly_history = [
        (today - timedelta(days=30 * i), max(0, 6 - i // 2))
        for i in range(12, 0, -1)
    ]
    activity_dates = [
        today - timedelta(days=random.randint(300, 720)) for _ in range(15)
    ]
    return PackageRawStats(
        package_name=package_name,
        commit_counts_by_author={"solo-maintainer": 340, "one-time-contributor": 2},
        monthly_active_contributors=monthly_history,
        advisories=[
            {
                "published_date": today - timedelta(days=400),
                "patched_date": None,  # still unpatched
            }
        ],
        activity_dates=activity_dates,
    )


def main():
    session = SessionLocal()
    try:
        packages_by_name = {
            name: get_or_create_package(session, name, registry)
            for name, registry in FAKE_PACKAGES
        }

        healthy_stats = build_healthy_stats("healthy-lib-example")
        abandoned_stats = build_abandoned_stats("abandoned-lib-example")

        for stats in (healthy_stats, abandoned_stats):
            result = compute_score(stats)
            package = packages_by_name[stats.package_name]
            write_score_history(session, package.id, result)
            print(
                f"{stats.package_name}: score={result.score} "
                f"(composite_risk={result.breakdown['composite_risk']})"
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()