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
    """
    Extract the repository URL from PyPI metadata.

    Three passes, most reliable first:

    1. Scan every project_urls VALUE for a github.com link, regardless of
       what the maintainer happened to label it (many modern packages use
       labels like "Homepage" or "Issue Tracker" for a GitHub link instead
       of "Repository"/"Source" -- matching on the label alone misses
       these entirely, which was the actual bug: urllib3, SQLAlchemy,
       celery, tensorflow, selenium, django-rest-framework, and others
       all had a real GitHub repo that this function failed to find).
       A value pointing at /issues, /pulls, etc. instead of the repo root
       is fine here -- parse_github_url() in utils.py only ever reads the
       first two path segments (owner, repo) and discards the rest.
    2. Fall back to the original label-keyword match, for the rare case
       of a non-GitHub forge (GitLab, etc.) under a clearly-labeled key.
    3. Fall back to home_page, same as before -- this is what was
       causing packages with a non-GitHub homepage (e.g. openpyxl, which
       is genuinely hosted on Heptapod, not GitHub) to resolve to that
       non-GitHub URL. That's correct behavior for those packages, not a
       bug -- a GitHub-only contributor crawler structurally can't get
       data for a project that isn't on GitHub at all.
    """
    info = metadata.get("info", {})
    project_urls = info.get("project_urls") or {}

    for url in project_urls.values():
        if url and "github.com" in url.lower():
            return url

    for key, url in project_urls.items():
        if url and any(
            keyword in key.lower()
            for keyword in ("github", "repository", "source", "code")
        ):
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