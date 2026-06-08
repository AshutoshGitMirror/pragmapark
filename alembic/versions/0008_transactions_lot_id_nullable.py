"""align financial schema with ORM

Wallet top-ups, deposits, refunds, and other account-level financial events are
valid transactions that are not tied to a parking lot. The ORM models
Transaction.lot_id as nullable, but the original migration created it NOT NULL.

This migration also captures ORM drift introduced by the wallet/prebooking
financial flow: user balances, prebook fee/deposit columns, and indexes used by
session, prediction, and transaction queries.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-08
"""
from typing import Sequence, Union, cast

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {cast(str, i["name"]) for i in inspect(op.get_bind()).get_indexes(table) if i.get("name") is not None}


def upgrade() -> None:
    if "balance" not in _columns("users"):
        op.add_column("users", sa.Column("balance", sa.Float(), nullable=True, server_default="0"))

    prebook_cols = _columns("prebook_records")
    with op.batch_alter_table("prebook_records") as batch_op:
        if "booking_fee" not in prebook_cols:
            batch_op.add_column(sa.Column("booking_fee", sa.Float(), nullable=True, server_default="0"))
        if "deposit" not in prebook_cols:
            batch_op.add_column(sa.Column("deposit", sa.Float(), nullable=True, server_default="0"))
        if "deposit_refunded" not in prebook_cols:
            batch_op.add_column(sa.Column("deposit_refunded", sa.Integer(), nullable=True, server_default="0"))

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.alter_column(
            "lot_id",
            existing_type=sa.String(length=50),
            nullable=True,
            existing_nullable=False,
        )

    tx_indexes = _indexes("transactions")
    if "ix_transactions_driver_action" in tx_indexes:
        op.drop_index("ix_transactions_driver_action", table_name="transactions")
    if "ix_transactions_action" not in tx_indexes:
        op.create_index("ix_transactions_action", "transactions", ["action"])
    if "ix_transactions_timestamp" not in tx_indexes:
        op.create_index("ix_transactions_timestamp", "transactions", ["timestamp"])

    if "ix_parking_sessions_start_time" not in _indexes("parking_sessions"):
        op.create_index("ix_parking_sessions_start_time", "parking_sessions", ["start_time"])
    if "ix_prediction_metrics_timestamp" not in _indexes("prediction_metrics"):
        op.create_index("ix_prediction_metrics_timestamp", "prediction_metrics", ["timestamp"])


def downgrade() -> None:
    if "ix_prediction_metrics_timestamp" in _indexes("prediction_metrics"):
        op.drop_index("ix_prediction_metrics_timestamp", table_name="prediction_metrics")
    if "ix_parking_sessions_start_time" in _indexes("parking_sessions"):
        op.drop_index("ix_parking_sessions_start_time", table_name="parking_sessions")

    tx_indexes = _indexes("transactions")
    if "ix_transactions_timestamp" in tx_indexes:
        op.drop_index("ix_transactions_timestamp", table_name="transactions")
    if "ix_transactions_action" in tx_indexes:
        op.drop_index("ix_transactions_action", table_name="transactions")
    if "ix_transactions_driver_action" not in tx_indexes:
        op.create_index("ix_transactions_driver_action", "transactions", ["driver_id", "action"])

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.alter_column(
            "lot_id",
            existing_type=sa.String(length=50),
            nullable=False,
            existing_nullable=True,
        )

    prebook_cols = _columns("prebook_records")
    with op.batch_alter_table("prebook_records") as batch_op:
        if "deposit_refunded" in prebook_cols:
            batch_op.drop_column("deposit_refunded")
        if "deposit" in prebook_cols:
            batch_op.drop_column("deposit")
        if "booking_fee" in prebook_cols:
            batch_op.drop_column("booking_fee")

    if "balance" in _columns("users"):
        op.drop_column("users", "balance")
