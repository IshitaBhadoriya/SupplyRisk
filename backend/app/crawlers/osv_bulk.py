
import time

from app.database import SessionLocal
from app.models import Package
from app.crawlers.osv import crawl_osv_package
from app.services.ingestion_status import (
    mark_running,
    mark_success,
    mark_failed,
)


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
    """Fetch OSV advisories and track ingestion status per package."""
    packages = get_packages()

    total = len(packages)
    successful = 0
    failed = 0
    total_advisories = 0

    print("=" * 60)
    print("SUPPLYRISK - BULK OSV INGESTION")
    print("=" * 60)
    print(f"Packages to process: {total}")

    for index, package in enumerate(packages, start=1):
        print(
            f"[{index}/{total}] "
            f"Processing {package.registry}/{package.name}"
        )

        try:
            mark_running(package.id, "osv")

            saved = crawl_osv_package(
                package.registry,
                package.name,
            )

            mark_success(package.id, "osv", saved)

            successful += 1
            total_advisories += saved

            print(
                f"[SUCCESS] {package.registry}/{package.name}: "
                f"{saved} advisories saved"
            )

        except Exception as exc:
            failed += 1

            print(
                f"[FAILED] {package.registry}/{package.name}: {exc}"
            )

            try:
                mark_failed(package.id, "osv", str(exc))
            except Exception as status_error:
                print(
                    f"[STATUS UPDATE FAILED] {status_error}"
                )

        print(
            f"Progress: {index}/{total} | "
            f"Successful: {successful} | "
            f"Failed: {failed} | "
            f"Advisories saved: {total_advisories}"
        )

        print("-" * 60)
        time.sleep(0.2)

    print("\n" + "=" * 60)
    print("BULK OSV INGESTION COMPLETE")
    print("=" * 60)
    print(f"Total packages: {total}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total advisories saved: {total_advisories}")
    print("=" * 60)


if __name__ == "__main__":
    bulk_osv_ingestion()
