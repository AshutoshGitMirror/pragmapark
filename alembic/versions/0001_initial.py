"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), server_default="driver"),
        sa.Column("organization", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "parking_lots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), server_default=""),
        sa.Column("total_slots", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("timezone", sa.String(50), server_default="UTC"),
        sa.Column("base_price", sa.Numeric(10, 2), server_default="10.0"),
        sa.Column("price_cap", sa.Numeric(10, 2), server_default="200.0"),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parking_lots_lot_id", "parking_lots", ["lot_id"], unique=True)
    op.create_index("ix_parking_lots_owner_id", "parking_lots", ["owner_id"])

    op.create_table(
        "occupancy_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.String(50), sa.ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False),
        sa.Column("occupied_slots", sa.Integer(), nullable=False),
        sa.Column("total_slots", sa.Integer(), nullable=False),
        sa.Column("occupancy_rate", sa.Float(), nullable=False),
        sa.Column("net_flux", sa.Float(), server_default="0.0"),
        sa.Column("price", sa.Numeric(10, 2), server_default="10.0"),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_occupancy_records_lot_id", "occupancy_records", ["lot_id"])
    op.create_index("ix_occupancy_records_timestamp", "occupancy_records", ["timestamp"])

    op.create_table(
        "parking_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("lot_id", sa.String(50), sa.ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False),
        sa.Column("driver_id", sa.String(100), nullable=False),
        sa.Column("slot", sa.Integer(), server_default="0"),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), server_default="0"),
        sa.Column("entry_price", sa.Numeric(10, 2), server_default="10.0"),
        sa.Column("final_price", sa.Numeric(10, 2), server_default="10.0"),
        sa.Column("amount_charged", sa.Numeric(10, 2), server_default="0.0"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("blockchain_ref", sa.String(255), nullable=True),
        sa.Column("payment_tx", sa.String(255), nullable=True),
        sa.Column("payment_blockchain_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parking_sessions_session_id", "parking_sessions", ["session_id"], unique=True)
    op.create_index("ix_parking_sessions_lot_id", "parking_sessions", ["lot_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tx_hash", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("session_id", sa.String(100), sa.ForeignKey("parking_sessions.session_id", ondelete="SET NULL"), nullable=True),
        sa.Column("lot_id", sa.String(50), sa.ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False),
        sa.Column("driver_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), server_default="completed", nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("blockchain_ref", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tx_hash"),
    )
    op.create_index("ix_transactions_idempotency_key", "transactions", ["idempotency_key"], unique=True)
    op.create_index("ix_transactions_session_id", "transactions", ["session_id"])
    op.create_index("ix_transactions_lot_id", "transactions", ["lot_id"])

    op.create_table(
        "prediction_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.String(50), sa.ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(100), sa.ForeignKey("parking_sessions.session_id", ondelete="CASCADE"), nullable=True),
        sa.Column("predicted_occupancy", sa.Float(), nullable=False),
        sa.Column("actual_occupancy", sa.Float(), nullable=True),
        sa.Column("mae", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(50), server_default="rf+xgb_ensemble_v2"),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prediction_metrics_lot_id", "prediction_metrics", ["lot_id"])
    op.create_index("ix_prediction_metrics_session_id", "prediction_metrics", ["session_id"])

    op.create_table(
        "revenue_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.String(50), sa.ForeignKey("parking_lots.lot_id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("total_transactions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_revenue", sa.Numeric(10, 2), server_default="0.0", nullable=False),
        sa.Column("avg_price", sa.Numeric(10, 2), server_default="0.0", nullable=False),
        sa.Column("avg_occupancy", sa.Float(), server_default="0.0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lot_id", "date", name="uq_revenue_lot_date"),
    )
    op.create_index("ix_revenue_records_lot_id", "revenue_records", ["lot_id"])
    op.create_index("ix_revenue_records_date", "revenue_records", ["date"])


def downgrade() -> None:
    op.drop_table("revenue_records")
    op.drop_table("prediction_metrics")
    op.drop_table("transactions")
    op.drop_table("parking_sessions")
    op.drop_table("occupancy_records")
    op.drop_table("parking_lots")
    op.drop_table("users")
