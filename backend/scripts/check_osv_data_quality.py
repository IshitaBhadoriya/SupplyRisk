"""
Read-only diagnostic: checks whether any Advisory rows have a
published_at that's NULL despite OSV presumably having returned a date,
which would point at the same "one malformed row can silently cost data"
pattern already found and fixed once in dependencies.py (Phase 2) -- this
time possibly in B's osv.py instead.

Does NOT modify anything and does NOT conclude osv.py has a bug on its
own -- NULL published_at can also legitimately mean OSV itself didn't
provide one for that advisory. This just surfaces the count so it can be
checked against OSV's raw response and flagged to B if it looks wrong,
rather than assumed either way.

Run with:
    docker exec -it -e PYTHONPATH=/app supplyrisk_backend python scripts/check_osv_data_quality.py
"""

from app.database import SessionLocal
from app.models import Advisory


def main():
    session = SessionLocal()
    try:
        total_advisories = session.query(Advisory).count()
        null_published = (
            session.query(Advisory)
            .filter(Advisory.published_at.is_(None))
            .count()
        )
        null_severity = (
            session.query(Advisory)
            .filter(Advisory.severity.is_(None))
            .count()
        )

        print("=" * 60)
        print("OSV ADVISORY DATA QUALITY CHECK")
        print("=" * 60)
        print(f"Total advisory rows:                {total_advisories}")
        print(f"Rows with published_at = NULL:      {null_published}")
        print(f"Rows with severity = NULL:           {null_severity}")
        print("=" * 60)

        if null_published:
            print(
                "\nscoring's build_stats.py already tolerates this (skips "
                "rows with no published_at, logs a one-line notice per "
                "package) -- so scoring won't crash either way. Worth "
                "checking with B whether these specific rows genuinely "
                "had no 'published' field in OSV's response, or whether "
                "osv.py's save_advisories() is losing a real date on "
                "insert -- same category of bug as the dependency-edges "
                "duplicate-key issue found in Phase 2, just unconfirmed "
                "here rather than reproduced."
            )
        else:
            print(
                "\nNo NULL published_at rows found -- OSV's dates are "
                "parsing and storing cleanly. No action needed on this "
                "front."
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()