"""twin metrics + backtest columns (created_at, evaluation_outcome, latency_ms)

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-20

Closes the remaining gaps from the transformation plan's Required Metrics:
* twin_observations.created_at  -> audit timestamp for real evidence.
* twin_scenario_runs.evaluation_outcome -> backtest outcome when a comparable
  real event later materialises (persisted, never auto-applied).
* twin_scenario_runs.latency_ms -> scenario latency (Required Metric).

Dialect-aware: direct ALTER for Postgres, batch_alter_table for SQLite. The
new not-null column is backfilled deterministically (created_at <- observed_at)
so existing rows stay valid.
"""

from alembic import op
import sqlalchemy as sa


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    op.add_column(
        "twin_observations",
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_twin_obs_created_at", "twin_observations", ["created_at"]
    )
    # Backfill created_at from the real observation timestamp (always present).
    op.execute(
        "UPDATE twin_observations SET created_at = observed_at "
        "WHERE created_at IS NULL"
    )
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE twin_observations ALTER COLUMN created_at SET NOT NULL"
        )
    else:
        with op.batch_alter_table("twin_observations") as batch_op:
            batch_op.alter_column(
                "created_at", existing_type=sa.DateTime(), nullable=False
            )

    op.add_column(
        "twin_scenario_runs",
        sa.Column("evaluation_outcome", sa.Text(), server_default=""),
    )
    op.add_column(
        "twin_scenario_runs",
        sa.Column("latency_ms", sa.Float(), nullable=True),
    )


def downgrade():
    bind = op.get_bind()

    op.drop_column("twin_scenario_runs", "latency_ms")
    op.drop_column("twin_scenario_runs", "evaluation_outcome")

    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE twin_observations ALTER COLUMN created_at DROP NOT NULL"
        )
    else:
        with op.batch_alter_table("twin_observations") as batch_op:
            batch_op.alter_column(
                "created_at", existing_type=sa.DateTime(), nullable=True
            )
    op.drop_index("ix_twin_obs_created_at", table_name="twin_observations")
    op.drop_column("twin_observations", "created_at")
