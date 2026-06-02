from fastapi import APIRouter, Depends
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from src.api.database import get_db, ParkingLot, OccupancyRecord, Transaction, RevenueRecord, User
from src.api.auth import get_current_user
from src.api.utils import require_admin
from src.api.schemas import SystemHealthResponse, DashboardResponse
from src.pipeline.orchestrator import pipeline

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

@router.get("/dashboard", response_model=DashboardResponse)
async def admin_dashboard(user: dict = Depends(get_current_user), session = Depends(get_db)):
    require_admin(user)
    total_lots = session.query(ParkingLot).count()
    total_users = session.query(User).count()
    total_revenue = session.query(func.sum(RevenueRecord.total_revenue)).scalar() or 0
    total_tx = session.query(Transaction).count()
    latest_per_lot = session.query(
        OccupancyRecord.lot_id,
        func.max(OccupancyRecord.timestamp).label('max_ts'),
    ).group_by(OccupancyRecord.lot_id).subquery()
    latest_occs = session.query(OccupancyRecord).join(
        latest_per_lot,
        (OccupancyRecord.lot_id == latest_per_lot.c.lot_id) &
        (OccupancyRecord.timestamp == latest_per_lot.c.max_ts),
    ).all()
    avg_occupancy = sum(o.occupancy_rate for o in latest_occs) / max(len(latest_occs), 1) if latest_occs else 0
    return DashboardResponse(
        total_lots=total_lots,
        total_users=total_users,
        total_revenue=round(total_revenue, 2),
        total_transactions=total_tx,
        system_occupancy=round(avg_occupancy, 1),
    )

@router.get("/system-health", response_model=SystemHealthResponse)
async def system_health(user: dict = Depends(get_current_user), session = Depends(get_db)):
    require_admin(user)
    cutoff_hour = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_tx = session.query(Transaction).filter(
        Transaction.timestamp >= cutoff_hour
    ).count()
    cutoff_5min = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent_occ = session.query(OccupancyRecord).filter(
        OccupancyRecord.timestamp >= cutoff_5min
    ).count()
    # probe subsystems for real status
    bc_valid = pipeline.ledger.validate_chain() if pipeline.ledger else False
    import os
    ml_status = "operational" if os.path.isdir(os.path.join(os.path.dirname(__file__), '..', 'models', 'artifacts')) else "no_model"
    rl_status = "operational" if hasattr(pipeline, 'rl') and pipeline.rl else "no_model"
    iot_status = "operational" if recent_occ > 0 else "no_data"
    overall = "healthy" if recent_occ > 0 and recent_tx >= 0 else "degraded"
    return SystemHealthResponse(
        status=overall,
        transactions_last_hour=recent_tx,
        occupancy_updates_last_5min=recent_occ,
        layers={
            "iot": iot_status,
            "ml": ml_status,
            "blockchain": "operational" if bc_valid else "corrupt",
            "rl": rl_status,
            "digital_twin": "simulated",
            "api": "operational",
        },
    )
