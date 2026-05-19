from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime, timedelta
from src.api.database import get_session, RevenueRecord, ParkingLot, OccupancyRecord, Transaction
from src.api.auth import get_current_user

router = APIRouter(prefix="/api/v1/revenue", tags=["Revenue"])

@router.get("/overview")
async def revenue_overview(days: int = Query(30, ge=1, le=365), user=Depends(get_current_user)):
    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        records = session.query(RevenueRecord).filter(
            RevenueRecord.date >= cutoff
        ).all()
        lots = session.query(ParkingLot).all()
        total_revenue = sum(r.total_revenue for r in records)
        total_transactions = sum(r.total_transactions for r in records)
        return {
            "total_revenue": round(total_revenue, 2),
            "total_transactions": total_transactions,
            "avg_daily_revenue": round(total_revenue / max(len(records), 1), 2),
            "active_lots": len(lots),
            "daily": [
                {"date": r.date.isoformat(), "revenue": r.total_revenue,
                 "transactions": r.total_transactions, "avg_occupancy": r.avg_occupancy}
                for r in sorted(records, key=lambda x: x.date, reverse=True)[:30]
            ],
        }
    finally:
        session.close()

@router.get("/by-lot")
async def revenue_by_lot(days: int = Query(30, ge=1, le=365), user=Depends(get_current_user)):
    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        records = session.query(RevenueRecord).filter(RevenueRecord.date >= cutoff).all()
        by_lot = {}
        for r in records:
            key = r.lot_id
            if key not in by_lot:
                by_lot[key] = {"revenue": 0, "transactions": 0, "days": 0}
            by_lot[key]["revenue"] += r.total_revenue
            by_lot[key]["transactions"] += r.total_transactions
            by_lot[key]["days"] += 1
        result = []
        for lot_id, data in by_lot.items():
            lot = session.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
            result.append({
                "lot_id": lot_id,
                "name": lot.name if lot else lot_id,
                "total_revenue": round(data["revenue"], 2),
                "total_transactions": data["transactions"],
                "avg_daily_revenue": round(data["revenue"] / max(data["days"], 1), 2),
            })
        return sorted(result, key=lambda x: x["total_revenue"], reverse=True)
    finally:
        session.close()

@router.get("/transactions")
async def list_transactions(limit: int = Query(50, ge=1, le=500), user=Depends(get_current_user)):
    session = get_session()
    try:
        txs = session.query(Transaction).order_by(
            Transaction.timestamp.desc()
        ).limit(limit).all()
        return [
            {
                "tx_hash": t.tx_hash, "lot_id": t.lot_id, "driver_id": t.driver_id,
                "action": t.action, "amount": t.amount, "duration_minutes": t.duration_minutes,
                "status": t.status, "timestamp": t.timestamp.isoformat(),
            }
            for t in txs
        ]
    finally:
        session.close()
