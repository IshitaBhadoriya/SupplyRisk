
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from sqlalchemy import or_

from app.database import SessionLocal
from app.models import Package, IngestionStatus

from app.crawlers.dependencies import (
    get_dependencies,
    save_dependency_edges,
)

from app.services.ingestion_status import (
    mark_running,
    mark_success,
    mark_failed,
    mark_not_found,
)


MAX_PACKAGES_PER_RUN = 500
MAX_WORKERS = 5


def get_unprocessed_packages(limit=MAX_PACKAGES_PER_RUN):
    """Select packages that still need dependency ingestion."""

    db = SessionLocal()

    try:
        packages = (
            db.query(Package)
            .outerjoin(
                IngestionStatus,
                (
                    IngestionStatus.package_id == Package.id
                ) & (
                    IngestionStatus.source == "dependencies"
                )
            )
            .filter(
                Package.registry.in_(["npm", "pypi"]),
                or_(
                    IngestionStatus.id.is_(None),
                    IngestionStatus.status.notin_(
                        ["success", "not_found"]
                    )
                )
            )
            .order_by(Package.id)
            .limit(limit)
            .all()
        )

        return [
            {
                "id": package.id,
                "name": package.name,
                "registry": package.registry
            }
            for package in packages
        ]

    finally:
        db.close()


def fetch_package_dependencies(package):
    """Fetch remote dependency metadata."""

    return get_dependencies(
        package["registry"],
        package["name"]
    )


def bulk_dependency_ingestion():
    """Fetch dependencies concurrently and save them safely."""

    packages = get_unprocessed_packages()

    total = len(packages)
    successful = 0
    failed = 0
    not_found = 0

    total_edges = 0
    total_discovered = 0

    errors = []

    print("=" * 60)
    print("SUPPLYRISK - CONCURRENT DEPENDENCY INGESTION")
    print("=" * 60)

    print(f"Packages selected: {total}")
    print(f"Concurrent workers: {MAX_WORKERS}")

    if not packages:
        return {
            "packages_selected": 0,
            "successful_packages": 0,
            "failed_packages": 0,
            "not_found_packages": 0,
            "new_packages_discovered": 0,
            "dependency_edges_saved": 0,
            "remaining_unprocessed_packages": 0,
            "errors": []
        }

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

        futures = {}

        # Submit API requests concurrently.
        for package in packages:

            try:
                mark_running(
                    package["id"],
                    "dependencies"
                )

                future = executor.submit(
                    fetch_package_dependencies,
                    package
                )

                futures[future] = package

            except Exception as exc:

                failed += 1

                message = (
                    f"{package['registry']}/{package['name']}: {exc}"
                )

                errors.append(message)

                try:
                    mark_failed(
                        package["id"],
                        "dependencies",
                        str(exc)
                    )
                except Exception as status_error:
                    print(f"[STATUS ERROR] {status_error}")

        # Database writes happen sequentially here.
        for future in as_completed(futures):

            package = futures[future]
            package_id = package["id"]

            try:
                dependency_names = future.result()

                result = save_dependency_edges(
                    package_id,
                    dependency_names,
                    package["registry"]
                )

                mark_success(
                    package_id,
                    "dependencies",
                    result["edges_saved"]
                )

                successful += 1
                total_edges += result["edges_saved"]
                total_discovered += result["packages_discovered"]

                print(
                    f"[SUCCESS] {package['registry']}/{package['name']} "
                    f"| Edges: {result['edges_saved']} "
                    f"| Discovered: {result['packages_discovered']}"
                )

            except httpx.HTTPStatusError as exc:

                status_code = exc.response.status_code

                message = (
                    f"{package['registry']}/{package['name']}: "
                    f"HTTP {status_code}"
                )

                errors.append(message)

                if status_code == 404:

                    not_found += 1

                    try:
                        mark_not_found(
                            package_id,
                            "dependencies",
                            message
                        )

                        print(f"[NOT FOUND] {message}")

                    except Exception as status_error:
                        print(f"[STATUS ERROR] {status_error}")

                else:

                    failed += 1

                    try:
                        mark_failed(
                            package_id,
                            "dependencies",
                            str(exc)
                        )

                    except Exception as status_error:
                        print(f"[STATUS ERROR] {status_error}")

                    print(f"[FAILED] {message}")

            except Exception as exc:

                failed += 1

                message = (
                    f"{package['registry']}/{package['name']}: {exc}"
                )

                errors.append(message)

                try:
                    mark_failed(
                        package_id,
                        "dependencies",
                        str(exc)
                    )

                except Exception as status_error:
                    print(f"[STATUS ERROR] {status_error}")

                print(f"[FAILED] {message}")

    remaining = len(
        get_unprocessed_packages(limit=100000)
    )

    summary = {
        "packages_selected": total,
        "successful_packages": successful,
        "failed_packages": failed,
        "not_found_packages": not_found,
        "new_packages_discovered": total_discovered,
        "dependency_edges_saved": total_edges,
        "remaining_unprocessed_packages": remaining,
        "errors": errors
    }

    print("\n" + "=" * 60)
    print("DEPENDENCY INGESTION SUMMARY")
    print("=" * 60)

    for key, value in summary.items():
        print(f"{key}: {value}")

    return summary


if __name__ == "__main__":
    bulk_dependency_ingestion()
