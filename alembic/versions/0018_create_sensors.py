"""create sensors table for per-device API-key authentication

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None


def upgrade():
    op.create_table(
        "sensors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sensor_id", sa.String(50), nullable=False),
        sa.Column(
            "lot_id",
            sa.String(50),
            sa.ForeignKeyConstraint(
                ["lot_id"], ["parking_lots.lot_id"], ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(255), nullable=False, server_default=""),
        sa.Column("api_key_hash", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("sensor_id"),
        sa.UniqueConstraint("api_key_hash"),
    )
    op.create_index("ix_sensors_sensor_id", "sensors", ["sensor_id"], unique=True)
    op.create_index("ix_sensors_lot_id", "sensors", ["lot_id"], unique=False)
    op.create_index("ix_sensors_owner_id", "sensors", ["owner_id"], unique=False)
    op.create_index("ix_sensors_api_key_hash", "sensors", ["api_key_hash"], unique=True)


def downgrade():
    op.drop_index("ix_sensors_api_key_hash", table_name="sensors")
    op.drop_index("ix_sensors_owner_id", table_name="sensors")
    op.drop_index("ix_sensors_lot_id", table_name="sensors")
    op.drop_index("ix_sensors_sensor_id", table_name="sensors")
    op.drop_table("sensors")
