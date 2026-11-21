import time

from app.database import SessionLocal
from app.models import Package
from app.crawlers.osv import crawl_osv_package


def get_packages():
    """Return all npm and PyPI packages from the database."""
    db = SessionLocal()

    try:
        return (
            db.query(Package)
            .filter(Package.registry.in_(["npm", "pypi"]))
            .order_by(Package.registry, Package.id)
            .all()
        )
    finally:
        db.close()


def bulk_osv_ingestion():
    """Fetch OSV advisories for all npm and PyPI packages."""
    packages = get_packages()

    total = len(packages)
    successful = 0
    failed = 0
    total_advisories = 0

    print("=" * 60)
    print("SupplyRisk - Bulk OSV Ingestion")
    print("=" * 60)
    print(f"Packages to process: {total}")
    print()

    for index, package in enumerate(packages, start=1):
        print(
            f"[{index}/{total}] "
            f"Processing {package.registry}/{package.name}"
        )

        try:
            saved = crawl_osv_package(
                package.registry,
                package.name,
            )

            successful += 1
            total_advisories += saved

        except Exception as exc:
            failed += 1

            print(
                f"[FAILED] {package.registry}/{package.name}: {exc}"
            )

        print(
            f"Progress: {index}/{total} | "
            f"Successful: {successful} | "
            f"Failed: {failed} | "
            f"Advisories saved: {total_advisories}"
        )

        print("-" * 60)

        # Small delay to avoid sending requests too rapidly.
        time.sleep(0.2)

    print()
    print("=" * 60)
    print("Bulk OSV Ingestion Complete")
    print("=" * 60)
    print(f"Total packages: {total}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total advisories saved: {total_advisories}")
    print("=" * 60)


if __name__ == "__main__":
    bulk_osv_ingestion()