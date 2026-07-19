"""add residential slot geo + nullable lot_id

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-19

Residential home slots (a resident's driveway) are not tied to a commercial
lot, so micro_slots.lot_id becomes nullable. Every slot also gains its own
latitude/longitude so standalone residential slots can be pinned on a map and
bucketed by geohash. Existing lot-attached slots are backfilled with their
parent lot's coordinates. Dialect-aware (direct ALTER for Postgres,
batch_alter_table for SQLite).
"""

from alembic import op
import sqlalchemy as sa


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    op.add_column("micro_slots", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("micro_slots", sa.Column("longitude", sa.Float(), nullable=True))

    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE micro_slots ALTER COLUMN lot_id DROP NOT NULL")
    else:
        with op.batch_alter_table("micro_slots") as batch_op:
            batch_op.alter_column(
                "lot_id", existing_type=sa.String(50), nullable=True
            )

    # Backfill lat/lng from the parent lot for existing lot-attached slots.
    op.execute(
        "UPDATE micro_slots SET latitude = ("
        "SELECT parking_lots.latitude FROM parking_lots "
        "WHERE parking_lots.lot_id = micro_slots.lot_id) "
        "WHERE latitude IS NULL AND lot_id IS NOT NULL"
    )
    op.execute(
        "UPDATE micro_slots SET longitude = ("
        "SELECT parking_lots.longitude FROM parking_lots "
        "WHERE parking_lots.lot_id = micro_slots.lot_id) "
        "WHERE longitude IS NULL AND lot_id IS NOT NULL"
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE micro_slots ALTER COLUMN lot_id SET NOT NULL")
    else:
        with op.batch_alter_table("micro_slots") as batch_op:
            batch_op.alter_column(
                "lot_id", existing_type=sa.String(50), nullable=False
            )
    op.drop_column("micro_slots", "longitude")
    op.drop_column("micro_slots", "latitude")
