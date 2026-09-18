import json
import urllib.request
import urllib.parse

from app.crawlers.utils import get_or_create_package


NPM_REGISTRY_URL = "https://registry.npmjs.org"


def get_npm_package(name: str) -> dict:
    """Fetch package metadata from the npm registry."""
    encoded_name = urllib.parse.quote(name, safe="@/")
    url = f"{NPM_REGISTRY_URL}/{encoded_name}"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "SupplyRisk-Crawler",
        },
        method="GET",
    )

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_repository_url(metadata: dict) -> str | None:
    """Extract a usable repository URL from npm metadata."""
    repository = metadata.get("repository")

    if isinstance(repository, dict):
        url = repository.get("url")
    elif isinstance(repository, str):
        url = repository
    else:
        url = None

    if not url:
        return None

    url = url.strip()

    if url.startswith("git+https://github.com/"):
        url = url[4:]
    elif url.startswith("git://github.com/"):
        url = "https://" + url[len("git://"):]
    elif url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]

    if url.endswith(".git"):
        url = url[:-4]

    return url


def crawl_npm_package(name: str) -> int:
    """Fetch one npm package and save it to the packages table."""
    print(f"Fetching npm package: {name}")

    metadata = get_npm_package(name)

    package_name = metadata.get("name", name)
    repo_url = extract_repository_url(metadata)

    print(f"Package name: {package_name}")
    print(f"Repository: {repo_url}")

    package_id = get_or_create_package(
        registry="npm",
        name=package_name,
        repo_url=repo_url,
    )

    print(f"Saved npm package with id={package_id}")

    return package_id


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m app.crawlers.npm <package-name>")
        print("Example: python -m app.crawlers.npm express")
        raise SystemExit(1)

    package_name = sys.argv[1]

    crawl_npm_package(package_name)