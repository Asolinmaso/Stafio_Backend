"""add approver workflow fields

Revision ID: f8a4b2cd93e1
Revises: 6ddbb253a03a
Create Date: 2026-02-12 11:22:30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8a4b2cd93e1'
down_revision = '6ddbb253a03a'
branch_labels = None
depends_on = None


def upgrade():
    # Add approver workflow fields to leave_requests
    op.add_column('leave_requests',
        sa.Column('approver_type', sa.String(length=20), nullable=True))
    op.add_column('leave_requests',
        sa.Column('designated_approver_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_leave_requests_designated_approver',
        'leave_requests', 'users',
        ['designated_approver_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Add approver workflow fields to regularizations
    op.add_column('regularizations',
        sa.Column('approver_type', sa.String(length=20), nullable=True))
    op.add_column('regularizations',
        sa.Column('designated_approver_id', sa.Integer(), nullable=True))
    op.add_column('regularizations',
        sa.Column('rejection_reason', sa.Text(), nullable=True))
    op.create_foreign_key(
        'fk_regularizations_designated_approver',
        'regularizations', 'users',
        ['designated_approver_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Set default approver_type for existing records
    op.execute("UPDATE leave_requests SET approver_type = 'admin' WHERE approver_type IS NULL")
    op.execute("UPDATE regularizations SET approver_type = 'admin' WHERE approver_type IS NULL")


def downgrade():
    # Remove from regularizations
    op.drop_constraint('fk_regularizations_designated_approver', 'regularizations', type_='foreignkey')
    op.drop_column('regularizations', 'rejection_reason')
    op.drop_column('regularizations', 'designated_approver_id')
    op.drop_column('regularizations', 'approver_type')
    
    # Remove from leave_requests
    op.drop_constraint('fk_leave_requests_designated_approver', 'leave_requests', type_='foreignkey')
    op.drop_column('leave_requests', 'designated_approver_id')
    op.drop_column('leave_requests', 'approver_type')
