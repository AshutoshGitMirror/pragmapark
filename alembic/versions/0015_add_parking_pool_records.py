"""add parking_pool_records table

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "parking_pool_records",
        sa.Column("pool_id", sa.String(50), primary_key=True),
        sa.Column("total_spots", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String(100), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_table("parking_pool_records")
