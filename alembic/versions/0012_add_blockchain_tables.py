"""add blockchain_blocks and blockchain_pending_tx tables

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "blockchain_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("index", sa.Integer(), nullable=False, unique=True),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("transactions", sa.Text(), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.Integer(), server_default="0"),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
    )
    op.create_table(
        "blockchain_pending_tx",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tx_data", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_table("blockchain_pending_tx")
    op.drop_table("blockchain_blocks")
