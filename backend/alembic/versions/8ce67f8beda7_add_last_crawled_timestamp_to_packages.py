from alembic import op
import sqlalchemy as sa

revision = '8ce67f8beda7'
down_revision = 'd3d64a2f867d'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        'packages',
        sa.Column('last_crawled_at', sa.DateTime(), nullable=True)
    )

def downgrade() -> None:
    op.drop_column('packages', 'last_crawled_at')
