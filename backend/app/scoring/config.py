"""
Scoring weights and thresholds, kept in one place on purpose.

Why this file exists separately: in Phase 4 you have to defend *why* each
signal is weighted the way it is. Keeping every tunable number here (instead
of scattered as magic numbers inside formulas.py) means you can point to one
file and say "these are our weights, here's why," and you can experiment
with different weightings without touching the actual calculation logic.

These starting weights are a reasonable first guess based on how OpenSSF
Scorecard-style tools reason about risk (bus factor and unpatched advisories
are usually treated as the strongest signals of real danger). Treat these as
a hypothesis to refine once you're scoring real packages in Week 3, not as
a final answer.
"""

# Each signal contributes a 0-100 "risk score" (0 = totally healthy,
# 100 = maximum risk). WEIGHTS must sum to 1.0 -- they control how much each
# signal contributes to the final composite score.
WEIGHTS = {
    "bus_factor": 0.35,          # commit concentration among contributors
    "contributor_churn": 0.20,   # how fast the contributor pool is shrinking
    "advisory_response": 0.30,   # how slowly known vulnerabilities get patched
    "release_cadence_decay": 0.15,  # how much release/commit activity has dropped
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "WEIGHTS must sum to 1.0"

# --- Thresholds used inside individual signal calculations ---

# Advisory response: an advisory patched same-day is 0 risk; one that's been
# open this many days (or more, or never patched) is treated as max risk.
ADVISORY_MAX_RISK_DAYS = 365

# Contributor churn: we look back this many months of contributor-count
# history to measure the trend.
CHURN_LOOKBACK_MONTHS = 12

# Release cadence decay: we compare the last N months of activity against
# the N months before that, to catch a project that's slowing down.
CADENCE_WINDOW_MONTHS = 6
