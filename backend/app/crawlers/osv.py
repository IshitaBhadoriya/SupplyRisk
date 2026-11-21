import httpx

from app.database import SessionLocal
from app.models import Package, Advisory


OSV_API_URL = "https://api.osv.dev/v1/query"


def query_osv(package_name: str, ecosystem: str) -> list[dict]:
    """Query OSV for vulnerabilities affecting a package."""
    response = httpx.post(
        OSV_API_URL,
        json={
            "package": {
                "name": package_name,
                "ecosystem": ecosystem,
            }
        },
        timeout=30.0,
    )
    response.raise_for_status()

    data = response.json()
    return data.get("vulns", [])


def get_package(db, registry: str, name: str):
    return (
        db.query(Package)
        .filter(
            Package.registry == registry,
            Package.name == name,
        )
        .first()
    )


def extract_severity(vulnerability: dict) -> str | None:
    """Extract a qualitative severity from an OSV vulnerability."""
    database_specific = vulnerability.get("database_specific", {})

    severity = database_specific.get("severity")
    if severity:
        return str(severity).lower()

    severity_list = vulnerability.get("severity", [])

    if severity_list:
        severity_type = severity_list[0].get("type")
        if severity_type:
            return str(severity_type).lower()

    return None


def save_advisories(package_id: int, vulnerabilities: list[dict]) -> int:
    """Replace existing advisory rows for a package with fresh OSV data."""
    db = SessionLocal()

    try:
        db.query(Advisory).filter(
            Advisory.package_id == package_id
        ).delete(synchronize_session=False)

        saved = 0

        for vulnerability in vulnerabilities:
            published_at = vulnerability.get("published")

            advisory = Advisory(
                package_id=package_id,
                severity=extract_severity(vulnerability),
                published_at=published_at,
                patched_at=None,
            )

            db.add(advisory)
            saved += 1

        db.commit()
        return saved

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def crawl_osv_package(registry: str, name: str) -> int:
    """Fetch and store OSV advisories for one npm or PyPI package."""
    ecosystem_map = {
        "npm": "npm",
        "pypi": "PyPI",
    }

    ecosystem = ecosystem_map.get(registry)

    if ecosystem is None:
        raise ValueError(f"Unsupported registry: {registry}")

    db = SessionLocal()

    try:
        package = get_package(db, registry, name)

        if package is None:
            raise ValueError(
                f"Package not found in database: {registry}/{name}"
            )

        package_id = package.id

    finally:
        db.close()

    vulnerabilities = query_osv(name, ecosystem)

    saved = save_advisories(package_id, vulnerabilities)

    print(
        f"[OSV] {registry}/{name}: "
        f"{len(vulnerabilities)} vulnerabilities found, "
        f"{saved} advisory rows saved"
    )

    return saved


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python -m app.crawlers.osv <registry> <package>")
        raise SystemExit(1)

    crawl_osv_package(sys.argv[1], sys.argv[2])
