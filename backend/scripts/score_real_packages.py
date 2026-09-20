"""
Runs the scoring formula against B's REAL crawled packages (psf/requests,
pallets/flask, or whatever's actually in your `packages` table after
merging feature/github-crawler) and writes real scores to score_history.

This is the Task 13 checkpoint from the dependency sequence: "test scoring
formula against B's real dataset." Run this after merging B's PR and
confirming data landed (see the psql checks in the PR-review steps).

Run with:
    docker exec -it -e PYTHONPATH=/app supplyrisk_backend python scripts/score_real_packages.py
"""

from app.database import SessionLocal
from app.models import Package
from app.scoring import compute_score, write_score_history
from app.scoring.build_stats import build_stats_for_package


def main():
    session = SessionLocal()
    try:
        packages = session.query(Package).all()
        if not packages:
            print("No packages found — did feature/github-crawler get merged "
                  "and actually run yet?")
            return

        for package in packages:
            stats = build_stats_for_package(session, package)
            result = compute_score(stats)
            write_score_history(session, package.id, result)
            print(
                f"{package.registry}/{package.name}: score={result.score} "
                f"(composite_risk={result.breakdown['composite_risk']}, "
                f"contributors={len(stats.commit_counts_by_author)})"
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()