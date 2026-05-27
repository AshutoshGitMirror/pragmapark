"""add index on slot_reservations.expires_at

slot_reservations table was added to the model after migration 0001
and is created by create_all() fallback, so it may not exist yet
when this migration runs on a fresh database.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-27
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import inspect

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "slot_reservations" not in inspector.get_table_names():
        # table will be created by create_all() fallback with the index
        return
    op.create_index(
        "ix_slot_reservations_expires_at",
        "slot_reservations",
        ["expires_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "slot_reservations" not in inspector.get_table_names():
        return
    op.drop_index("ix_slot_reservations_expires_at", table_name="slot_reservations")
