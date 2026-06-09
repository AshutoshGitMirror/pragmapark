"""add rate_limit_windows table

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rate_limit_windows",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("call_count", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_rate_limit_windows_window_start",
        "rate_limit_windows",
        ["window_start"],
    )


def downgrade():
    op.drop_table("rate_limit_windows")
