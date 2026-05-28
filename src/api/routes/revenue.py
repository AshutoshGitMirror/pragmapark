from typing import List
from fastapi import APIRouter, Query, Depends
from datetime import datetime, timedelta, timezone
from sqlalchemy import func as sa_func
from src.api.database import get_db, RevenueRecord, ParkingLot, Transaction, ParkingSession, User
from src.api.auth import get_current_user
from src.api.utils import require_admin
from src.api.schemas import RevenueOverviewResponse, RevenueOverviewItem, TransactionHistoryItem, RevenueCumulativeResponse

router = APIRouter(prefix="/api/v1/revenue", tags=["Revenue"])

@router.get("/cumulative", response_model=RevenueCumulativeResponse)
async def revenue_cumulative(user: dict = Depends(get_current_user), session = Depends(get_db)):
    require_admin(user)
    total_revenue = session.query(sa_func.coalesce(sa_func.sum(RevenueRecord.total_revenue), 0)).scalar()
    total_sessions = session.query(sa_func.count(ParkingSession.id)).scalar() or 0
    total_lots = session.query(sa_func.count(ParkingLot.id)).scalar() or 0
    total_drivers = session.query(sa_func.count(User.id)).scalar() or 0
    avg_rev_per_session = round(total_revenue / total_sessions, 2) if total_sessions else 0.0
    avg_rev_per_lot = round(total_revenue / total_lots, 2) if total_lots else 0.0
    return RevenueCumulativeResponse(
        total_revenue=round(float(total_revenue), 2),
        total_sessions=total_sessions, total_lots=total_lots,
        total_drivers=total_drivers,
        avg_revenue_per_session=avg_rev_per_session,
        avg_revenue_per_lot=avg_rev_per_lot,
    )


@router.get("/overview", response_model=RevenueOverviewResponse)
async def revenue_overview(days: int = Query(30, ge=1, le=365), user: dict = Depends(get_current_user), session = Depends(get_db)):
    require_admin(user)
    cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    records = session.query(RevenueRecord).filter(RevenueRecord.date >= cutoff).limit(1000).all()
    by_lot = {}
    for r in records:
        key = r.lot_id
        if key not in by_lot:
            by_lot[key] = {"revenue": 0, "transactions": 0, "days": 0}
        by_lot[key]["revenue"] += r.total_revenue
        by_lot[key]["transactions"] += r.total_transactions
        by_lot[key]["days"] += 1
    result = []
    if by_lot:
        lots = session.query(ParkingLot).filter(ParkingLot.lot_id.in_(list(by_lot.keys()))).all()
        lot_map = {lot.lot_id: lot.name for lot in lots}
        for lot_id, data in by_lot.items():
            result.append(RevenueOverviewItem(
                lot_id=lot_id,
                name=lot_map.get(lot_id, lot_id),
                total_revenue=round(data["revenue"], 2),
                total_transactions=data["transactions"],
                avg_daily_revenue=round(data["revenue"] / max(data["days"], 1), 2),
            ))
    result = sorted(result, key=lambda x: x.total_revenue, reverse=True)
    total_revenue = sum(r.total_revenue for r in result)
    total_transactions = sum(r.total_transactions for r in result)
    return RevenueOverviewResponse(
        total_revenue=total_revenue,
        total_transactions=total_transactions,
        daily=result,
    )

@router.get("/transactions", response_model=List[TransactionHistoryItem])
async def list_transactions(offset: int = Query(0, ge=0, description="Number of records to skip"),
                            limit: int = Query(50, ge=1, le=500, description="Max records to return"),
                            user: dict = Depends(get_current_user),
                            session = Depends(get_db)):
    require_admin(user)
    txs = session.query(Transaction).order_by(
        Transaction.timestamp.desc()
    ).offset(offset).limit(limit).all()
    return [
        TransactionHistoryItem(
            tx_hash=t.tx_hash, lot_id=t.lot_id, driver_id=t.driver_id,
            action=t.action, amount=t.amount, duration_minutes=t.duration_minutes,
            status=t.status, timestamp=t.timestamp.isoformat(),
        )
        for t in txs
    ]
