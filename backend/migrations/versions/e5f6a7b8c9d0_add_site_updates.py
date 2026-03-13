"""Add site updates table

Revision ID: e5f6a7b8c9d0
Revises: d4f1a2b3c4d5
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "site_updates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("broadcast_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("broadcast_success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("broadcast_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_site_updates_created_at"), "site_updates", ["created_at"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_site_updates_created_at"), table_name="site_updates")
    op.drop_table("site_updates")
