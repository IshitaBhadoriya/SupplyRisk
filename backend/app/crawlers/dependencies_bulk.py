import time

from app.database import SessionLocal
from app.models import Package
from app.crawlers.dependencies import crawl_dependencies


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


def bulk_dependency_ingestion():
    """Fetch and store direct dependency edges for all packages."""
    packages = get_packages()

    total = len(packages)
    successful = 0
    failed = 0
    total_edges = 0

    print("=" * 60)
    print("SupplyRisk - Bulk Dependency Ingestion")
    print("=" * 60)
    print(f"Packages to process: {total}")
    print()

    for index, package in enumerate(packages, start=1):
        print(
            f"[{index}/{total}] "
            f"Processing {package.registry}/{package.name}"
        )

        try:
            saved = crawl_dependencies(package)

            successful += 1
            total_edges += saved

        except Exception as exc:
            failed += 1

            print(
                f"[FAILED] {package.registry}/{package.name}: {exc}"
            )

        print(
            f"Progress: {index}/{total} | "
            f"Successful: {successful} | "
            f"Failed: {failed} | "
            f"Edges saved: {total_edges}"
        )

        print("-" * 60)

        # Small delay between API requests.
        time.sleep(0.2)

    print()
    print("=" * 60)
    print("Bulk Dependency Ingestion Complete")
    print("=" * 60)
    print(f"Total packages: {total}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Dependency edges saved: {total_edges}")
    print("=" * 60)


if __name__ == "__main__":
    bulk_dependency_ingestion()