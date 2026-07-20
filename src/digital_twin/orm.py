"""Durable, persisted digital-twin models.

These replace the in-memory / deque-based state that previously lived inside
``src/digital_twin/simulator.py``. Every record is persisted to the database so
the twin survives restarts (no singleton / in-memory-only state).

Design rules (see project goal):
* A ``TwinObservation`` is the only real evidence of occupancy. It is never
  produced by the simulator.
* A ``TwinForecast`` is immutable once written: the later observed outcome is
  attached as a *separate* column (``actual_occupancy`` / ``error_*``) and the
  original prediction is never overwritten (principle 2).
* ``TwinScenarioRun`` records whether its prediction came from a deterministic
  rule or a learned model, and never mutates production (principle 8).
* ``TwinModelVersion`` is the provenance record for every forecasting model so
  evaluation can be attributed to a concrete artifact version (principle 2).
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.api.database import Base


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TwinObservation(Base):
    """A single observed snapshot of a parking lot (the real evidence)."""

    __tablename__ = "twin_observations"

    id = Column(Integer, primary_key=True)
    lot_id = Column(
        String(50),
        ForeignKey("parking_lots.lot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observed_at = Column(DateTime, nullable=False, index=True)
    occupancy_rate = Column(Float, nullable=False)
    occupied_slots = Column(Integer, nullable=False)
    total_slots = Column(Integer, nullable=False)
    arrivals = Column(Integer, default=0)
    departures = Column(Integer, default=0)
    price = Column(Float, default=0.0)
    sensor_confidence = Column(Float, default=1.0)
    source = Column(String(50), default="iot", nullable=False)
    context = Column(Text, default="")  # weather / event flags, JSON-encoded

    __table_args__ = (
        UniqueConstraint("lot_id", "observed_at", name="uq_twin_obs_lot_time"),
        Index("ix_twin_obs_lot_time", "lot_id", "observed_at"),
    )


class TwinState(Base):
    """Estimated current state of a lot, derived from observations."""

    __tablename__ = "twin_states"

    id = Column(Integer, primary_key=True)
    lot_id = Column(
        String(50),
        ForeignKey("parking_lots.lot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    state_at = Column(DateTime, nullable=False, index=True)
    est_occupancy_rate = Column(Float, nullable=False)
    est_available_slots = Column(Integer, nullable=False)
    est_price = Column(Float, default=0.0)
    congestion_level = Column(Float, default=0.0)
    resident_share_count = Column(Integer, default=0)
    confidence = Column(Float, default=0.0)
    source_observation_id = Column(
        Integer,
        ForeignKey("twin_observations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("lot_id", "state_at", name="uq_twin_state_lot_time"),
    )


class TwinForecast(Base):
    """A persisted forecast. Immutable: actual outcome is attached, never overwrites."""

    __tablename__ = "twin_forecasts"

    id = Column(Integer, primary_key=True)
    lot_id = Column(
        String(50),
        ForeignKey("parking_lots.lot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generated_at = Column(DateTime, nullable=False, index=True)
    target_at = Column(DateTime, nullable=False, index=True)
    horizon_minutes = Column(Integer, nullable=False, index=True)
    predicted_occupancy_rate = Column(Float, nullable=False)
    # Quantile / interval forecast (calibration, principle 2).
    lower_occupancy_rate = Column(Float, nullable=True)
    upper_occupancy_rate = Column(Float, nullable=True)
    model_name = Column(String(50), nullable=False)
    model_version = Column(String(50), nullable=False)
    feature_version = Column(String(50), default="unknown")
    input_observation_id = Column(
        Integer,
        ForeignKey("twin_observations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Outcome columns -- populated when a later observation lands. The original
    # prediction above is NEVER overwritten (so the link is auditable).
    actual_occupancy_rate = Column(Float, nullable=True)
    evaluated_at = Column(DateTime, nullable=True)
    error = Column(Float, nullable=True)  # actual - predicted (signed)
    abs_error = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_twin_fc_lot_target", "lot_id", "target_at"),
    )


class TwinScenarioRun(Base):
    """A what-if scenario evaluation. Never mutates production (principle 8)."""

    __tablename__ = "twin_scenario_runs"

    id = Column(Integer, primary_key=True)
    lot_id = Column(
        String(50),
        ForeignKey("parking_lots.lot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, index=True)
    scenario_type = Column(String(50), nullable=False)
    params = Column(Text, default="{}")  # JSON-encoded intervention parameters
    random_seed = Column(Integer, nullable=True)
    # Determinism classification (principle 4): 'deterministic' rule-based vs
    # 'learned' model-based. Rule-based outputs must NOT be called learned.
    kind = Column(String(20), default="deterministic", nullable=False)
    model_version = Column(String(50), nullable=True)
    predicted_occupancy_rate = Column(Float, nullable=True)
    predicted_price = Column(Float, nullable=True)
    lower_occupancy_rate = Column(Float, nullable=True)
    upper_occupancy_rate = Column(Float, nullable=True)
    assumptions = Column(Text, default="")
    uncertainty_note = Column(Text, default="")
    safety_note = Column(Text, default="")
    base_state_ref = Column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_twin_scen_lot_type", "lot_id", "scenario_type"),
    )


class TwinModelVersion(Base):
    """Provenance + validation record for a forecasting model artifact."""

    __tablename__ = "twin_model_versions"

    id = Column(Integer, primary_key=True)
    model_name = Column(String(50), nullable=False, index=True)
    artifact_version = Column(String(50), nullable=False)
    training_data_cutoff = Column(DateTime, nullable=True)
    feature_schema_version = Column(String(50), default="unknown")
    # Validation metrics, JSON-encoded (MAE/RMSE/coverage by horizon).
    validation_metrics = Column(Text, default="{}")
    promotion_status = Column(String(20), default="candidate", nullable=False)
    is_baseline = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            "model_name", "artifact_version", name="uq_twin_model_name_ver"
        ),
    )


# Relationship hints (optional; kept minimal to avoid import cycles at module load).
TwinObservation.derived_states = relationship(
    "TwinState", backref="observation", foreign_keys=[TwinState.source_observation_id]
)
TwinObservation.derived_forecasts = relationship(
    "TwinForecast", backref="input_observation",
    foreign_keys=[TwinForecast.input_observation_id]
)
