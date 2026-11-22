"""
Refreshes the riskiest_packages materialized view.

This is what "precomputed, refreshed on a schedule" means in practice —
run this after a scoring pass (e.g. after score_real_packages.py) so the
leaderboard reflects current data. CONCURRENTLY means reads of the view
aren't blocked while it refreshes — this requires the unique index on
package_id created alongside the view (Postgres enforces this).

Run with:
    docker exec -it -e PYTHONPATH=/app supplyrisk_backend python scripts/refresh_leaderboard.py

B's Celery Beat schedule (app/celery_app.py) would be the natural place
to call this on a timer later, the same way the ingestion tasks are
scheduled — not done here since that's B's scheduling layer, not this
script's concern.
"""

from sqlalchemy import text

from app.database import SessionLocal


def refresh_leaderboard() -> None:
    session = SessionLocal()
    try:
        session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY riskiest_packages"))
        session.commit()
        print("riskiest_packages materialized view refreshed.")
    finally:
        session.close()


if __name__ == "__main__":
    refresh_leaderboard()