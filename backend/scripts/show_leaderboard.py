"""
Prints the current leaderboard (riskiest real packages first) from the
riskiest_packages materialized view.

Run with:
    docker exec -it -e PYTHONPATH=/app supplyrisk_backend python scripts/show_leaderboard.py [N]

N defaults to 15.
"""

import sys

from sqlalchemy import text

from app.database import SessionLocal


def show_leaderboard(limit: int = 15) -> None:
    session = SessionLocal()
    try:
        rows = session.execute(
            text(
                """
                SELECT registry, name, current_score, score_30d_ago, score_change_30d
                FROM riskiest_packages
                ORDER BY current_score ASC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).all()

        if not rows:
            print(
                "Leaderboard is empty — run score_real_packages.py and "
                "scripts/refresh_leaderboard.py first."
            )
            return

        print(f"{'Package':35} {'Score':>6} {'30d ago':>8} {'Change':>7}")
        print("-" * 60)
        for row in rows:
            label = f"{row.registry}/{row.name}"
            score_30d = f"{row.score_30d_ago:.1f}" if row.score_30d_ago is not None else "-"
            change = f"{row.score_change_30d:+.1f}" if row.score_change_30d is not None else "-"
            print(f"{label:35} {row.current_score:>6.1f} {score_30d:>8} {change:>7}")
    finally:
        session.close()


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    show_leaderboard(limit)