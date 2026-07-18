"""enforce occupancy_rate not null

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-18

Prod schema drifted from the ORM/migration definition: OccupancyRecord.occupancy_rate
was declared nullable=False in the ORM (database.py) and in all prior migrations
(0001, 0013, 9dfac872075f), but live prod rows contained NULL occupancy_rate,
causing 'TypeError: unsupported operand type(s) for *: NoneType and int' on every
endpoint that dereferenced latest.occupancy_rate. This migration backfills NULL
rows to 0.0 and enforces NOT NULL, dialect-aware (direct ALTER for Postgres,
batch_alter_table for SQLite). price stays nullable by design.
"""

from alembic import op
import sqlalchemy as sa


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    # Backfill NULL occupancy_rate to 0.0 (plain DML, safe on both dialects).
    op.execute(
        "UPDATE occupancy_records SET occupancy_rate = 0.0 "
        "WHERE occupancy_rate IS NULL"
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE occupancy_records ALTER COLUMN occupancy_rate "
            "SET NOT NULL"
        )
    else:
        with op.batch_alter_table("occupancy_records") as batch_op:
            batch_op.alter_column(
                "occupancy_rate",
                existing_type=sa.Float(),
                nullable=False,
            )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE occupancy_records ALTER COLUMN occupancy_rate "
            "DROP NOT NULL"
        )
    else:
        with op.batch_alter_table("occupancy_records") as batch_op:
            batch_op.alter_column(
                "occupancy_rate",
                existing_type=sa.Float(),
                nullable=True,
            )
