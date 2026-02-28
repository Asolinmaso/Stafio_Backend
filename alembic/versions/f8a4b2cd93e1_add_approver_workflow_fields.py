"""add approver workflow fields

Revision ID: f8a4b2cd93e1
Revises: 6ddbb253a03a
Create Date: 2026-02-12 11:22:30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError


# revision identifiers, used by Alembic.
revision = 'f8a4b2cd93e1'
down_revision = '6ddbb253a03a'
branch_labels = None
depends_on = None


def _add_column_if_not_exists(table, column):
    """Add a column only if it doesn't already exist (idempotent)."""
    try:
        op.add_column(table, column)
    except ProgrammingError:
        # Column already exists – roll back the failed statement so the
        # transaction stays usable, then continue.
        op.execute("ROLLBACK TO SAVEPOINT pre_add_column")
    else:
        return
    # If we reach here the column existed; nothing to do.


def _create_fk_if_not_exists(name, source_table, referent_table, local_cols, remote_cols, ondelete=None):
    """Create a foreign key constraint only if it doesn't already exist."""
    try:
        op.create_foreign_key(
            name, source_table, referent_table,
            local_cols, remote_cols,
            ondelete=ondelete
        )
    except ProgrammingError:
        op.execute("ROLLBACK TO SAVEPOINT pre_add_fk")


def upgrade():
    bind = op.get_bind()

    def column_exists(table, col):
        result = bind.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name=:t AND column_name=:c"
            ),
            {"t": table, "c": col}
        )
        return result.fetchone() is not None

    def fk_exists(name, table):
        result = bind.execute(
            sa.text(
                "SELECT 1 FROM information_schema.table_constraints "
                "WHERE constraint_name=:n AND table_name=:t"
            ),
            {"n": name, "t": table}
        )
        return result.fetchone() is not None

    # ── leave_requests ───────────────────────────────────────────────────────
    if not column_exists('leave_requests', 'approver_type'):
        op.add_column('leave_requests',
            sa.Column('approver_type', sa.String(length=20), nullable=True))

    if not column_exists('leave_requests', 'designated_approver_id'):
        op.add_column('leave_requests',
            sa.Column('designated_approver_id', sa.Integer(), nullable=True))

    if not fk_exists('fk_leave_requests_designated_approver', 'leave_requests'):
        op.create_foreign_key(
            'fk_leave_requests_designated_approver',
            'leave_requests', 'users',
            ['designated_approver_id'], ['id'],
            ondelete='SET NULL'
        )

    # ── regularizations ──────────────────────────────────────────────────────
    if not column_exists('regularizations', 'approver_type'):
        op.add_column('regularizations',
            sa.Column('approver_type', sa.String(length=20), nullable=True))

    if not column_exists('regularizations', 'designated_approver_id'):
        op.add_column('regularizations',
            sa.Column('designated_approver_id', sa.Integer(), nullable=True))

    if not column_exists('regularizations', 'rejection_reason'):
        op.add_column('regularizations',
            sa.Column('rejection_reason', sa.Text(), nullable=True))

    if not column_exists('regularizations', 'approval_reason'):
        op.add_column('regularizations',
            sa.Column('approval_reason', sa.Text(), nullable=True))

    if not fk_exists('fk_regularizations_designated_approver', 'regularizations'):
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
    try:
        op.drop_constraint('fk_regularizations_designated_approver', 'regularizations', type_='foreignkey')
    except Exception:
        pass
    for col in ('approval_reason', 'rejection_reason', 'designated_approver_id', 'approver_type'):
        try:
            op.drop_column('regularizations', col)
        except Exception:
            pass

    # Remove from leave_requests
    try:
        op.drop_constraint('fk_leave_requests_designated_approver', 'leave_requests', type_='foreignkey')
    except Exception:
        pass
    for col in ('designated_approver_id', 'approver_type'):
        try:
            op.drop_column('leave_requests', col)
        except Exception:
            pass

