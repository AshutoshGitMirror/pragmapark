"""add token blacklist and ledger outbox

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "token_blacklist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_token_blacklist_token_hash", "token_blacklist", ["token_hash"], unique=True)

    op.create_table(
        "ledger_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tx_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ledger_outbox_tx_hash", "ledger_outbox", ["tx_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ledger_outbox_tx_hash", table_name="ledger_outbox")
    op.drop_table("ledger_outbox")
    op.drop_index("ix_token_blacklist_token_hash", table_name="token_blacklist")
    op.drop_table("token_blacklist")
