"""merge heads

Revision ID: b09d18fa936e
Revises: bd845747596e, f8a4b2cd93e1
Create Date: 2026-02-27 13:03:09.992631

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b09d18fa936e'
down_revision = ('bd845747596e', 'f8a4b2cd93e1')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

