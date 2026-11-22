"""Create riskiest_packages materialized view (leaderboard)

Revision ID: 8a5952ef9068
Revises: f6d23e5fa5fb
Create Date: 2026-11-21 00:05:00.000000

The leaderboard ("riskiest popular packages") is precomputed into a
materialized view and refreshed on a schedule, rather than recalculated
on every request -- a real performance-engineering decision, per the
project plan.

The view also surfaces each package's score from ~30 days ago (pulled
from the now-partitioned score_history) alongside its current score, so
the leaderboard can show a trend, not just a snapshot -- this is the
"live risk score + trend arrow" the original feature spec calls for.

A unique index on package_id is required for
REFRESH MATERIALIZED VIEW CONCURRENTLY to work (Postgres enforces this),
which matters here specifically because a concurrent refresh doesn't
block reads of the view while it runs.
"""
from alembic import op


revision = '8a5952ef9068'
down_revision = 'f6d23e5fa5fb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE MATERIALIZED VIEW riskiest_packages AS
        WITH latest_old_score AS (
            SELECT DISTINCT ON (package_id)
                package_id,
                score AS score_30d_ago
            FROM score_history
            WHERE scored_at <= NOW() - INTERVAL '30 days'
            ORDER BY package_id, scored_at DESC
        )
        SELECT
            p.id AS package_id,
            p.registry,
            p.name,
            p.repo_url,
            p.current_score,
            p.last_scored_at,
            los.score_30d_ago,
            (p.current_score - los.score_30d_ago) AS score_change_30d
        FROM packages p
        LEFT JOIN latest_old_score los ON los.package_id = p.id
        WHERE p.current_score IS NOT NULL
        ORDER BY p.current_score ASC
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_riskiest_packages_package_id "
        "ON riskiest_packages (package_id)"
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS riskiest_packages")