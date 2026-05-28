from fastapi import APIRouter, Depends
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from src.api.database import get_db, ParkingLot, OccupancyRecord, Transaction, RevenueRecord, User
from src.api.auth import get_current_user
from src.api.utils import require_admin
from src.api.schemas import SystemHealthResponse, DashboardResponse

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

@router.get("/dashboard", response_model=DashboardResponse)
async def admin_dashboard(user: dict = Depends(get_current_user), session = Depends(get_db)):
    require_admin(user)
    total_lots = session.query(ParkingLot).count()
    total_users = session.query(User).count()
    total_revenue = session.query(func.sum(RevenueRecord.total_revenue)).scalar() or 0
    total_tx = session.query(Transaction).count()
    latest_occ = session.query(OccupancyRecord).order_by(
        OccupancyRecord.timestamp.desc()
    ).first()
    return DashboardResponse(
        total_lots=total_lots,
        total_users=total_users,
        total_revenue=round(total_revenue, 2),
        total_transactions=total_tx,
        system_occupancy=latest_occ.occupancy_rate if latest_occ else 0,
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
    return SystemHealthResponse(
        status="healthy" if recent_occ > 0 else "degraded",
        transactions_last_hour=recent_tx,
        occupancy_updates_last_5min=recent_occ,
        layers={
            "iot": "operational" if recent_occ > 0 else "no_data",
            "ml": "operational",
            "blockchain": "operational",
            "rl": "operational",
            "digital_twin": "simulated",
            "api": "operational",
        },
    )
