"""Add site update delivery queue

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f7a8b9c0d1e2"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "newsletter_subscribers",
        sa.Column("phone", sa.String(length=32), nullable=True),
    )

    op.add_column(
        "site_updates",
        sa.Column("broadcast_pending_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "site_updates",
        sa.Column("send_email", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "site_updates",
        sa.Column("send_sms", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "site_updates",
        sa.Column("send_whatsapp", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "site_updates",
        sa.Column("schedule_type", sa.String(length=20), nullable=False, server_default="immediate"),
    )
    op.add_column(
        "site_updates",
        sa.Column("schedule_day", sa.Integer(), nullable=True),
    )
    op.add_column(
        "site_updates",
        sa.Column("schedule_month", sa.Integer(), nullable=True),
    )
    op.add_column(
        "site_updates",
        sa.Column("last_scheduled_run_on", sa.Date(), nullable=True),
    )

    op.create_table(
        "site_update_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_update_id", sa.Integer(), nullable=False),
        sa.Column("subscriber_id", sa.Integer(), nullable=True),
        sa.Column("recipient_name", sa.String(length=100), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("recipient_phone", sa.String(length=32), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False, server_default="email"),
        sa.Column("dispatch_key", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["site_update_id"], ["site_updates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscriber_id"], ["newsletter_subscribers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_site_update_deliveries_site_update_id"),
        "site_update_deliveries",
        ["site_update_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_site_update_deliveries_recipient_email"),
        "site_update_deliveries",
        ["recipient_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_site_update_deliveries_recipient_phone"),
        "site_update_deliveries",
        ["recipient_phone"],
        unique=False,
    )
    op.create_index(
        op.f("ix_site_update_deliveries_channel"),
        "site_update_deliveries",
        ["channel"],
        unique=False,
    )
    op.create_index(
        op.f("ix_site_update_deliveries_dispatch_key"),
        "site_update_deliveries",
        ["dispatch_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_site_update_deliveries_status"),
        "site_update_deliveries",
        ["status"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_site_update_deliveries_status"), table_name="site_update_deliveries")
    op.drop_index(op.f("ix_site_update_deliveries_dispatch_key"), table_name="site_update_deliveries")
    op.drop_index(op.f("ix_site_update_deliveries_channel"), table_name="site_update_deliveries")
    op.drop_index(op.f("ix_site_update_deliveries_recipient_phone"), table_name="site_update_deliveries")
    op.drop_index(op.f("ix_site_update_deliveries_recipient_email"), table_name="site_update_deliveries")
    op.drop_index(op.f("ix_site_update_deliveries_site_update_id"), table_name="site_update_deliveries")
    op.drop_table("site_update_deliveries")
    op.drop_column("site_updates", "last_scheduled_run_on")
    op.drop_column("site_updates", "schedule_month")
    op.drop_column("site_updates", "schedule_day")
    op.drop_column("site_updates", "schedule_type")
    op.drop_column("site_updates", "send_whatsapp")
    op.drop_column("site_updates", "send_sms")
    op.drop_column("site_updates", "send_email")
    op.drop_column("site_updates", "broadcast_pending_count")
    op.drop_column("newsletter_subscribers", "phone")
