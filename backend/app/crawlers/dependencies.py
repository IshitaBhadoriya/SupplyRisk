import httpx
from packaging.requirements import Requirement, InvalidRequirement

from app.database import SessionLocal
from app.models import Package, DependencyEdge


NPM_API_URL = "https://registry.npmjs.org"
PYPI_API_URL = "https://pypi.org/pypi"


def get_dependencies(registry: str, package_name: str) -> list[str]:
    """Fetch direct dependencies for one npm or PyPI package."""

    if registry == "npm":
        url = f"{NPM_API_URL}/{package_name}"
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()

        data = response.json()

        latest_version = data.get("dist-tags", {}).get("latest")

        if not latest_version:
            return []

        version_data = data.get("versions", {}).get(
            latest_version,
            {},
        )

        dependencies = version_data.get("dependencies", {})

        return list(dependencies.keys())

    if registry == "pypi":
        url = f"{PYPI_API_URL}/{package_name}/json"
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()

        data = response.json()

        requires_dist = (
            data.get("info", {}).get("requires_dist") or []
        )

        dependencies = []

        for requirement in requires_dist:
            try:
                dependency_name = Requirement(requirement).name
            except InvalidRequirement:
                continue

            if dependency_name:
                dependencies.append(dependency_name)

        return dependencies

    raise ValueError(f"Unsupported registry: {registry}")


def normalize_package_name(registry: str, name: str) -> str:
    """Normalize package names for database matching."""

    name = name.strip()

    if registry == "pypi":
        return name.lower().replace("_", "-").replace(".", "-")

    return name.lower()


def find_package(db, registry: str, name: str):
    """Find an existing package using normalized package names."""

    normalized_name = normalize_package_name(registry, name)

    packages = (
        db.query(Package)
        .filter(Package.registry == registry)
        .all()
    )

    for package in packages:
        if normalize_package_name(registry, package.name) == normalized_name:
            return package

    return None


def save_dependency_edges(
    package_id: int,
    dependency_names: list[str],
    registry: str,
) -> int:
    """Save dependency relationships that exist in the database."""

    db = SessionLocal()

    try:
        package = db.query(Package).filter(
            Package.id == package_id
        ).first()

        if package is None:
            raise ValueError(f"Package ID not found: {package_id}")

        saved = 0
        skipped = 0
        resolved_dependency_ids = set()

        for dependency_name in dependency_names:
            dependency = find_package(
                db,
                registry,
                dependency_name,
            )

            if dependency is None:
                skipped += 1
                continue

            if dependency.id == package_id:
                skipped += 1
                continue
            if dependency.id in resolved_dependency_ids:
                skipped += 1
                continue
            existing = (
                db.query(DependencyEdge)
                .filter(
                    DependencyEdge.package_id == package_id,
                    DependencyEdge.depends_on_package_id == dependency.id,
                )
                .first()
            )

            if existing:
                skipped += 1
                continue

            edge = DependencyEdge(
                package_id=package_id,
                depends_on_package_id=dependency.id,
            )

            db.add(edge)
            resolved_dependency_ids.add(dependency.id)
            saved += 1

        db.commit()

        return saved

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def crawl_dependencies(package: Package) -> int:
    """Fetch and store direct dependencies for one package."""

    dependencies = get_dependencies(
        package.registry,
        package.name,
    )

    saved = save_dependency_edges(
        package.id,
        dependencies,
        package.registry,
    )

    print(
        f"[DEPENDENCY] {package.registry}/{package.name}: "
        f"{len(dependencies)} dependencies found, "
        f"{saved} edges saved"
    )

    return saved


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print(
            "Usage: python -m app.crawlers.dependencies "
            "<registry> <package>"
        )
        raise SystemExit(1)

    registry = sys.argv[1]
    package_name = sys.argv[2]

    db = SessionLocal()

    try:
        package = (
            db.query(Package)
            .filter(
                Package.registry == registry,
                Package.name == package_name,
            )
            .first()
        )

        if package is None:
            raise ValueError(
                f"Package not found: {registry}/{package_name}"
            )

        package_id = package.id

    finally:
        db.close()

    db = SessionLocal()

    try:
        package = db.query(Package).filter(
            Package.id == package_id
        ).first()

        crawl_dependencies(package)

    finally:
        db.close()