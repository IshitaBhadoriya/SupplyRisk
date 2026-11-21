import os
import json
import urllib.request
import time
from datetime import datetime
from app.models import Contributor
from app.database import SessionLocal
from app.models import Package

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


def github_graphql(query: str):
    """Send a GraphQL query to GitHub with retry handling."""

    token = os.getenv("GITHUB_TOKEN")

    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")

    request = urllib.request.Request(
        GITHUB_GRAPHQL_URL,
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "SupplyRisk-Crawler",
        },
        method="POST",
    )

    max_retries = 3

    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                remaining = response.headers.get("X-RateLimit-Remaining")
                reset_at = response.headers.get("X-RateLimit-Reset")
                result = json.loads(response.read().decode("utf-8"))

            if remaining is not None and int(remaining) == 0:
                wait_seconds = max(
                    0,
                    int(reset_at) - int(time.time())
                ) if reset_at else 60

                print(
                    f"GitHub rate limit reached. "
                    f"Waiting {wait_seconds} seconds until reset."
                )

                time.sleep(wait_seconds)
                continue

            if "errors" in result:
                raise RuntimeError(
                    f"GitHub GraphQL error: {result['errors']}"
                )

            return result["data"]

        except Exception as exc:
            if attempt == max_retries:
                raise

            print(
                f"GitHub request failed "
                f"(attempt {attempt}/{max_retries}): {exc}"
            )

            time.sleep(2 ** attempt)


def get_repository(owner: str, name: str):
    """Fetch basic information about one GitHub repository."""

    query = f"""
    {{
      repository(owner: "{owner}", name: "{name}") {{
        nameWithOwner
        name
        description
        stargazerCount
        forkCount
        defaultBranchRef {{
          name
        }}
      }}
    }}
    """

    data = github_graphql(query)

    return data["repository"]


def get_contributors_page(owner: str, name: str, first: int = 100, after: str = None):
    """Fetch one page of commit history (used to derive contributors)."""

    after_clause = f', after: "{after}"' if after else ""

    query = f"""
    {{
      repository(owner: "{owner}", name: "{name}") {{
        defaultBranchRef {{
          target {{
            ... on Commit {{
              history(first: {first}{after_clause}) {{
                pageInfo {{
                  hasNextPage
                  endCursor
                }}
                nodes {{
                  committedDate
                  author {{
                    name
                    email
                    user {{
                      login
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """

    data = github_graphql(query)
    return data["repository"]["defaultBranchRef"]["target"]["history"]

def get_all_commits(owner: str, name: str, max_pages: int = 50):
    """Paginate through commit history and return all commit nodes."""

    all_commits = []
    after = None
    page_num = 0

    while True:
        page_num += 1
        history = get_contributors_page(owner, name, first=100, after=after)
        all_commits.extend(history["nodes"])

        print(f"Fetched page {page_num} — total commits so far: {len(all_commits)}")

        if not history["pageInfo"]["hasNextPage"]:
            break

        after = history["pageInfo"]["endCursor"]

        if page_num >= max_pages:
            print(f"Reached max_pages limit ({max_pages}), stopping early.")
            break

    return all_commits
def summarize_contributors(commits: list) -> dict:
    """Aggregate raw commit nodes into per-contributor stats."""

    contributors = {}

    for commit in commits:
        author = commit["author"]
        login = author["user"]["login"] if author["user"] else None
        key = login if login else f"email:{author['email']}"
        date = commit["committedDate"]

        if key not in contributors:
            contributors[key] = {
                "login": login,
                "name": author["name"],
                "email": author["email"],
                "commit_count": 0,
                "first_commit_at": date,
                "last_commit_at": date,
            }

        stats = contributors[key]
        stats["commit_count"] += 1
        if date < stats["first_commit_at"]:
            stats["first_commit_at"] = date
        if date > stats["last_commit_at"]:
            stats["last_commit_at"] = date

    return contributors
def map_to_contributor_rows(contributors: dict, package_id: int) -> list[dict]:
    """Convert summarized contributor stats into rows matching the Contributor model."""

    rows = []

    for c in contributors.values():
        username = c["login"] if c["login"] else (c["name"] or c["email"] or "unknown")

        rows.append({
            "package_id": package_id,
            "username": username,
            "commit_count": c["commit_count"],
            "first_commit_at": datetime.fromisoformat(c["first_commit_at"].replace("Z", "+00:00")),
            "last_commit_at": datetime.fromisoformat(c["last_commit_at"].replace("Z", "+00:00")),
        })

    return rows
def get_or_create_package(registry: str, name: str, repo_url: str = None) -> int:
    """Return the id of the package row, creating it if it doesn't exist."""

    db = SessionLocal()
    try:
        package = db.query(Package).filter_by(registry=registry, name=name).first()

        if package:
            print(f"Found existing package: id={package.id}")
            return package.id

        package = Package(registry=registry, name=name, repo_url=repo_url)
        db.add(package)
        db.commit()
        db.refresh(package)

        print(f"Created new package: id={package.id}")
        return package.id
    finally:
        db.close()

def save_contributors(package_id: int, rows: list[dict]):
    """Replace existing contributor rows for this package with fresh data."""
    db = SessionLocal()
    try:
        deleted = db.query(Contributor).filter_by(package_id=package_id).delete()
        print(f"Deleted {deleted} existing contributor rows for package_id={package_id}")

        for row in rows:
            db.add(Contributor(**row))

        db.commit()
        print(f"Inserted {len(rows)} contributor rows for package_id={package_id}")
    finally:
        db.close()

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m app.crawlers.github <owner> <repo>")
        print("Example: python -m app.crawlers.github psf requests")
        raise SystemExit(1)

    owner = sys.argv[1]
    name = sys.argv[2]

    print(f"Starting GitHub crawl for: {owner}/{name}")

    commits = get_all_commits(owner, name, max_pages=50)

    contributors = summarize_contributors(commits)

    package_id = get_or_create_package(
        registry="github",
        name=f"{owner}/{name}",
        repo_url=f"https://github.com/{owner}/{name}",
    )

    rows = map_to_contributor_rows(
        contributors,
        package_id=package_id
    )

    print(
        f"\nMapped {len(rows)} contributor rows "
        f"using package_id={package_id}. Sample (first 3):"
    )

    for row in rows[:3]:
        print(row)

    save_contributors(package_id, rows)

    print(
        f"\nDone. {len(rows)} contributors saved "
        f"for package_id={package_id}."
    )
