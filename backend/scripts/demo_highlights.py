"""
Phase 4: picks a short, curated set of real demo talking points instead
of scrolling through all 399 scored packages live. Selected automatically
from whatever's actually in the database right now, so this stays
accurate as the dataset changes rather than hardcoding package names
that could drift (e.g. if B re-crawls and numbers shift).

Picks four stories:
  1. Healthiest high-confidence package -- "here's what a well-run
     project looks like"
  2. Riskiest high-confidence package (real signal, not missing data)
     -- "here's a genuine risk our formula caught"
  3. A low-confidence package -- "here's the system being honest about
     not having enough data, instead of asserting a number it can't back"
  4. Biggest tree-risk drop -- a package that looks fine on its own but
     whose dependency tree drags its aggregate score down -- "here's why
     the recursive CTE matters, not just the base score"

Run with:
    docker exec -it -e PYTHONPATH=/app supplyrisk_backend python scripts/demo_highlights.py
"""

from app.database import SessionLocal
from app.models import Package, DependencyEdge
from app.scoring.build_stats import build_stats_for_package
from app.scoring import compute_score
from app.scoring.dependency_tree import compute_tree_risk


def main():
    session = SessionLocal()
    try:
        packages = session.query(Package).all()

        scored = []
        for package in packages:
            stats = build_stats_for_package(session, package)
            result = compute_score(stats)
            confidence = result.breakdown["data_completeness"]["confidence"]
            scored.append((package, result, confidence))

        high_confidence = [s for s in scored if s[2] == "high"]
        low_confidence = [s for s in scored if s[2] == "low"]

        healthiest = max(high_confidence, key=lambda s: s[1].score, default=None)
        riskiest_real = min(high_confidence, key=lambda s: s[1].score, default=None)
        low_confidence_example = low_confidence[0] if low_confidence else None

        # Biggest tree-risk drop: only among packages with real outgoing edges
        dependency_package_ids = {
            row[0] for row in session.query(DependencyEdge.package_id).distinct()
        }
        biggest_drop = None
        biggest_drop_margin = -1
        for package, result, confidence in scored:
            if package.id not in dependency_package_ids:
                continue
            tree_result = compute_tree_risk(session, package.id)
            if tree_result.aggregate_score is None or tree_result.own_score is None:
                continue
            margin = tree_result.own_score - tree_result.aggregate_score
            if margin > biggest_drop_margin:
                biggest_drop_margin = margin
                biggest_drop = (package, tree_result)

        print("=" * 70)
        print("DEMO HIGHLIGHTS")
        print("=" * 70)

        if healthiest:
            pkg, result, _ = healthiest
            print(f"\n1. HEALTHY EXAMPLE: {pkg.registry}/{pkg.name}")
            print(f"   Score: {result.score}/100 (high confidence)")
            print(f"   {result.breakdown['signals']['bus_factor']['reason']}")

        if riskiest_real:
            pkg, result, _ = riskiest_real
            print(f"\n2. GENUINE RISK EXAMPLE: {pkg.registry}/{pkg.name}")
            print(f"   Score: {result.score}/100 (high confidence -- this is a real signal, not missing data)")
            print(f"   {result.breakdown['signals']['bus_factor']['reason']}")

        if low_confidence_example:
            pkg, result, _ = low_confidence_example
            print(f"\n3. LOW-CONFIDENCE EXAMPLE: {pkg.registry}/{pkg.name}")
            print(f"   Score: {result.score}/100 (low confidence -- insufficient crawled data, not a real risk assessment)")
            completeness = result.breakdown["data_completeness"]
            print(f"   Only {completeness['signals_with_data']}/{completeness['total_signals']} signals had real data")

        if biggest_drop:
            pkg, tree_result = biggest_drop
            print(f"\n4. DEPENDENCY-TREE RISK EXAMPLE: {pkg.registry}/{pkg.name}")
            print(f"   Own score: {tree_result.own_score} -> Tree-adjusted: {tree_result.aggregate_score}")
            print(f"   Worst dependency in its tree scores {tree_result.worst_dependency_score} "
                  f"(tree size: {tree_result.tree_size}, depth: {tree_result.max_depth_reached})")

        print("\n" + "=" * 70)
    finally:
        session.close()


if __name__ == "__main__":
    main()