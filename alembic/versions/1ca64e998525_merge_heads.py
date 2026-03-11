"""merge heads

Revision ID: 1ca64e998525
Revises: bc2b9807fad5, e054cd5110e7
Create Date: 2026-03-11 13:47:13.981101

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1ca64e998525'
down_revision = ('bc2b9807fad5', 'e054cd5110e7')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

