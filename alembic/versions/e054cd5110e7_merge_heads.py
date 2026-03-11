"""merge heads

Revision ID: e054cd5110e7
Revises: b09d18fa936e, b7ec6fc14aa7
Create Date: 2026-03-10 16:41:54.703684

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e054cd5110e7'
down_revision = ('b09d18fa936e', 'b7ec6fc14aa7')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

