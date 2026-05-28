"""add payment_method column, widen slot_state_log.lot_id

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # Add payment_method column if not already present (may exist via
    # runtime ALTER TABLE on older deployments)
    cols = [c["name"] for c in inspector.get_columns("parking_sessions")]
    if "payment_method" not in cols:
        op.add_column(
            "parking_sessions",
            sa.Column("payment_method", sa.String(20), server_default="card"),
        )

    # Widen slot_state_log.lot_id from VARCHAR(20) to VARCHAR(50) to
    # match parking_lots.lot_id primary key — prevents truncation
    # when a lot_id with length >20 is logged.
    if "slot_state_log" in inspector.get_table_names():
        ssl_cols = inspector.get_columns("slot_state_log")
        lot_col = next(
            (c for c in ssl_cols if c["name"] == "lot_id"), None
        )
        if lot_col is not None:
            current_len = (
                lot_col["type"].length
                if hasattr(lot_col["type"], "length")
                else None
            )
            if isinstance(current_len, int) and current_len < 50:
                with op.batch_alter_table("slot_state_log") as batch_op:
                    batch_op.alter_column(
                        "lot_id", type_=sa.String(50)
                    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    cols = [c["name"] for c in inspector.get_columns("parking_sessions")]
    if "payment_method" in cols:
        op.drop_column("parking_sessions", "payment_method")

    if "slot_state_log" in inspector.get_table_names():
        ssl_cols = inspector.get_columns("slot_state_log")
        lot_col = next(
            (c for c in ssl_cols if c["name"] == "lot_id"), None
        )
        if lot_col is not None:
            current_len = (
                lot_col["type"].length
                if hasattr(lot_col["type"], "length")
                else None
            )
            if isinstance(current_len, int) and current_len > 20:
                with op.batch_alter_table("slot_state_log") as batch_op:
                    batch_op.alter_column(
                        "lot_id", type_=sa.String(20)
                    )
