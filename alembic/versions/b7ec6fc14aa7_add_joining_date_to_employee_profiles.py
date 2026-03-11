"""add joining_date to employee_profiles

Revision ID: b7ec6fc14aa7
Revises: f8a4b2cd93e1
Create Date: 2026-03-03 13:12:22.028515
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b7ec6fc14aa7'
down_revision = 'f8a4b2cd93e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # ---- Broadcast table updates ----
    broadcast_columns = [col['name'] for col in inspector.get_columns('broadcasts')]
    
    if 'event_date' not in broadcast_columns:
        op.add_column('broadcasts', sa.Column('event_date', sa.Date(), nullable=True))
    if 'event_name' not in broadcast_columns:
        op.add_column('broadcasts', sa.Column('event_name', sa.String(length=200), nullable=True))
    if 'event_time' not in broadcast_columns:
        op.add_column('broadcasts', sa.Column('event_time', sa.String(length=50), nullable=True))
    if 'event_type' not in broadcast_columns:
        op.add_column('broadcasts', sa.Column('event_type', sa.String(length=50), nullable=True))
    if 'image_url' not in broadcast_columns:
        op.add_column('broadcasts', sa.Column('image_url', sa.String(length=500), nullable=True))
    if 'mentioned_employee_id' not in broadcast_columns:
        op.add_column('broadcasts', sa.Column('mentioned_employee_id', sa.Integer(), nullable=True))
    if 'author_name' not in broadcast_columns:
        op.add_column('broadcasts', sa.Column('author_name', sa.String(length=100), nullable=True))
    if 'author_email' not in broadcast_columns:
        op.add_column('broadcasts', sa.Column('author_email', sa.String(length=100), nullable=True))
    if 'author_designation' not in broadcast_columns:
        op.add_column('broadcasts', sa.Column('author_designation', sa.String(length=100), nullable=True))
    if 'reactions_count' not in broadcast_columns:
        op.add_column('broadcasts', sa.Column('reactions_count', sa.Integer(), nullable=True))

    if 'title' in broadcast_columns:
        op.alter_column(
            'broadcasts',
            'title',
            existing_type=sa.VARCHAR(length=200),
            nullable=True
        )

    # Check for foreign key existence is harder, but we can try-except or just assume if cols are missing
    try:
        op.create_foreign_key(
            'fk_broadcasts_mentioned_employee',
            'broadcasts',
            'users',
            ['mentioned_employee_id'],
            ['id'],
            ondelete='SET NULL'
        )
    except Exception:
        pass

    # ---- Employee Profile update ----
    profile_columns = [col['name'] for col in inspector.get_columns('employee_profiles')]
    if 'joining_date' not in profile_columns:
        op.add_column(
            'employee_profiles',
            sa.Column('joining_date', sa.Date(), nullable=True)
        )

    # ---- Regularizations update ----
    reg_columns = [col['name'] for col in inspector.get_columns('regularizations')]
    if 'approval_reason' not in reg_columns:
        op.add_column(
            'regularizations',
            sa.Column('approval_reason', sa.Text(), nullable=True)
        )


def downgrade() -> None:
    # ---- Remove Regularizations column ----
    op.drop_column('regularizations', 'approval_reason')

    # ---- Remove Employee joining_date ----
    op.drop_column('employee_profiles', 'joining_date')

    # ---- Remove Broadcast FK ----
    op.drop_constraint(
        'fk_broadcasts_mentioned_employee',
        'broadcasts',
        type_='foreignkey'
    )

    # ---- Revert Broadcast changes ----
    op.alter_column(
        'broadcasts',
        'title',
        existing_type=sa.VARCHAR(length=200),
        nullable=False
    )

    op.drop_column('broadcasts', 'reactions_count')
    op.drop_column('broadcasts', 'author_designation')
    op.drop_column('broadcasts', 'author_email')
    op.drop_column('broadcasts', 'author_name')
    op.drop_column('broadcasts', 'mentioned_employee_id')
    op.drop_column('broadcasts', 'image_url')
    op.drop_column('broadcasts', 'event_type')
    op.drop_column('broadcasts', 'event_time')
    op.drop_column('broadcasts', 'event_name')
    op.drop_column('broadcasts', 'event_date')