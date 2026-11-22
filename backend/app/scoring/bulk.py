
from app.database import SessionLocal
from app.models import Package

from app.scoring.build_stats import build_stats_for_package
from app.scoring.formula import compute_score
from app.scoring.write_score import write_score_history


def bulk_score_all_packages():
    session = SessionLocal()

    successful = 0
    skipped = 0
    failed = 0
    errors = []

    try:
        packages = (
            session.query(Package)
            .filter(Package.registry.in_(["npm", "pypi"]))
            .order_by(Package.id)
            .all()
        )

        total = len(packages)

        print(f"Starting bulk scoring for {total} packages")

        for index, package in enumerate(packages, start=1):
            try:
                stats = build_stats_for_package(
                    session, package
                )

                result = compute_score(stats)

                saved = write_score_history(
                    session,
                    package.id,
                    result
                )

                if not saved:
                    skipped += 1

                    print(
                        f"[SKIPPED] {index}/{total} "
                        f"{package.registry}/{package.name} "
                        f"Coverage: "
                        f"{result.breakdown['data_coverage_pct']}%"
                    )
                    continue

                successful += 1

                print(
                    f"[SUCCESS] {index}/{total} "
                    f"{package.registry}/{package.name} "
                    f"Score: {result.score}/100 "
                    f"Coverage: "
                    f"{result.breakdown['data_coverage_pct']}%"
                )

            except Exception as exc:
                session.rollback()
                failed += 1

                message = (
                    f"{package.registry}/{package.name}: {exc}"
                )
                errors.append(message)

                print(f"[FAILED] {message}")

        summary = {
            "total_packages": total,
            "successful_packages": successful,
            "skipped_packages": skipped,
            "failed_packages": failed,
            "errors": errors,
        }

        print("\nBULK SCORING COMPLETE")
        print(summary)

        return summary

    finally:
        session.close()
