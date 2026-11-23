
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.crawlers.github import (
    get_all_commits,
    save_contributors,
    summarize_contributors,
    map_to_contributor_rows,
)
from app.crawlers.utils import parse_github_url
from app.database import SessionLocal
from app.models import Package
from app.services.ingestion_status import (
    mark_running,
    mark_success,
    mark_failed,
)


LOG_DIR = Path("/app/logs")
FAILED_REPOSITORIES_LOG = LOG_DIR / "github_failed_repositories.json"


def save_failed_repository(
    owner: str,
    repository: str,
    error: str,
) -> None:
    """Persist a failed GitHub repository for later inspection."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if FAILED_REPOSITORIES_LOG.exists():
        try:
            failures = json.loads(FAILED_REPOSITORIES_LOG.read_text())
        except json.JSONDecodeError:
            failures = []
    else:
        failures = []

    failures.append({
        "repository": f"{owner}/{repository}",
        "error": str(error),
        "timestamp": datetime.now().isoformat(),
    })

    FAILED_REPOSITORIES_LOG.write_text(
        json.dumps(failures, indent=2)
    )


def get_github_packages() -> list[Package]:
    """Return packages that have a GitHub repository URL."""
    db = SessionLocal()

    try:
        return (
            db.query(Package)
            .filter(Package.repo_url.ilike("%github.com%"))
            .order_by(Package.id)
            .all()
        )
    finally:
        db.close()


def build_repository_groups(packages: list[Package]) -> dict:
    """Group packages by unique GitHub repository."""
    repositories = defaultdict(list)

    for package in packages:
        parsed = parse_github_url(package.repo_url)

        if parsed is None:
            print(
                f"[SKIP] Invalid GitHub URL: "
                f"{package.registry}/{package.name}"
            )
            continue

        owner, repository = parsed
        key = (owner.lower(), repository.lower())
        repositories[key].append(package)

    return dict(repositories)


def update_packages_running(
    packages: list[Package],
) -> list[str]:
    """Mark packages as running and collect status-update errors."""
    errors = []

    for package in packages:
        try:
            mark_running(package.id, "github")
        except Exception as exc:
            message = (
                f"{package.registry}/{package.name}: "
                f"could not mark running: {exc}"
            )
            errors.append(message)
            print(f"[STATUS ERROR] {message}")

    return errors


def update_packages_success(
    packages: list[Package],
    records_found: int,
) -> list[str]:
    """Mark packages as successful and collect status-update errors."""
    errors = []

    for package in packages:
        try:
            mark_success(
                package.id,
                "github",
                records_found,
            )
        except Exception as exc:
            message = (
                f"{package.registry}/{package.name}: "
                f"could not mark successful: {exc}"
            )
            errors.append(message)
            print(f"[STATUS ERROR] {message}")

    return errors


def update_packages_failed(
    packages: list[Package],
    error: str,
) -> list[str]:
    """Mark packages as failed and collect status-update errors."""
    errors = []

    for package in packages:
        try:
            mark_failed(
                package.id,
                "github",
                error,
            )
        except Exception as exc:
            message = (
                f"{package.registry}/{package.name}: "
                f"could not mark failed: {exc}"
            )
            errors.append(message)
            print(f"[STATUS ERROR] {message}")

    return errors


def crawl_repository(
    owner: str,
    repository: str,
    packages: list[Package],
) -> int:
    """Crawl one repository and save contributors for linked packages."""
    print("\n" + "-" * 60)
    print(f"Repository: {owner}/{repository}")
    print(f"Linked packages: {len(packages)}")
    freshness_cutoff = datetime.now() - timedelta(hours=GITHUB_CRAWL_FRESHNESS_HOURS)

    if packages and all(
        package.last_crawled_at is not None
        and package.last_crawled_at >= freshness_cutoff
        for package in packages
    ):
        print(f"[SKIP] Repository crawled within the last {GITHUB_CRAWL_FRESHNESS_HOURS} hours.")
        return 0
    commits = get_all_commits(
        owner,
        repository,
        max_pages=50,
    )

    contributor_data = summarize_contributors(commits)

    print(
        f"Found {len(contributor_data)} contributors "
        f"from {len(commits)} commits"
    )

    for package in packages:
        rows = map_to_contributor_rows(
            contributor_data,
            package_id=package.id,
        )

        save_contributors(
            package_id=package.id,
            rows=rows,
        )

        print(
            f"Saved contributors for "
            f"{package.registry}/{package.name} "
            f"(package_id={package.id})"
        )

    return len(contributor_data)


def bulk_github_ingestion() -> dict:
    """Crawl repositories, track statuses, retry failures and return summary."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    FAILED_REPOSITORIES_LOG.write_text("[]")

    print("=" * 60)
    print("SUPPLYRISK BULK GITHUB INGESTION")
    print("=" * 60)

    packages = get_github_packages()
    repositories = build_repository_groups(packages)

    print(f"Packages discovered: {len(packages)}")
    print(f"Unique repositories: {len(repositories)}")

    grouped_package_ids = {
        package.id
        for linked_packages in repositories.values()
        for package in linked_packages
    }

    skipped_packages = len(packages) - len(grouped_package_ids)

    successful_package_ids = set()
    failed_package_ids = set()
    successful_repository_keys = set()

    status_update_errors = []
    failed_repositories = []
    retry_failed_repositories = []

    # First attempt
    for (owner, repository), linked_packages in repositories.items():
        key = (owner, repository)

        status_update_errors.extend(
            update_packages_running(linked_packages)
        )

        try:
            records_found = crawl_repository(
                owner,
                repository,
                linked_packages,
            )

            successful_package_ids.update(
                package.id for package in linked_packages
            )
            successful_repository_keys.add(key)

            status_update_errors.extend(
                update_packages_success(
                    linked_packages,
                    records_found,
                )
            )

        except Exception as exc:
            print(f"[ERROR] {owner}/{repository}: {exc}")

            status_update_errors.extend(
                update_packages_failed(
                    linked_packages,
                    str(exc),
                )
            )

            failed_repositories.append(
                (owner, repository, linked_packages, str(exc))
            )

            save_failed_repository(
                owner,
                repository,
                str(exc),
            )

    # Retry failed repositories once
    if failed_repositories:
        print("\n" + "=" * 60)
        print(
            f"RETRYING {len(failed_repositories)} FAILED REPOSITORIES"
        )
        print("=" * 60)

        print("Waiting 60 seconds before retrying...")
        time.sleep(60)

        for owner, repository, linked_packages, previous_error in failed_repositories:
            key = (owner, repository)

            print(f"\n[RETRY] {owner}/{repository}")

            status_update_errors.extend(
                update_packages_running(linked_packages)
            )

            try:
                records_found = crawl_repository(
                    owner,
                    repository,
                    linked_packages,
                )

                successful_package_ids.update(
                    package.id for package in linked_packages
                )
                successful_repository_keys.add(key)

                status_update_errors.extend(
                    update_packages_success(
                        linked_packages,
                        records_found,
                    )
                )

                print(f"[RETRY SUCCESS] {owner}/{repository}")

            except Exception as exc:
                print(
                    f"[RETRY FAILED] {owner}/{repository}: {exc}"
                )

                status_update_errors.extend(
                    update_packages_failed(
                        linked_packages,
                        str(exc),
                    )
                )

                retry_failed_repositories.append(
                    (owner, repository, linked_packages)
                )

                save_failed_repository(
                    owner,
                    repository,
                    str(exc),
                )

    # Calculate final failed packages after all retries
    for _, _, linked_packages in retry_failed_repositories:
        failed_package_ids.update(
            package.id for package in linked_packages
        )

    successful_repositories = len(successful_repository_keys)
    failed_repository_count = (
        len(repositories) - successful_repositories
    )

    summary = {
        "packages_discovered": len(packages),
        "packages_skipped_invalid_url": skipped_packages,
        "repositories_discovered": len(repositories),
        "successful_repositories": successful_repositories,
        "failed_repositories": failed_repository_count,
        "successful_packages": len(successful_package_ids),
        "failed_packages": len(failed_package_ids),
        "status_update_errors": len(status_update_errors),
    }

    print("\n" + "=" * 60)
    print("BULK GITHUB INGESTION SUMMARY")
    print("=" * 60)

    for key, value in summary.items():
        print(f"{key.replace('_', ' ').title()}: {value}")

    print("=" * 60)

    return summary


if __name__ == "__main__":
    bulk_github_ingestion()
