"""add ipfs_store table

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ipfs_store",
        sa.Column("cid", sa.String(64), primary_key=True),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(50), server_default="generic"),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), server_default="0"),
        sa.Column("pinned", sa.Integer(), server_default="1"),
    )


def downgrade():
    op.drop_table("ipfs_store")
