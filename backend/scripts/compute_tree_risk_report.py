"""
Runs the recursive dependency-tree risk aggregation against every real
package that has at least one outgoing dependency edge, and prints them
sorted by aggregate_score ascending (riskiest trees first).

This is the Phase 2 equivalent of score_real_packages.py: it doesn't
compute anything new about individual packages, it aggregates what's
already in `packages.current_score` across each package's real
dependency graph from B's crawler.

Run with:
    docker exec -it -e PYTHONPATH=/app supplyrisk_backend python scripts/compute_tree_risk_report.py
"""

from app.database import SessionLocal
from app.models import Package, DependencyEdge
from app.scoring.dependency_tree import compute_tree_risk


def main():
    session = SessionLocal()
    try:
        package_ids_with_deps = (
            session.query(DependencyEdge.package_id)
            .distinct()
            .all()
        )
        package_ids = [row[0] for row in package_ids_with_deps]

        if not package_ids:
            print(
                "No packages have dependency edges yet — run "
                "dependencies_bulk first."
            )
            return

        results = []
        for package_id in package_ids:
            result = compute_tree_risk(session, package_id)
            results.append(result)

        results.sort(
            key=lambda r: (r.aggregate_score is None, r.aggregate_score)
        )

        packages_by_id = {
            p.id: p for p in session.query(Package).filter(
                Package.id.in_(package_ids)
            )
        }

        print(f"{'Package':35} {'Own':>6} {'TreeMin':>8} {'TreeAvg':>8} "
              f"{'Agg':>6} {'Size':>5} {'Depth':>6}")
        print("-" * 80)
        for result in results:
            package = packages_by_id.get(result.package_id)
            label = f"{package.registry}/{package.name}" if package else str(result.package_id)
            print(
                f"{label:35} "
                f"{_fmt(result.own_score):>6} "
                f"{_fmt(result.worst_dependency_score):>8} "
                f"{_fmt(result.avg_dependency_score):>8} "
                f"{_fmt(result.aggregate_score):>6} "
                f"{result.tree_size:>5} "
                f"{_fmt(result.max_depth_reached, is_int=True):>6}"
            )
    finally:
        session.close()


def _fmt(value, is_int=False):
    if value is None:
        return "-"
    return str(int(value)) if is_int else f"{value:.1f}"


if __name__ == "__main__":
    main()