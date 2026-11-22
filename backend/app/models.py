from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Package(Base):
    """One row per tracked package (e.g. 'requests' on PyPI, 'lodash' on npm)."""

    __tablename__ = "packages"

    id = Column(Integer, primary_key=True)
    registry = Column(String, nullable=False)  # "npm" | "pypi" | "github"
    name = Column(String, nullable=False)
    repo_url = Column(String, nullable=True)
    current_score = Column(Float, nullable=True)
    last_scored_at = Column(DateTime, nullable=True)

    score_history = relationship("ScoreHistory", back_populates="package")
    contributors = relationship("Contributor", back_populates="package")
    advisories = relationship("Advisory", back_populates="package")

    __table_args__ = (UniqueConstraint("registry", "name", name="uq_registry_name"),)


class ScoreHistory(Base):
    """One row per (package, time) risk score snapshot â€” this is what powers trend charts."""

    __tablename__ = "score_history"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=False)
    scored_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    score = Column(Float, nullable=False)
    bus_factor = Column(Float, nullable=True)
    churn_rate = Column(Float, nullable=True)
    advisory_gap_days = Column(Integer, nullable=True)

    package = relationship("Package", back_populates="score_history")


class Contributor(Base):
    """Per-package contributor commit stats â€” used to compute bus factor / churn."""

    __tablename__ = "contributors"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=False)
    username = Column(String, nullable=False)
    commit_count = Column(Integer, default=0)
    first_commit_at = Column(DateTime, nullable=True)
    last_commit_at = Column(DateTime, nullable=True)

    package = relationship("Package", back_populates="contributors")


class Advisory(Base):
    """Known security advisories for a package, and how fast they were patched."""

    __tablename__ = "advisories"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=False)
    severity = Column(String, nullable=True)  # "low" | "medium" | "high" | "critical"
    published_at = Column(DateTime, nullable=True)
    patched_at = Column(DateTime, nullable=True)

    package = relationship("Package", back_populates="advisories")


class DependencyEdge(Base):
    """Self-referencing edge table â€” package_id depends on depends_on_package_id."""
    __tablename__ = "dependency_edges"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=False)
    depends_on_package_id = Column(Integer, ForeignKey("packages.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "package_id",
            "depends_on_package_id",
            name="uq_dependency_edge",
        ),
    )

class Watchlist(Base):
    """Packages saved by individual users."""

    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, nullable=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    package_id = Column(
        Integer,
        ForeignKey("packages.id"),
        nullable=False,
    )
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "package_id",
            name="uq_watchlist_user_package",
        ),
    )


class IngestionStatus(Base):
    """Tracks ingestion results for each package and data source."""

    __tablename__ = "ingestion_status"

    id = Column(Integer, primary_key=True)

    package_id = Column(
        Integer,
        ForeignKey("packages.id"),
        nullable=False,
    )

    source = Column(String, nullable=False)
    status = Column(
        String,
        nullable=False,
        default="pending",
    )

    last_attempt_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    last_success_at = Column(DateTime, nullable=True)

    records_found = Column(
        Integer,
        nullable=False,
        default=0,
    )

    error_message = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "package_id",
            "source",
            name="uq_ingestion_package_source",
        ),
    )

class User(Base):
    """Registered SupplyRisk users."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
