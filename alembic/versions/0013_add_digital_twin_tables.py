"""add zone_snapshots, dt_config, twin_state_history tables

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "zone_snapshots",
        sa.Column("zone_id", sa.String(50), primary_key=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("occupancy_rate", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("price", sa.Float(), nullable=False, server_default="10.0"),
        sa.Column("updated_at", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_table(
        "dt_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("current_time", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stid_weights", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_table(
        "twin_state_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.Float(), nullable=False, index=True),
        sa.Column("zone_id", sa.String(50), nullable=False, index=True),
        sa.Column("occupancy_rate", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("total_slots", sa.Integer(), nullable=False),
        sa.Column("flux", sa.Float(), server_default="0"),
        sa.Column("congestion_level", sa.String(20), server_default="normal"),
        sa.Column("stid_prediction", sa.Float(), nullable=True),
    )


def downgrade():
    op.drop_table("twin_state_history")
    op.drop_table("dt_config")
    op.drop_table("zone_snapshots")
