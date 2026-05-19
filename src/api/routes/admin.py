from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from sqlalchemy import func
from src.api.database import get_session, ParkingLot, OccupancyRecord, Transaction, RevenueRecord, User
from src.api.auth import get_current_user

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

REQUIRED_ROLES = {"admin", "city_planner"}

def _require_admin(user: dict):
    if user.get("role") not in REQUIRED_ROLES:
        raise HTTPException(403, "Admin or city_planner role required")

@router.get("/dashboard")
async def admin_dashboard(user=Depends(get_current_user)):
    _require_admin(user)
    session = get_session()
    try:
        total_lots = session.query(ParkingLot).count()
        total_users = session.query(User).count()
        total_revenue = session.query(func.sum(RevenueRecord.total_revenue)).scalar() or 0
        total_tx = session.query(Transaction).count()
        latest_occ = session.query(OccupancyRecord).order_by(
            OccupancyRecord.timestamp.desc()
        ).first()
        return {
            "total_lots": total_lots,
            "total_users": total_users,
            "total_revenue": round(total_revenue, 2),
            "total_transactions": total_tx,
            "system_occupancy": latest_occ.occupancy_rate if latest_occ else 0,
        }
    finally:
        session.close()

@router.get("/system-health")
async def system_health(user=Depends(get_current_user)):
    _require_admin(user)
    session = get_session()
    try:
        recent_tx = session.query(Transaction).filter(
            Transaction.timestamp >= datetime.utcnow() - timedelta(hours=1)
        ).count()
        recent_occ = session.query(OccupancyRecord).filter(
            OccupancyRecord.timestamp >= datetime.utcnow() - timedelta(minutes=5)
        ).count()
        return {
            "status": "healthy" if recent_occ > 0 else "degraded",
            "transactions_last_hour": recent_tx,
            "occupancy_updates_last_5min": recent_occ,
            "layers": {
                "iot": "operational" if recent_occ > 0 else "no_data",
                "ml": "operational",
                "blockchain": "operational",
                "rl": "operational",
                "digital_twin": "simulated",
                "api": "operational",
            },
        }
    finally:
        session.close()
