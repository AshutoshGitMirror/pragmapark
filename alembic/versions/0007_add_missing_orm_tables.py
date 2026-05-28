"""add 5 ORM tables missing from alembic migrations

micro_zones, micro_slots, slot_reservations, prebook_records,
and slot_state_log are defined in src/api/database.py but were
never added to an alembic migration. They currently exist in
production via the create_all() fallback in run_migrations().
This migration ensures alembic can fully reconstruct the schema.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = inspector.get_table_names()

    # micro_zones
    if "micro_zones" not in existing:
        op.create_table(
            "micro_zones",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "lot_id",
                sa.String(50),
                sa.ForeignKey("parking_lots.lot_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.Text(), server_default=""),
            sa.Column("centroid_x", sa.Float(), server_default="0.0"),
            sa.Column("centroid_y", sa.Float(), server_default="0.0"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_micro_zones_lot_id", "micro_zones", ["lot_id"])

    # micro_slots
    if "micro_slots" not in existing:
        op.create_table(
            "micro_slots",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "lot_id",
                sa.String(50),
                sa.ForeignKey("parking_lots.lot_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("slot_index", sa.Integer(), nullable=False),
            sa.Column(
                "micro_zone_id",
                sa.Integer(),
                sa.ForeignKey("micro_zones.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("row_label", sa.String(10), server_default="A"),
            sa.Column("position", sa.Integer(), server_default="0"),
            sa.Column("slot_type", sa.String(20), server_default="regular"),
            sa.Column("active", sa.Integer(), server_default="1"),
            sa.Column("base_modifier_score", sa.Float(), server_default="0.0"),
            sa.Column("current_modifier", sa.Float(), server_default="0.0"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("lot_id", "slot_index", name="uq_slot_lot_index"),
        )
        op.create_index("ix_micro_slots_lot_id", "micro_slots", ["lot_id"])
        op.create_index("ix_micro_slots_micro_zone_id", "micro_slots", ["micro_zone_id"])

    # slot_reservations
    if "slot_reservations" not in existing:
        op.create_table(
            "slot_reservations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "slot_id",
                sa.Integer(),
                sa.ForeignKey("micro_slots.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("driver_id", sa.String(100), nullable=False),
            sa.Column("idempotency_key", sa.String(64), nullable=True),
            sa.Column("target_time", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("probability_given", sa.Float(), server_default="0.0"),
            sa.Column(
                "status", sa.String(20), server_default="active", nullable=False
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_slot_reservations_slot_id", "slot_reservations", ["slot_id"]
        )
        op.create_index(
            "ix_slot_reservations_driver_id", "slot_reservations", ["driver_id"]
        )
        op.create_index(
            "ix_slot_reservations_idempotency_key",
            "slot_reservations",
            ["idempotency_key"],
        )
        op.create_index(
            "ix_slot_reservations_expires_at", "slot_reservations", ["expires_at"]
        )
        op.create_index(
            "ix_slot_reservations_status", "slot_reservations", ["status"]
        )

    # prebook_records
    if "prebook_records" not in existing:
        op.create_table(
            "prebook_records",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("prebook_id", sa.String(64), nullable=False),
            sa.Column(
                "lot_id",
                sa.String(50),
                sa.ForeignKey("parking_lots.lot_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("driver_id", sa.String(100), nullable=False),
            sa.Column(
                "slot_id",
                sa.Integer(),
                sa.ForeignKey("micro_slots.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("slot_index", sa.Integer(), nullable=False),
            sa.Column("ranked_order", sa.Integer(), server_default="0"),
            sa.Column("target_time", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("probability_given", sa.Float(), server_default="0.0"),
            sa.Column("price_at_booking", sa.Numeric(10, 2), server_default="0.0"),
            sa.Column(
                "status", sa.String(20), server_default="active", nullable=False
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("prebook_id"),
        )
        op.create_index(
            "ix_prebook_records_prebook_id",
            "prebook_records",
            ["prebook_id"],
            unique=True,
        )
        op.create_index("ix_prebook_records_lot_id", "prebook_records", ["lot_id"])
        op.create_index(
            "ix_prebook_records_driver_id", "prebook_records", ["driver_id"]
        )
        op.create_index("ix_prebook_records_status", "prebook_records", ["status"])

    # slot_state_log
    # NOTE: lot_id uses String(50) (not the model's String(20)) because
    # migration 0006 already widens this column for existing tables;
    # on a fresh DB this runs after 0006 so we create it at the
    # widened size to match the expected final schema.
    if "slot_state_log" not in existing:
        op.create_table(
            "slot_state_log",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("slot_id", sa.Integer(), nullable=False),
            sa.Column("lot_id", sa.String(50), nullable=False),
            sa.Column("previous_state", sa.String(20), nullable=True),
            sa.Column("new_state", sa.String(20), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=True),
            sa.Column("duration_s", sa.Float(), server_default="0.0"),
            sa.Column("driver_id", sa.String(100), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_slot_state_log_slot_id", "slot_state_log", ["slot_id"])
        op.create_index("ix_slot_state_log_lot_id", "slot_state_log", ["lot_id"])
        op.create_index(
            "ix_slot_state_log_timestamp", "slot_state_log", ["timestamp"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = inspector.get_table_names()

    for tbl in (
        "slot_state_log",
        "prebook_records",
        "slot_reservations",
        "micro_slots",
        "micro_zones",
    ):
        if tbl in existing:
            op.drop_table(tbl)
