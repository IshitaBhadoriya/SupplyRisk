from app.database import SessionLocal
from app.models import Package
from urllib.parse import urlparse

def get_or_create_package(
    registry: str,
    name: str,
    repo_url: str | None = None,
) -> int:
    """
    Get an existing package or create a new package record.

    The database enforces uniqueness for registry + package name.
    """

    db = SessionLocal()

    try:
        package = (
            db.query(Package)
            .filter_by(registry=registry, name=name)
            .first()
        )

        if package:
            # Update the repository URL when newer metadata provides one.
            if repo_url and package.repo_url != repo_url:
                package.repo_url = repo_url
                db.commit()

            print(
                f"Found existing package: "
                f"{registry}/{name} (id={package.id})"
            )

            return package.id

        package = Package(
            registry=registry,
            name=name,
            repo_url=repo_url,
        )

        db.add(package)
        db.commit()
        db.refresh(package)

        print(
            f"Created package: "
            f"{registry}/{name} (id={package.id})"
        )

        return package.id

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

def parse_github_url(repo_url: str) -> tuple[str, str] | None:
    """
    Extract GitHub owner and repository name from common GitHub URL formats.
    """
    if not repo_url:
        return None

    try:
        url = repo_url.strip()

        # SCP-style:
        # git@github.com:owner/repository.git
        if url.startswith("git@github.com:"):
            path = url[len("git@github.com:"):]

        else:
            # Remove git+ prefix
            if url.startswith("git+"):
                url = url[4:]

            # Handle git+ssh://git@github.com/owner/repository
            if url.startswith("ssh://git@github.com/"):
                path = url[len("ssh://git@github.com/"):]

            else:
                parsed = urlparse(url)

                if parsed.netloc.lower() not in {
                    "github.com",
                    "www.github.com",
                }:
                    return None

                path = parsed.path

        parts = [
            part.strip()
            for part in path.strip("/").split("/")
            if part.strip()
        ]

        if len(parts) < 2:
            return None

        owner = parts[0]
        repository = parts[1]

        if repository.endswith(".git"):
            repository = repository[:-4]

        if not owner or not repository:
            return None

        return owner, repository

    except (ValueError, AttributeError):
        return None