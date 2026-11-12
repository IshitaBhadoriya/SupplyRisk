"""
Unit tests for the scoring engine.

These need NOTHING from B, C, or D -- no database, no API, no real crawled
data. Every test builds its own tiny synthetic input by hand. This is the
whole point: you can write, run, and trust this file in Week 1-2, and it
keeps working exactly the same way once real data shows up in Week 3,
because signals.py and formula.py never touch the database at all.

Run with:
    docker exec -it supplyrisk_backend pytest tests/test_scoring.py -v
"""

from datetime import date, timedelta

from app.scoring.signals import (
    bus_factor_score,
    contributor_churn_score,
    advisory_response_score,
    release_cadence_decay_score,
)
from app.scoring.formula import PackageRawStats, compute_score


# ---------- bus_factor_score ----------


def test_bus_factor_single_contributor_is_max_risk():
    risk, detail = bus_factor_score({"solo": 500})
    assert risk == 100.0
    assert detail["top_contributor"] == "solo"


def test_bus_factor_evenly_split_is_low_risk():
    risk, _ = bus_factor_score({"a": 50, "b": 50, "c": 50, "d": 50})
    assert risk == 25.0  # each contributor did exactly 25% of commits


def test_bus_factor_no_commits_is_max_risk():
    risk, detail = bus_factor_score({})
    assert risk == 100.0
    assert detail["top_contributor"] is None


# ---------- contributor_churn_score ----------


def test_churn_declining_contributors_is_high_risk():
    today = date.today()
    history = [
        (today - timedelta(days=30 * i), count)
        for i, count in zip(range(12, 0, -1), [10] * 6 + [1] * 6)
    ]
    risk, detail = contributor_churn_score(history)
    assert risk > 50.0
    assert detail["latest_count"] < detail["earliest_count"]


def test_churn_stable_contributors_is_low_risk():
    today = date.today()
    history = [(today - timedelta(days=30 * i), 8) for i in range(12, 0, -1)]
    risk, _ = contributor_churn_score(history)
    assert risk == 0.0


def test_churn_insufficient_history_returns_neutral_score():
    risk, detail = contributor_churn_score([(date.today(), 5)])
    assert risk == 50.0
    assert "Not enough history" in detail["reason"]


# ---------- advisory_response_score ----------


def test_advisory_no_advisories_is_zero_risk():
    risk, _ = advisory_response_score([])
    assert risk == 0.0


def test_advisory_unpatched_long_open_is_high_risk():
    old_advisory = [
        {"published_date": date.today() - timedelta(days=400), "patched_date": None}
    ]
    risk, detail = advisory_response_score(old_advisory)
    assert risk == 100.0  # capped at ADVISORY_MAX_RISK_DAYS (365)
    assert detail["worst_days_open"] == 400


def test_advisory_quickly_patched_is_low_risk():
    quick_fix = [
        {
            "published_date": date.today() - timedelta(days=10),
            "patched_date": date.today() - timedelta(days=9),
        }
    ]
    risk, detail = advisory_response_score(quick_fix)
    assert risk < 5.0
    assert detail["worst_days_open"] == 1


# ---------- release_cadence_decay_score ----------


def test_cadence_no_activity_is_max_risk():
    risk, _ = release_cadence_decay_score([])
    assert risk == 100.0


def test_cadence_steady_activity_is_low_risk():
    today = date.today()
    dates = [today - timedelta(days=d) for d in range(0, 360, 5)]
    risk, _ = release_cadence_decay_score(dates)
    assert risk < 20.0


def test_cadence_dropped_off_is_high_risk():
    today = date.today()
    # lots of activity 7-12 months ago, almost none in the last 6 months
    dates = [today - timedelta(days=d) for d in range(180, 360, 3)]
    risk, detail = release_cadence_decay_score(dates)
    assert risk > 70.0
    assert detail["recent_count"] < detail["previous_count"]


# ---------- compute_score (the full composite) ----------


def test_compute_score_healthy_package_scores_high():
    today = date.today()
    stats = PackageRawStats(
        package_name="healthy-example",
        commit_counts_by_author={"a": 100, "b": 90, "c": 85, "d": 80},
        monthly_active_contributors=[
            (today - timedelta(days=30 * i), 8) for i in range(12, 0, -1)
        ],
        advisories=[
            {
                "published_date": today - timedelta(days=20),
                "patched_date": today - timedelta(days=18),
            }
        ],
        activity_dates=[today - timedelta(days=d) for d in range(0, 180, 4)],
    )
    result = compute_score(stats)
    assert result.score >= 70
    assert "signals" in result.breakdown


def test_compute_score_abandoned_package_scores_low():
    today = date.today()
    stats = PackageRawStats(
        package_name="abandoned-example",
        commit_counts_by_author={"solo": 300, "other": 1},
        monthly_active_contributors=[
            (today - timedelta(days=30 * i), max(0, 5 - i))
            for i in range(12, 0, -1)
        ],
        advisories=[
            {"published_date": today - timedelta(days=500), "patched_date": None}
        ],
        activity_dates=[today - timedelta(days=d) for d in range(300, 720, 20)],
    )
    result = compute_score(stats)
    assert result.score <= 30


def test_compute_score_is_bounded_0_to_100():
    today = date.today()
    stats = PackageRawStats(
        package_name="edge-case",
        commit_counts_by_author={},
        monthly_active_contributors=[],
        advisories=[],
        activity_dates=[],
    )
    result = compute_score(stats)
    assert 0 <= result.score <= 100