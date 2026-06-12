"""add slot_current_state table

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "slot_current_state",
        sa.Column("slot_id", sa.Integer(), primary_key=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="available"),
        sa.Column("driver_id", sa.String(100), nullable=True),
        sa.Column("expires_at", sa.Float(), nullable=True),
        sa.Column("prebook_driver_id", sa.String(100), nullable=True),
        sa.Column("prebook_expires_at", sa.Float(), nullable=True),
        sa.Column("prebook_target", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_table("slot_current_state")
