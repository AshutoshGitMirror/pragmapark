from typing import List
from fastapi import APIRouter, Query, Depends
from datetime import datetime, timedelta, timezone
from sqlalchemy import func as sa_func
from src.api.database import (
    get_db,
    RevenueRecord,
    ParkingLot,
    Transaction,
    ParkingSession,
    User,
)
from src.api.auth import get_current_user
from src.api.utils import require_admin
from src.api.schemas import (
    RevenueOverviewResponse,
    RevenueOverviewItem,
    DailyRevenueItem,
    RevenueByLotItem,
    TransactionHistoryItem,
    RevenueCumulativeResponse,
)

router = APIRouter(prefix="/api/v1/revenue", tags=["Revenue"])


@router.get("/cumulative", response_model=RevenueCumulativeResponse)
async def revenue_cumulative(
    user: dict = Depends(get_current_user), session=Depends(get_db)
):
    require_admin(user)
    total_revenue = session.query(
        sa_func.coalesce(sa_func.sum(RevenueRecord.total_revenue), 0)
    ).scalar()
    total_sessions = (
        session.query(sa_func.count(ParkingSession.id)).scalar() or 0
    )
    total_lots = session.query(sa_func.count(ParkingLot.id)).scalar() or 0
    total_drivers = (
        session.query(sa_func.count(User.id))
        .filter(User.role == "driver")
        .scalar()
        or 0
    )
    avg_rev_per_session = (
        round(total_revenue / total_sessions, 2) if total_sessions else 0.0
    )
    avg_rev_per_lot = (
        round(total_revenue / total_lots, 2) if total_lots else 0.0
    )
    return RevenueCumulativeResponse(
        total_revenue=round(float(total_revenue), 2),
        total_sessions=total_sessions,
        total_lots=total_lots,
        total_drivers=total_drivers,
        avg_revenue_per_session=avg_rev_per_session,
        avg_revenue_per_lot=avg_rev_per_lot,
    )


@router.get("/overview", response_model=RevenueOverviewResponse)
async def revenue_overview(
    days: int = Query(30, ge=1, le=365),
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    require_admin(user)
    cutoff = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=days)
    records = (
        session.query(RevenueRecord).filter(RevenueRecord.date >= cutoff).all()
    )
    by_day = {}
    by_lot = {}
    for r in records:
        day = r.date.date() if hasattr(r.date, "date") else r.date
        day_str = str(day)
        lot_id = str(r.lot_id)
        rev = float(r.total_revenue)
        txns = r.total_transactions
        by_day.setdefault(day_str, {"revenue": 0, "transactions": 0})
        by_day[day_str]["revenue"] += rev
        by_day[day_str]["transactions"] += txns
        by_lot.setdefault(
            lot_id, {"revenue": 0, "transactions": 0, "dates": set()})
        by_lot[lot_id]["revenue"] += rev
        by_lot[lot_id]["transactions"] += txns
        by_lot[lot_id]["dates"].add(day)
    daily_revenue = sorted(
        [
            DailyRevenueItem(date=d, revenue=round(
                v["revenue"], 2), transactions=v["transactions"])
            for d, v in by_day.items()
        ],
        key=lambda x: x.date,
    )
    revenue_by_lot = []
    if by_lot:
        lots = (
            session.query(ParkingLot)
            .filter(ParkingLot.lot_id.in_(list(by_lot.keys())))
            .all()
        )
        lot_map = {str(lot.lot_id): lot.name for lot in lots}
        for lot_id, data in by_lot.items():
            revenue_by_lot.append(
                RevenueByLotItem(
                    lot_id=lot_id,
                    name=lot_map.get(lot_id, lot_id),
                    revenue=round(data["revenue"], 2),
                    transactions=data["transactions"],
                )
            )
    revenue_by_lot = sorted(
        revenue_by_lot, key=lambda x: x.revenue, reverse=True)
    total_revenue = sum(r.revenue for r in revenue_by_lot)
    total_transactions = sum(r.transactions for r in revenue_by_lot)
    period_revenue = sum(d.revenue for d in daily_revenue)
    period_transactions = sum(d.transactions for d in daily_revenue)
    return RevenueOverviewResponse(
        total_revenue=total_revenue,
        total_transactions=total_transactions,
        period_revenue=round(period_revenue, 2),
        period_transactions=period_transactions,
        daily_revenue=daily_revenue,
        revenue_by_lot=revenue_by_lot,
        daily=[
            RevenueOverviewItem(
                lot_id=x.lot_id,
                name=x.name,
                total_revenue=x.revenue,
                total_transactions=x.transactions,
                avg_daily_revenue=round(
                    x.revenue / max(len(by_lot.get(x.lot_id, {}).get("dates", set())), 1), 2),
            )
            for x in revenue_by_lot
        ],
    )


@router.get("/transactions", response_model=List[TransactionHistoryItem])
async def list_transactions(
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    user: dict = Depends(get_current_user),
    session=Depends(get_db),
):
    require_admin(user)
    txs = (
        session.query(Transaction)
        .order_by(Transaction.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        TransactionHistoryItem(
            tx_hash=t.tx_hash,
            lot_id=t.lot_id,
            driver_id=t.driver_id,
            action=t.action,
            amount=t.amount,
            duration_minutes=t.duration_minutes,
            status=t.status,
            timestamp=t.timestamp.replace(tzinfo=timezone.utc).isoformat(),
        )
        for t in txs
    ]
