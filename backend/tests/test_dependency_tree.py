"""
Integration test for compute_tree_risk() — unlike test_scoring.py, this
genuinely needs a running Postgres, because the recursive CTE itself
(ARRAY-based cycle guard, RECURSIVE syntax) is Postgres-specific and
can't be exercised with fake in-memory data the way the pure signal
functions can.

Every row this test creates is rolled back at the end, never committed,
so it doesn't leave synthetic packages in the real dataset.

Run with:
    docker exec -it -e PYTHONPATH=/app supplyrisk_backend pytest tests/test_dependency_tree.py -v
"""

import pytest

from app.database import SessionLocal
from app.models import Package, DependencyEdge
from app.scoring.dependency_tree import compute_tree_risk


@pytest.fixture
def session():
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()


def _make_package(session, name, registry, score):
    package = Package(name=name, registry=registry, current_score=score)
    session.add(package)
    session.flush()  # assigns package.id without committing
    return package


def test_compute_tree_risk_diamond_and_cycle(session):
    """
    Graph:
        root -> lib_a, lib_b
        lib_a -> lib_c
        lib_b -> lib_c          (diamond: lib_c reachable two ways)
        lib_c -> lib_d
        lib_d -> lib_b          (cycle: lib_d depends back on lib_b)

    Expects: lib_a, lib_b, lib_c, lib_d counted exactly once each (no
    infinite loop from the cycle, no double-count from the diamond), and
    the worst score in the tree (lib_b, 20.0) drives the aggregate.
    """
    root = _make_package(session, "test-root-app", "pypi", 90.0)
    lib_a = _make_package(session, "test-lib-a", "pypi", 70.0)
    lib_b = _make_package(session, "test-lib-b", "pypi", 20.0)
    lib_c = _make_package(session, "test-lib-c", "pypi", 85.0)
    lib_d = _make_package(session, "test-lib-d", "pypi", 60.0)

    edges = [
        (root, lib_a), (root, lib_b),
        (lib_a, lib_c), (lib_b, lib_c),
        (lib_c, lib_d), (lib_d, lib_b),
    ]
    for src, dst in edges:
        session.add(
            DependencyEdge(package_id=src.id, depends_on_package_id=dst.id)
        )
    session.flush()

    result = compute_tree_risk(session, root.id)

    assert result.tree_size == 4
    assert result.worst_dependency_score == 20.0
    assert result.aggregate_score == 20.0  # min(root's 90, worst dep's 20)
    assert result.max_depth_reached == 3   # root->lib_b->lib_c->lib_d


def test_compute_tree_risk_no_dependencies(session):
    """A package with zero outgoing edges should return a clean empty tree,
    not an error — its own score is all there is to aggregate."""
    lonely = _make_package(session, "test-lonely-package", "npm", 55.0)

    result = compute_tree_risk(session, lonely.id)

    assert result.tree_size == 0
    assert result.worst_dependency_score is None
    assert result.aggregate_score == 55.0  # falls back to its own score


def test_compute_tree_risk_cycle_not_touching_root(session):
    """
    A cycle entirely downstream of the root (root -> A -> B -> C -> A)
    doesn't touch the root itself. The UNION-based query doesn't
    structurally forbid revisiting A/B/C the way the old ARRAY path
    check did -- it bounds the re-walking via max_depth instead -- but
    the final grouped aggregate must still come out correct.
    """
    root = _make_package(session, "test-root-cycle", "pypi", 90.0)
    lib_a = _make_package(session, "test-cycle-a", "pypi", 70.0)
    lib_b = _make_package(session, "test-cycle-b", "pypi", 20.0)  # worst
    lib_c = _make_package(session, "test-cycle-c", "pypi", 85.0)

    edges = [
        (root, lib_a),
        (lib_a, lib_b),
        (lib_b, lib_c),
        (lib_c, lib_a),  # cycles back to lib_a, not to root
    ]
    for src, dst in edges:
        session.add(
            DependencyEdge(package_id=src.id, depends_on_package_id=dst.id)
        )
    session.flush()

    result = compute_tree_risk(session, root.id)

    assert result.tree_size == 3  # lib_a, lib_b, lib_c — each once
    assert result.worst_dependency_score == 20.0
    assert result.aggregate_score == 20.0
