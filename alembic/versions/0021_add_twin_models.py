"""add digital-twin durable models (observations, state, forecasts, scenarios, model versions)

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-20

These tables back the observation-driven, persistent digital twin. They replace
the previous in-memory / deque state in src/digital_twin/simulator.py. Every
forecast is immutable (later observed outcome is stored separately, never
overwrites the prediction). No singleton / in-memory-only state.
"""

from alembic import op
import sqlalchemy as sa


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "twin_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lot_id", sa.String(50), sa.ForeignKey("parking_lots.lot_id"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("occupancy_rate", sa.Float(), nullable=False),
        sa.Column("occupied_slots", sa.Integer(), nullable=False),
        sa.Column("total_slots", sa.Integer(), nullable=False),
        sa.Column("arrivals", sa.Integer(), server_default="0"),
        sa.Column("departures", sa.Integer(), server_default="0"),
        sa.Column("price", sa.Float(), server_default="0.0"),
        sa.Column("sensor_confidence", sa.Float(), server_default="1.0"),
        sa.Column("source", sa.String(50), server_default="iot", nullable=False),
        sa.Column("context", sa.Text(), server_default=""),
        sa.UniqueConstraint("lot_id", "observed_at", name="uq_twin_obs_lot_time"),
    )
    op.create_index(
        "ix_twin_obs_lot_time", "twin_observations", ["lot_id", "observed_at"]
    )

    op.create_table(
        "twin_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lot_id", sa.String(50), sa.ForeignKey("parking_lots.lot_id"),
            nullable=False,
        ),
        sa.Column("state_at", sa.DateTime(), nullable=False),
        sa.Column("est_occupancy_rate", sa.Float(), nullable=False),
        sa.Column("est_available_slots", sa.Integer(), nullable=False),
        sa.Column("est_price", sa.Float(), server_default="0.0"),
        sa.Column("congestion_level", sa.Float(), server_default="0.0"),
        sa.Column("resident_share_count", sa.Integer(), server_default="0"),
        sa.Column("confidence", sa.Float(), server_default="0.0"),
        sa.Column(
            "source_observation_id", sa.Integer(),
            sa.ForeignKey("twin_observations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("lot_id", "state_at", name="uq_twin_state_lot_time"),
    )
    op.create_index("ix_twin_state_lot_time", "twin_states", ["lot_id", "state_at"])

    op.create_table(
        "twin_forecasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lot_id", sa.String(50), sa.ForeignKey("parking_lots.lot_id"),
            nullable=False,
        ),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("target_at", sa.DateTime(), nullable=False),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False),
        sa.Column("predicted_occupancy_rate", sa.Float(), nullable=False),
        sa.Column("lower_occupancy_rate", sa.Float(), nullable=True),
        sa.Column("upper_occupancy_rate", sa.Float(), nullable=True),
        sa.Column("model_name", sa.String(50), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("feature_version", sa.String(50), server_default="unknown"),
        sa.Column(
            "input_observation_id", sa.Integer(),
            sa.ForeignKey("twin_observations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actual_occupancy_rate", sa.Float(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Float(), nullable=True),
        sa.Column("abs_error", sa.Float(), nullable=True),
    )
    op.create_index("ix_twin_fc_lot_target", "twin_forecasts", ["lot_id", "target_at"])
    op.create_index("ix_twin_fc_generated", "twin_forecasts", ["generated_at"])
    op.create_index("ix_twin_fc_horizon", "twin_forecasts", ["horizon_minutes"])

    op.create_table(
        "twin_scenario_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lot_id", sa.String(50), sa.ForeignKey("parking_lots.lot_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("scenario_type", sa.String(50), nullable=False),
        sa.Column("params", sa.Text(), server_default="{}"),
        sa.Column("random_seed", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(20), server_default="deterministic", nullable=False),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("predicted_occupancy_rate", sa.Float(), nullable=True),
        sa.Column("predicted_price", sa.Float(), nullable=True),
        sa.Column("lower_occupancy_rate", sa.Float(), nullable=True),
        sa.Column("upper_occupancy_rate", sa.Float(), nullable=True),
        sa.Column("assumptions", sa.Text(), server_default=""),
        sa.Column("uncertainty_note", sa.Text(), server_default=""),
        sa.Column("safety_note", sa.Text(), server_default=""),
        sa.Column("base_state_ref", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_twin_scen_lot_type", "twin_scenario_runs", ["lot_id", "scenario_type"]
    )

    op.create_table(
        "twin_model_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(50), nullable=False),
        sa.Column("artifact_version", sa.String(50), nullable=False),
        sa.Column("training_data_cutoff", sa.DateTime(), nullable=True),
        sa.Column("feature_schema_version", sa.String(50), server_default="unknown"),
        sa.Column("validation_metrics", sa.Text(), server_default="{}"),
        sa.Column("promotion_status", sa.String(20), server_default="candidate", nullable=False),
        sa.Column("is_baseline", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "model_name", "artifact_version", name="uq_twin_model_name_ver"
        ),
    )
    op.create_index("ix_twin_model_name", "twin_model_versions", ["model_name"])


def downgrade():
    op.drop_table("twin_model_versions")
    op.drop_table("twin_scenario_runs")
    op.drop_table("twin_forecasts")
    op.drop_table("twin_states")
    op.drop_table("twin_observations")
