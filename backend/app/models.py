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
    """One row per (package, time) risk score snapshot — this is what powers trend charts.

    Partitioned by month on scored_at (see the partition_score_history
    migration). Postgres requires any primary key on a partitioned table
    to include the partition key column, which is why scored_at is part
    of the primary key here alongside id, rather than id alone. This is
    additive, not breaking: nothing in the codebase looks up a
    ScoreHistory row by id alone — write_score_history() only ever
    inserts new rows."""

    __tablename__ = "score_history"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=False)
    scored_at = Column(DateTime, primary_key=True, default=datetime.utcnow, nullable=False)
    score = Column(Float, nullable=False)
    bus_factor = Column(Float, nullable=True)
    churn_rate = Column(Float, nullable=True)
    advisory_gap_days = Column(Integer, nullable=True)

    package = relationship("Package", back_populates="score_history")


class Contributor(Base):
    """Per-package contributor commit stats — used to compute bus factor / churn."""

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
    """Self-referencing edge table — package_id depends on depends_on_package_id."""
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
    """A team's tracked packages — advanced-scope feature, table included now
    so the schema doesn't need breaking changes later."""

    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, nullable=False)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)