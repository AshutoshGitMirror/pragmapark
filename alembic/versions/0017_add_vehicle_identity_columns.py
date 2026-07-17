"""add registered_vehicle to resident_profiles and vehicle_id to share_bookings

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None


def upgrade():
    op.add_column("resident_profiles", sa.Column("registered_vehicle", sa.String(20), nullable=True))
    op.add_column("share_bookings", sa.Column("vehicle_id", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("share_bookings", "vehicle_id")
    op.drop_column("resident_profiles", "registered_vehicle")
