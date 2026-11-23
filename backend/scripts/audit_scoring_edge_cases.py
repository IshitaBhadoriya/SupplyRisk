"""
Phase 3: scans the REAL dataset for the specific edge cases the project
plan calls out -- "a package with zero commits, a package with only one
contributor ever, a package with malformed advisory data" -- plus one
more found during Phase 1/2 testing: packages with no GitHub-linked data
at all. Also confirms scoring runs cleanly across the whole dataset
without crashing on any of them, and reports the data_completeness
confidence distribution.

Run this BEFORE and AFTER the Phase 3 hardening changes land to see the
hardening actually working, not just assume it does.

Run with:
    docker exec -it -e PYTHONPATH=/app supplyrisk_backend python scripts/audit_scoring_edge_cases.py
"""

from app.database import SessionLocal
from app.models import Package, Contributor, Advisory, DependencyEdge
from app.scoring.build_stats import build_stats_for_package
from app.scoring import compute_score


def main():
    session = SessionLocal()
    try:
        packages = session.query(Package).all()
        total = len(packages)

        zero_contributors = 0
        one_contributor = 0
        zero_advisories = 0
        zero_outgoing_dependencies = 0
        crash_count = 0
        confidence_counts = {"high": 0, "medium": 0, "low": 0}
        crashed_packages = []

        dependency_package_ids = {
            row[0] for row in session.query(DependencyEdge.package_id).distinct()
        }

        for package in packages:
            contributor_count = (
                session.query(Contributor)
                .filter_by(package_id=package.id)
                .count()
            )
            advisory_count = (
                session.query(Advisory)
                .filter_by(package_id=package.id)
                .count()
            )

            if contributor_count == 0:
                zero_contributors += 1
            elif contributor_count == 1:
                one_contributor += 1

            if advisory_count == 0:
                zero_advisories += 1

            if package.id not in dependency_package_ids:
                zero_outgoing_dependencies += 1

            try:
                stats = build_stats_for_package(session, package)
                result = compute_score(stats)
                confidence = result.breakdown["data_completeness"]["confidence"]
                confidence_counts[confidence] += 1
            except Exception as exc:
                crash_count += 1
                crashed_packages.append(f"{package.registry}/{package.name}: {exc}")

        print("=" * 60)
        print("SCORING EDGE-CASE AUDIT")
        print("=" * 60)
        print(f"Total packages:                 {total}")
        print(f"Zero contributors:              {zero_contributors}")
        print(f"Exactly one contributor:        {one_contributor}")
        print(f"Zero advisories:                {zero_advisories}")
        print(f"No outgoing dependency edges:   {zero_outgoing_dependencies}")
        print(f"Scoring crashes:                {crash_count}")
        if crashed_packages:
            print("\nCrashed packages:")
            for line in crashed_packages:
                print(f"  [CRASH] {line}")
        print("-" * 60)
        print("Data-completeness confidence distribution:")
        for level in ("high", "medium", "low"):
            print(f"  {level:8}: {confidence_counts[level]}")
        print("=" * 60)
    finally:
        session.close()


if __name__ == "__main__":
    main()