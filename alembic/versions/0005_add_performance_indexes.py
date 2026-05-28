"""add performance indexes

Add indexes for common query patterns on parking_sessions,
transactions, and slot_state_log tables.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-28 00:00:00
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import inspect

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_parking_sessions_driver_id", "parking_sessions", ["driver_id"])
    op.create_index("ix_parking_sessions_status", "parking_sessions", ["status"])
    op.create_index("ix_transactions_driver_id", "transactions", ["driver_id"])
    op.create_index("ix_transactions_driver_action", "transactions", ["driver_id", "action"])

    bind = op.get_bind()
    inspector = inspect(bind)
    if "slot_state_log" in inspector.get_table_names():
        op.create_index("ix_slot_state_log_slot_id_timestamp", "slot_state_log", ["slot_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_parking_sessions_driver_id", table_name="parking_sessions")
    op.drop_index("ix_parking_sessions_status", table_name="parking_sessions")
    op.drop_index("ix_transactions_driver_id", table_name="transactions")
    op.drop_index("ix_transactions_driver_action", table_name="transactions")

    bind = op.get_bind()
    inspector = inspect(bind)
    if "slot_state_log" in inspector.get_table_names():
        op.drop_index("ix_slot_state_log_slot_id_timestamp", table_name="slot_state_log")
