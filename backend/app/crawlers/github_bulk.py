import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

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
            failures = json.loads(
                FAILED_REPOSITORIES_LOG.read_text()
            )
        except json.JSONDecodeError:
            failures = []
    else:
        failures = []

    failures.append(
        {
            "repository": f"{owner}/{repository}",
            "error": str(error),
            "timestamp": datetime.now().isoformat(),
        }
    )

    FAILED_REPOSITORIES_LOG.write_text(
        json.dumps(failures, indent=2)
    )

from app.crawlers.github import (
    get_all_commits,
    save_contributors,
    summarize_contributors,
    map_to_contributor_rows,
)
from app.crawlers.utils import parse_github_url
from app.database import SessionLocal
from app.models import Package


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
    """
    Group packages by unique GitHub repository.

    One GitHub repository may belong to multiple registry packages.
    """
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


def crawl_repository(owner: str, repository: str, packages: list[Package]):
    """Crawl one repository and save contributors for all linked packages."""
    print("\n" + "-" * 60)
    print(f"Repository: {owner}/{repository}")
    print(
        f"Linked packages: "
        f"{len(packages)}"
    )

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


def bulk_github_ingestion() -> None:
    """Crawl each unique GitHub repository once, then retry failures."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if FAILED_REPOSITORIES_LOG.exists():
        FAILED_REPOSITORIES_LOG.unlink()
    FAILED_REPOSITORIES_LOG.write_text("[]")
    print("=" * 60)
    print("SUPPLYRISK BULK GITHUB INGESTION")
    print("=" * 60)

    packages = get_github_packages()

    print(f"Packages with GitHub URLs: {len(packages)}")

    repositories = build_repository_groups(packages)

    print(f"Unique GitHub repositories: {len(repositories)}")

    successful = 0
    failed = 0
    failed_repositories = []

    # First pass
    for (owner, repository), linked_packages in repositories.items():
        try:
            crawl_repository(
                owner,
                repository,
                linked_packages,
            )
            successful += 1

        except Exception as exc:
            failed += 1
            failed_repositories.append(
                (owner, repository, linked_packages)
            )

            save_failed_repository(
                owner,
                repository,
                str(exc),
            )

            print(
                f"[ERROR] {owner}/{repository}: {exc}"
            )

    # Retry failed repositories once
    if failed_repositories:
        print("\n" + "=" * 60)
        print(
            f"RETRYING {len(failed_repositories)} FAILED REPOSITORIES"
        )
        print("=" * 60)

        print("\nWaiting 60 seconds before retrying failed repositories...")
        time.sleep(60)
        retry_failed = 0

        for owner, repository, linked_packages in failed_repositories:
            try:
                print(
                    f"\n[RETRY] {owner}/{repository}"
                )

                crawl_repository(
                    owner,
                    repository,
                    linked_packages,
                )

                successful += 1
                failed -= 1

            except Exception as exc:
                retry_failed += 1

                print(
                    f"[RETRY FAILED] "
                    f"{owner}/{repository}: {exc}"
                )

        print(
            f"\nRetry complete: "
            f"{len(failed_repositories) - retry_failed} succeeded, "
            f"{retry_failed} still failed."
        )

    print("\n" + "=" * 60)
    print("BULK GITHUB INGESTION SUMMARY")
    print("=" * 60)
    print(f"Packages discovered:     {len(packages)}")
    print(f"Unique repositories:      {len(repositories)}")
    print(f"Repositories successful:  {successful}")
    print(f"Repositories failed:      {failed}")
    print("=" * 60)

if __name__ == "__main__":
    bulk_github_ingestion()
