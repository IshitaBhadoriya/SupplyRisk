"""
Integration test: build_stats_for_package() must not crash when an
Advisory row has a missing/unparseable published_at (the real-world
category checked for by scripts/check_osv_data_quality.py) -- it should
skip that row and keep going, the same way the dependency-edges crawler
was fixed to skip a bad row instead of losing a whole package's data.

Every row this test creates is rolled back at the end, never committed.

Run with:
    docker exec -it -e PYTHONPATH=/app supplyrisk_backend pytest tests/test_build_stats_edge_cases.py -v
"""

import pytest
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import Package, Contributor, Advisory
from app.scoring.build_stats import build_stats_for_package
from app.scoring import compute_score


@pytest.fixture
def session():
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()


def test_build_stats_skips_advisory_with_no_published_date(session):
    package = Package(name="test-malformed-advisory-pkg", registry="pypi")
    session.add(package)
    session.flush()

    session.add(
        Contributor(package_id=package.id, username="solo-dev", commit_count=42)
    )
    # The real-world malformed case: no published_at at all.
    session.add(
        Advisory(
            package_id=package.id,
            severity="high",
            published_at=None,
            patched_at=None,
        )
    )
    session.flush()

    # Should not raise.
    stats = build_stats_for_package(session, package)
    result = compute_score(stats)

    assert stats.advisories == []  # the bad row was skipped, not kept as garbage
    assert result.score is not None  # scoring completed


def test_build_stats_keeps_good_advisories_alongside_a_bad_one(session):
    """A mix of one good, real advisory and one malformed one should keep
    the good one -- the fix shouldn't throw away valid data just because
    a sibling row is bad."""
    package = Package(name="test-mixed-advisory-pkg", registry="npm")
    session.add(package)
    session.flush()

    session.add(
        Contributor(package_id=package.id, username="dev", commit_count=10)
    )
    session.add(
        Advisory(
            package_id=package.id,
            severity="medium",
            published_at=datetime.utcnow() - timedelta(days=30),
            patched_at=None,
        )
    )
    session.add(
        Advisory(
            package_id=package.id,
            severity="low",
            published_at=None,  # malformed/missing
            patched_at=None,
        )
    )
    session.flush()

    stats = build_stats_for_package(session, package)

    assert len(stats.advisories) == 1  # the good one survived
    assert stats.advisories[0]["published_date"] is not None