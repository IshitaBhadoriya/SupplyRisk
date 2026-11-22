"""
Phase 3 edge-case tests: the "has_data" / data_completeness signal added
to distinguish "genuinely risky" from "we have no data to judge this on."
Pure logic, no database needed -- same philosophy as test_scoring.py.

Run with:
    docker exec -it supplyrisk_backend pytest tests/test_scoring_edge_cases.py -v
"""

from datetime import date, timedelta

from app.scoring.signals import (
    bus_factor_score,
    contributor_churn_score,
    advisory_response_score,
    release_cadence_decay_score,
)
from app.scoring.formula import PackageRawStats, compute_score


# ---------- has_data flags on each signal ----------


def test_bus_factor_has_data_false_when_empty():
    _, detail = bus_factor_score({})
    assert detail["has_data"] is False


def test_bus_factor_has_data_true_when_present():
    _, detail = bus_factor_score({"alice": 10})
    assert detail["has_data"] is True


def test_churn_has_data_false_with_insufficient_history():
    _, detail = contributor_churn_score([(date.today(), 5)])
    assert detail["has_data"] is False


def test_churn_has_data_true_with_enough_history():
    today = date.today()
    history = [(today - timedelta(days=30 * i), 5) for i in range(12, 0, -1)]
    _, detail = contributor_churn_score(history)
    assert detail["has_data"] is True


def test_advisory_has_data_true_even_with_zero_advisories():
    # Zero advisories is real information ("we checked OSV, found
    # nothing"), not missing data -- has_data should still be True,
    # unlike the other three signals when they have nothing to work with.
    _, detail = advisory_response_score([])
    assert detail["has_data"] is True


def test_advisory_has_data_true_with_real_advisories():
    today = date.today()
    _, detail = advisory_response_score(
        [{"published_date": today - timedelta(days=10), "patched_date": None}]
    )
    assert detail["has_data"] is True


def test_cadence_has_data_false_with_no_activity():
    _, detail = release_cadence_decay_score([])
    assert detail["has_data"] is False


def test_cadence_has_data_true_with_activity():
    today = date.today()
    dates = [today - timedelta(days=d) for d in range(0, 180, 4)]
    _, detail = release_cadence_decay_score(dates)
    assert detail["has_data"] is True


# ---------- data_completeness aggregation in compute_score ----------


def test_compute_score_full_data_is_high_confidence():
    today = date.today()
    stats = PackageRawStats(
        package_name="full-data-example",
        commit_counts_by_author={"a": 100, "b": 90, "c": 85},
        monthly_active_contributors=[
            (today - timedelta(days=30 * i), 8) for i in range(12, 0, -1)
        ],
        advisories=[],
        activity_dates=[today - timedelta(days=d) for d in range(0, 180, 4)],
    )
    result = compute_score(stats)
    completeness = result.breakdown["data_completeness"]
    assert completeness["signals_with_data"] == 4
    assert completeness["total_signals"] == 4
    assert completeness["confidence"] == "high"


def test_compute_score_no_crawled_data_is_low_confidence():
    """
    The real-world case found during Phase 1/2 full-scale testing: a
    package with no GitHub-linked contributor data at all (e.g.
    SQLAlchemy, celery, tensorflow, before the pypi.py URL-extraction
    fix). It should still score -- not crash, not raise -- but be
    flagged low-confidence rather than silently treated the same as a
    genuinely well-evidenced, actually-abandoned project.

    Input shape matters here: build_stats.py's
    _approx_monthly_active_contributors() always returns
    CHURN_LOOKBACK_MONTHS entries (12), even for a package with zero
    contributors -- every entry is just (month, 0), not an empty list.
    Using the real shape (not a bare []) is what caught a real gap
    while writing this test: has_data for churn originally only checked
    list length, so 12 months of all-zero counted as "has data" even
    though there's no real signal in it. Fixed in signals.py.
    """
    today = date.today()
    twelve_zero_months = [
        (today - timedelta(days=30 * i), 0) for i in range(12, 0, -1)
    ]
    stats = PackageRawStats(
        package_name="no-crawled-data-example",
        commit_counts_by_author={},
        monthly_active_contributors=twelve_zero_months,
        advisories=[],
        activity_dates=[],
    )
    result = compute_score(stats)
    completeness = result.breakdown["data_completeness"]

    # Score is unchanged from Phase 1/2 formula behavior -- this test
    # documents that on purpose, it does not newly assert a "better"
    # score. It's 30, not 0: bus_factor/churn/cadence all max out at 100
    # risk (no data), but advisory_response correctly contributes 0 risk
    # (zero known vulnerabilities IS real, earned information, not a gap)
    # -- composite_risk = 100*.35 + 100*.2 + 0*.3 + 100*.15 = 70, score=30.
    # Real production packages that hit flat score=0 (e.g. SQLAlchemy,
    # moment) likely ALSO carry real OSV advisories on top of having no
    # contributor data -- a worse combination than this clean synthetic
    # case, not a contradiction of it.
    assert result.score == 30

    # Only advisory_response has_data=True (zero advisories is real
    # information); the other 3 signals had nothing real to work with.
    assert completeness["signals_with_data"] == 1
    assert completeness["confidence"] == "low"


def test_compute_score_partial_data_is_medium_confidence():
    """A package with real contributor commit counts but no churn/activity
    history yet (e.g. only just crawled, too recently for a time series)
    should land in the middle, not be conflated with either extreme."""
    stats = PackageRawStats(
        package_name="partial-data-example",
        commit_counts_by_author={"solo": 50},
        monthly_active_contributors=[],  # genuinely insufficient history
        advisories=[],
        activity_dates=[],
    )
    result = compute_score(stats)
    completeness = result.breakdown["data_completeness"]
    # has_data: bus_factor=True, churn=False (len<2), advisory=True, cadence=False
    assert completeness["signals_with_data"] == 2
    assert completeness["confidence"] == "medium"