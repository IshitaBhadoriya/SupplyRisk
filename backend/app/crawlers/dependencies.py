
import httpx

from urllib.parse import quote
from packaging.requirements import Requirement, InvalidRequirement
from packaging.utils import canonicalize_name

from app.database import SessionLocal
from app.models import Package, DependencyEdge


NPM_API_URL = "https://registry.npmjs.org"
PYPI_API_URL = "https://pypi.org/pypi"

def normalize_package_name(registry: str, name: str) -> str:
    """Normalize package names for database matching."""

    name = name.strip()

    if registry == "pypi":
        return str(canonicalize_name(name))

    return name.lower()


def get_dependencies(registry: str, package_name: str) -> list[str]:
    """Fetch direct dependencies for npm or PyPI packages."""

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:

        if registry == "npm":

            # Encode scoped package names correctly.
            # Example: @jest/react-is -> @jest%2Freact-is
            encoded_name = quote(package_name, safe="@")

            url = f"{NPM_API_URL}/{encoded_name}"

            response = client.get(url)
            response.raise_for_status()

            data = response.json()

            latest_version = (
                data.get("dist-tags", {}).get("latest")
            )

            if not latest_version:
                return []

            version_data = (
                data.get("versions", {}).get(latest_version, {})
            )

            dependencies = (
                version_data.get("dependencies") or {}
            )

            return list(dependencies.keys())

        elif registry == "pypi":

            url = f"{PYPI_API_URL}/{quote(package_name, safe='')}/json"

            response = client.get(url)
            response.raise_for_status()

            data = response.json()

            requires_dist = (
                data.get("info", {}).get("requires_dist") or []
            )

            dependencies = []

            for requirement_string in requires_dist:

                try:
                    requirement = Requirement(requirement_string)

                except InvalidRequirement:
                    continue

                # Exclude optional extras and evaluate
                # environment markers for this environment.
                if requirement.marker is not None:
                    if not requirement.marker.evaluate():
                        continue

                dependencies.append(requirement.name)

            return list(dict.fromkeys(dependencies))

        else:
            raise ValueError(
                f"Unsupported registry: {registry}"
            )


def build_package_lookup(db, registry: str) -> dict:
    """Build a normalized package lookup map."""

    packages = (
        db.query(Package)
        .filter(Package.registry == registry)
        .all()
    )

    lookup = {}

    for package in packages:

        normalized_name = normalize_package_name(
            registry,
            package.name
        )

        lookup[normalized_name] = package

    return lookup


def find_package(
    package_lookup: dict,
    registry: str,
    name: str
):
    """Find an existing package using normalized names."""

    normalized_name = normalize_package_name(
        registry,
        name
    )

    return package_lookup.get(normalized_name)


def save_dependency_edges(
    package_id: int,
    dependency_names: list[str],
    registry: str
) -> dict:
    """
    Discover missing packages and synchronize dependency edges.

    Existing edges are replaced only after dependency fetching
    has completed successfully.
    """

    db = SessionLocal()

    try:

        package = (
            db.query(Package)
            .filter(Package.id == package_id)
            .first()
        )

        if package is None:
            raise ValueError(
                f"Package ID not found: {package_id}"
            )

        package_lookup = build_package_lookup(
            db,
            registry
        )

        dependency_ids = set()
        discovered = 0

        parent_name = normalize_package_name(
            registry,
            package.name
        )

        for dependency_name in dependency_names:

            normalized_name = normalize_package_name(
                registry,
                dependency_name
            )

            # Prevent self-dependencies.
            if normalized_name == parent_name:
                continue

            dependency = package_lookup.get(normalized_name)

            # Automatically discover missing packages.
            if dependency is None:

                dependency = Package(
                    registry=registry,
                    name=dependency_name
                )

                db.add(dependency)
                db.flush()

                package_lookup[normalized_name] = dependency

                discovered += 1

            dependency_ids.add(dependency.id)

        # Remove old edges only after successful fetching
        # and package resolution.
        (
            db.query(DependencyEdge)
            .filter(
                DependencyEdge.package_id == package_id
            )
            .delete(synchronize_session=False)
        )

        # Insert current dependency relationships.
        for dependency_id in dependency_ids:

            db.add(
                DependencyEdge(
                    package_id=package_id,
                    depends_on_package_id=dependency_id
                )
            )

        db.commit()

        result = {
            "dependencies_found": len(dependency_names),
            "edges_saved": len(dependency_ids),
            "packages_discovered": discovered
        }

        print(
            f"[DEPENDENCY] Package ID {package_id}: "
            f"{result['dependencies_found']} dependencies found, "
            f"{result['edges_saved']} edges saved, "
            f"{result['packages_discovered']} packages discovered"
        )

        return result

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()