"""merge Phase 2 and Phase 4 migration heads

Revision ID: c585b30e0e1f
Revises: 8a5952ef9068, 8ce67f8beda7
Create Date: 2026-11-22 05:47:09.913618

"""
from alembic import op
import sqlalchemy as sa


revision = 'c585b30e0e1f'
down_revision = ('8a5952ef9068', '8ce67f8beda7')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
