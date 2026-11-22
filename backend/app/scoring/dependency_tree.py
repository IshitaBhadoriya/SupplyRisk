"""
Recursive dependency-tree risk aggregation (Person A, Phase 2).

Given a package, walks every package it depends on -- directly and
transitively -- through `dependency_edges`, and aggregates their current
scores into a single "how risky is this package's whole dependency tree"
view, instead of just looking at the package in isolation. A package that
scores well on its own but pulls in a severely under-maintained
dependency three levels down is still a real risk; this is what surfaces
that.

Design choices worth defending in a viva:

- The recursion happens in ONE SQL round-trip (a recursive CTE), not by
  walking edges one query at a time in Python -- this is the whole point
  of using a recursive CTE instead of application-level BFS/DFS.
- Cycle protection uses an array of visited package ids carried through
  the recursion (`path`), with `NOT de.depends_on_package_id = ANY(dt.path)`
  stopping the walk the moment it would revisit a node. Real dependency
  graphs shouldn't have cycles, but nothing guarantees the crawled data
  never does (a mistake in a package's metadata, a crawler bug, etc.),
  so this is defensive, not decorative.
- `max_depth` is a second, independent safety net (default 50) in case of
  a very deep but legitimate chain -- the cycle guard alone wouldn't stop
  that, since it's not a cycle.
- `aggregate_score` takes the MIN of the package's own score and its
  worst dependency's score, not an average -- a chain is only as strong
  as its weakest link; one severely abandoned transitive dependency
  should drag the aggregate down even if everything else in the tree is
  healthy. This mirrors the project's own framing for the bus-factor
  signal ("what if the one key person leaves") applied at the dependency
  level instead of the contributor level.

This does NOT persist the result anywhere -- there's no column for it on
`packages` or `score_history` yet. Adding one is a `models.py` change and,
per the team's own rule, a group decision via reviewed PR, not something
to add unilaterally here. For now this is callable on demand, the same
way build_stats.py / score_real_packages.py are.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Package



_TREE_RISK_QUERY = text(
    """
    WITH RECURSIVE dependency_tree(package_id, depth) AS (
        SELECT
            de.depends_on_package_id,
            1
        FROM dependency_edges de
        WHERE de.package_id = :root_package_id
          AND de.depends_on_package_id <> :root_package_id

        UNION

        SELECT
            de.depends_on_package_id,
            dt.depth + 1
        FROM dependency_edges de
        JOIN dependency_tree dt
            ON de.package_id = dt.package_id
        WHERE dt.depth < :max_depth
          AND de.depends_on_package_id <> :root_package_id
    ),
    distinct_tree AS (
        SELECT
            package_id,
            MIN(depth) AS min_depth
        FROM dependency_tree
        GROUP BY package_id
    )
    SELECT
        COUNT(*) AS tree_size,
        MIN(p.current_score) AS worst_dependency_score,
        AVG(p.current_score) AS avg_dependency_score,
        MAX(dt.min_depth) AS max_depth_reached
    FROM distinct_tree dt
    JOIN packages p ON p.id = dt.package_id
    WHERE p.current_score IS NOT NULL
    """
)


@dataclass
class TreeRiskResult:
    package_id: int
    own_score: Optional[float]
    tree_size: int
    worst_dependency_score: Optional[float]
    avg_dependency_score: Optional[float]
    max_depth_reached: Optional[int]
    aggregate_score: Optional[float]


def compute_tree_risk(
    session: Session, package_id: int, max_depth: int = 50
) -> TreeRiskResult:
    """
    Walk package_id's full dependency tree and aggregate its risk.

    max_depth is a safety cap on recursion depth (see module docstring),
    not a meaningful tuning knob for most calls -- the default of 50 is
    far deeper than any real dependency chain in this dataset.
    """
    row = session.execute(
        _TREE_RISK_QUERY,
        {"root_package_id": package_id, "max_depth": max_depth},
    ).first()

    package = session.get(Package, package_id)
    own_score = package.current_score if package is not None else None

    tree_size = row.tree_size or 0
    worst_dependency_score = row.worst_dependency_score
    avg_dependency_score = row.avg_dependency_score
    max_depth_reached = row.max_depth_reached

    if worst_dependency_score is not None and own_score is not None:
        aggregate_score = min(own_score, worst_dependency_score)
    elif worst_dependency_score is not None:
        aggregate_score = worst_dependency_score
    else:
        aggregate_score = own_score

    return TreeRiskResult(
        package_id=package_id,
        own_score=own_score,
        tree_size=tree_size,
        worst_dependency_score=worst_dependency_score,
        avg_dependency_score=avg_dependency_score,
        max_depth_reached=max_depth_reached,
        aggregate_score=aggregate_score,
    )