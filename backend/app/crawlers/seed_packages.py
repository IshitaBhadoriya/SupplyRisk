import json
import time
from pathlib import Path

from app.crawlers.npm import crawl_npm_package
from app.crawlers.pypi import crawl_pypi_package


SEED_DATA_FILE = Path(__file__).with_name("seed_data.json")


def load_seed_data() -> dict:

    """Load the package catalogue from seed_data.json."""

    if not SEED_DATA_FILE.exists():
        raise FileNotFoundError(
            f"Seed data file not found: {SEED_DATA_FILE}"
        )

    with SEED_DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Seed data must be a JSON object.")

    for registry in ("npm", "pypi"):
        if registry not in data:
            raise ValueError(
                f"Missing registry section: '{registry}'"
            )

        if not isinstance(data[registry], list):
            raise ValueError(
                f"'{registry}' must contain a list of package names."
            )

    return data

def validate_seed_data(data: dict) -> None:
    """
    Validate the package catalogue before ingestion.

    Checks registry structure, package names, empty values,
    and duplicate package entries.
    """

    for registry in ("npm", "pypi"):
        packages = data[registry]

        cleaned_packages = [
            package.strip()
            for package in packages
            if isinstance(package, str) and package.strip()
        ]

        if len(cleaned_packages) != len(packages):
            raise ValueError(
                f"{registry}: contains empty or invalid package names."
            )

        duplicates = {
            package
            for package in cleaned_packages
            if cleaned_packages.count(package) > 1
        }

        if duplicates:
            raise ValueError(
                f"{registry}: duplicate packages found: "
                f"{sorted(duplicates)}"
            )

    print("\nSeed data validation:")
    print("  ✓ Registry structure valid")
    print("  ✓ Package names valid")
    print("  ✓ No duplicate packages")

def crawl_registry_packages(
    registry: str,
    packages: list[str],
) -> dict:
    """
    Crawl packages from a registry independently.

    A failure for one package does not stop the remaining packages.
    """

    start_time = time.perf_counter()

    crawler = {
        "npm": crawl_npm_package,
        "pypi": crawl_pypi_package,
    }.get(registry)

    if crawler is None:
        raise ValueError(f"Unsupported registry: {registry}")

    successful = []
    failed = []

    for package_name in packages:
        package_name = package_name.strip()

        if not package_name:
            continue

        try:
            crawler(package_name)
            successful.append(package_name)

        except Exception as exc:
            failed.append({
                "package": package_name,
                "error": str(exc),
            })

            print(
                f"[ERROR] {registry}/{package_name}: {exc}"
            )

    elapsed = time.perf_counter() - start_time

    return {
        "registry": registry,
        "total": len(packages),
        "successful": successful,
        "failed": failed,
        "elapsed_seconds": round(elapsed, 2),
    }


def print_summary(results: list[dict]) -> None:
    """Print a clear ingestion summary."""

    print("\n" + "=" * 60)
    print("SUPPLYRISK INGESTION SUMMARY")
    print("=" * 60)

    total = 0
    successful = 0
    failed = 0

    for result in results:
        registry = result["registry"]
        registry_total = result["total"]
        registry_success = len(result["successful"])
        registry_failed = len(result["failed"])

        total += registry_total
        successful += registry_success
        failed += registry_failed

        print(f"\nRegistry: {registry}")
        print(f"  Total:      {registry_total}")
        print(f"  Successful: {registry_success}")
        print(f"  Failed:     {registry_failed}")
        print(f"  Time:       {result['elapsed_seconds']} seconds")

        if result["failed"]:
            print("  Failed packages:")

            for item in result["failed"]:
                print(
                    f"    - {item['package']}: "
                    f"{item['error']}"
                )

    print("\n" + "-" * 60)
    print(
        f"Overall: {successful}/{total} successful | "
        f"{failed} failed"
    )
    print("=" * 60)


def seed_packages() -> None:
    """Load and ingest the complete seed catalogue."""

    print("=" * 60)
    print("SUPPLYRISK PACKAGE INGESTION")
    print("=" * 60)

    seed_data = load_seed_data()

    validate_seed_data(seed_data)

    results = []

    for registry in ("npm", "pypi"):
        packages = seed_data[registry]

        print(
            f"\nStarting {registry} ingestion "
            f"({len(packages)} packages)..."
        )

        result = crawl_registry_packages(
            registry=registry,
            packages=packages,
        )

        results.append(result)

    print_summary(results)


if __name__ == "__main__":
    seed_packages()