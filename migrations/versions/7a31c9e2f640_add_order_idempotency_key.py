"""Add idempotency key to orders.

Revision ID: 7a31c9e2f640
Revises: 200f8479a03d
"""
from alembic import op
import sqlalchemy as sa

revision = "7a31c9e2f640"
down_revision = "200f8479a03d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "orders",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "uq_orders_user_idempotency_key",
        "orders",
        ["user_id", "idempotency_key"],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_orders_user_idempotency_key", table_name="orders")
    op.drop_column("orders", "idempotency_key")
