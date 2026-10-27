"""Add checkout request fingerprint.
Revision ID: 8c42e1b7d903
Revises: 7a31c9e2f640
"""
from alembic import op
import sqlalchemy as sa

revision = "8c42e1b7d903"
down_revision = "7a31c9e2f640"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "orders",
        sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=True),
    )

def downgrade():
    op.drop_column("orders", "idempotency_fingerprint")
