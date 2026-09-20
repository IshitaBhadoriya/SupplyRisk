"""
Scoring engine package.

Usage from elsewhere in the codebase (e.g. C's API routes, later):

    from app.scoring import PackageRawStats, compute_score, write_score_history

    stats = PackageRawStats(...)          # built from real DB rows
    result = compute_score(stats)         # pure calculation, no DB needed
    write_score_history(session, package_id, result)   # persists it
"""

from app.scoring.formula import PackageRawStats, ScoreResult, compute_score
from app.scoring.write_score import write_score_history

__all__ = [
    "PackageRawStats",
    "ScoreResult",
    "compute_score",
    "write_score_history",
]