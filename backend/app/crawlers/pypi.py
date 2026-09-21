import json
import urllib.request

from app.crawlers.utils import get_or_create_package


PYPI_URL = "https://pypi.org/pypi"


def get_pypi_package(name: str) -> dict:
    """Fetch package metadata from the PyPI JSON API."""
    url = f"{PYPI_URL}/{name}/json"

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
    """Extract the repository URL from PyPI metadata."""
    info = metadata.get("info", {})

    project_urls = info.get("project_urls") or {}

    for key, url in project_urls.items():
        if "github" in key.lower() or "repository" in key.lower() or "source" in key.lower():
            if url:
                return url

    home_page = info.get("home_page")

    if home_page:
        return home_page

    return None


def crawl_pypi_package(name: str) -> int:
    """Fetch one PyPI package and save it to the packages table."""
    print(f"Fetching PyPI package: {name}")

    metadata = get_pypi_package(name)

    info = metadata.get("info", {})

    package_name = info.get("name", name)
    repo_url = extract_repository_url(metadata)

    print(f"Package name: {package_name}")
    print(f"Repository: {repo_url}")

    package_id = get_or_create_package(
        registry="pypi",
        name=package_name,
        repo_url=repo_url,
    )

    print(f"Saved PyPI package with id={package_id}")

    return package_id


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m app.crawlers.pypi <package-name>")
        print("Example: python -m app.crawlers.pypi requests")
        raise SystemExit(1)

    package_name = sys.argv[1]

    crawl_pypi_package(package_name)