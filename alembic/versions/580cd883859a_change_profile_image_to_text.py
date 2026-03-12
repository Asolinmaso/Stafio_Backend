"""change profile_image to text

Revision ID: 580cd883859a
Revises: 1ca64e998525
Create Date: 2026-03-11 20:19:06.090920

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '580cd883859a'
down_revision = '1ca64e998525'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'employee_profiles',
        'profile_image',
        existing_type=sa.String(length=255),
        type_=sa.Text()
    )


def downgrade():
    op.alter_column(
        'employee_profiles',
        'profile_image',
        existing_type=sa.Text(),
        type_=sa.String(length=255)
    )
