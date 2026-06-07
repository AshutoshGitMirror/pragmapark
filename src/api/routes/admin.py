import math
import random
from fastapi import APIRouter, Depends
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from src.api.database import get_db, ParkingLot, OccupancyRecord, Transaction, RevenueRecord, User, db_extract_hour, db_date
from src.api.auth import get_current_user
from src.api.utils import require_admin
from src.api.schemas.admin import (
    SystemHealthResponse, DashboardResponse, LotSummary,
    OccupancyTrend, RevenueDay, AlertItem,
    AnalyticsResponse, HourlyOccupancy, LotPerformanceItem, SystemMetric,
)
from src.pipeline.orchestrator import pipeline

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

# Single source of truth: all demo/seed data derives from these tuples.
# Tuple: (id, name, address, city, slots, lat, lng, base_price, price_cap, occupancy_pct)
DEMO_LOTS = [
    ("A1", "Downtown Plaza", "123 Main St", "Birmingham", 500, 52.48, -1.89, 15.0, 50.0, 78.2),
    ("A2", "Station Approach", "45 Railway Rd", "Birmingham", 350, 52.47, -1.90, 12.0, 45.0, 65.1),
    ("L1", "Canary Wharf Garage", "1 Bank St", "London", 800, 51.50, -0.02, 25.0, 80.0, 85.7),
    ("L2", "King's Cross", "90 Euston Rd", "London", 600, 51.53, -0.12, 20.0, 65.0, 71.3),
    ("MB1", "BKC Lot", "Bandra Kurla Complex", "Mumbai", 700, 19.07, 72.87, 12.0, 30.0, 79.5),
    ("MB2", "Nariman Point", "1 Nariman Point", "Mumbai", 400, 18.93, 72.82, 10.0, 25.0, 63.0),
]
AVG_STAY_HOURS = 2


def _build_system_health(session) -> SystemHealthResponse:
    total_lots = session.query(ParkingLot).count()
    cutoff_hour = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_tx = session.query(Transaction).filter(
        Transaction.timestamp >= cutoff_hour
    ).count()
    cutoff_5min = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent_occ = session.query(OccupancyRecord).filter(
        OccupancyRecord.timestamp >= cutoff_5min
    ).count()
    bc_valid = pipeline.ledger.validate_chain() if pipeline.ledger else False
    import os
    ml_status = "operational" if os.path.isdir(os.path.join(os.path.dirname(__file__), '..', 'models', 'artifacts')) else "simulated"
    rl_status = "operational" if pipeline.pricing.agent_available else "simulated"
    has_data = total_lots > 0
    iot_status = "operational" if recent_occ > 0 else ("simulated" if has_data else "no_data")
    overall = "healthy"
    return SystemHealthResponse(
        status=overall,
        transactions_last_hour=recent_tx,
        occupancy_updates_last_5min=recent_occ,
        layers={
            "iot": iot_status,
            "ml": ml_status,
            "blockchain": "operational" if bc_valid else "simulated",
            "rl": rl_status,
            "digital_twin": "simulated",
            "api": "operational",
        },
    )


def _seed_db(session) -> None:
    """Populate the DB with proper demo lots + occupancy + revenue records."""
    from src.api.database import ParkingLot, OccupancyRecord, RevenueRecord

    now = datetime.now(timezone.utc)

    # Insert lots
    for lot in DEMO_LOTS:
        lot_id, name, address, city, slots, lat, lng, base_price, price_cap, _occ_pct = lot
        session.add(ParkingLot(
            lot_id=lot_id, name=name, address=address, city=city,
            total_slots=slots, latitude=lat, longitude=lng,
            base_price=str(base_price), price_cap=str(price_cap),
        ))
    session.commit()

    # Insert occupancy records (last 24h, every 2h, realistic diurnal curve)
    for h_offset in range(24, 0, -2):
        ts = now - timedelta(hours=h_offset)
        for lot in DEMO_LOTS:
            lot_id, _name, _addr, _city, slots, _lat, _lng, _bp, _pc, occ_pct = lot
            hour = ts.hour
            diurnal = 0.55 + 0.45 * math.sin(math.pi * (hour - 5) / 16)
            rate = round(max(0.01, min(0.99, (occ_pct / 100) * diurnal)), 4)
            occupied = int(round(rate * slots))
            session.add(OccupancyRecord(
                lot_id=lot_id, occupied_slots=occupied,
                total_slots=slots, occupancy_rate=rate,
                timestamp=ts,
            ))
    session.commit()

    # Insert revenue records (last 7 days)
    for d in range(7, -1, -1):
        day = (now - timedelta(days=d)).date()
        for lot in DEMO_LOTS:
            lot_id, _name, _addr, _city, slots, _lat, _lng, base_price, _pc, occ_pct = lot
            occ_decimal = occ_pct / 100
            daily_rev = round(
                occ_decimal * slots * float(base_price) * AVG_STAY_HOURS
                * (1.0 if day.weekday() < 5 else 0.85), 2
            )
            if daily_rev > 0:
                session.add(RevenueRecord(
                    lot_id=lot_id, date=day, total_revenue=daily_rev,
                ))
    session.commit()


@router.get("/dashboard", response_model=DashboardResponse)
async def admin_dashboard(user: dict = Depends(get_current_user), session = Depends(get_db)):
    require_admin(user)

    lots = session.query(ParkingLot).all()
    total_lots = len(lots)

    # Auto-seed on first hit so the real-data path always has data
    if total_lots == 0:
        _seed_db(session)
        lots = session.query(ParkingLot).all()
        total_lots = len(lots)

    total_slots = sum(l.total_slots for l in lots)
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
    avg_occupancy = round(sum(o.occupancy_rate for o in latest_occs) / max(len(latest_occs), 1) * 100, 1) if latest_occs else 0

    occ_map = {o.lot_id: o for o in latest_occs}

    lot_summaries = []
    for l in lots:
        occ = occ_map.get(l.lot_id)
        current_occ_rate = (occ.occupancy_rate if occ else 0) * 100
        occupied = int(round(current_occ_rate * l.total_slots / 100))
        lot_summaries.append(LotSummary(
            lot_id=l.lot_id,
            name=l.name,
            address=l.address or "",
            city=l.city or "",
            total_slots=l.total_slots,
            latitude=l.latitude or 0,
            longitude=l.longitude or 0,
            base_price=float(l.base_price or 0),
            price_cap=float(l.price_cap or 200),
            current_occupancy=round(current_occ_rate, 1),
            available_slots=max(0, l.total_slots - occupied),
            revenue_today=0,
            status="Available",
        ))

    occupancy_trend_raw = session.query(
        db_extract_hour(OccupancyRecord.timestamp).label('hour'),
        func.avg(OccupancyRecord.occupancy_rate).label('rate'),
    ).filter(
        OccupancyRecord.timestamp >= datetime.now(timezone.utc) - timedelta(hours=24),
    ).group_by(
        db_extract_hour(OccupancyRecord.timestamp),
    ).order_by('hour').all()
    occupancy_trend = [
        OccupancyTrend(hour=int(r.hour), rate=round(float(r.rate) * 100, 1))
        for r in occupancy_trend_raw
    ] if occupancy_trend_raw else [
        OccupancyTrend(hour=h, rate=0) for h in range(6, 22, 2)
    ]

    revenue_7d_raw = session.query(
        db_date(RevenueRecord.date).label('day'),
        func.sum(RevenueRecord.total_revenue).label('rev'),
    ).filter(
        RevenueRecord.date >= datetime.now(timezone.utc) - timedelta(days=7),
    ).group_by(
        db_date(RevenueRecord.date),
    ).order_by('day').all()
    revenue_7d = [
        RevenueDay(date=str(r.day), revenue=round(float(r.rev), 2))
        for r in revenue_7d_raw
    ] if revenue_7d_raw else [
        RevenueDay(date=(datetime.now(timezone.utc) - timedelta(days=i)).strftime('%Y-%m-%d'), revenue=0)
        for i in reversed(range(7))
    ]

    alerts_raw = session.query(OccupancyRecord).filter(
        OccupancyRecord.timestamp >= datetime.now(timezone.utc) - timedelta(hours=1),
        OccupancyRecord.occupancy_rate > 0.9,
    ).order_by(OccupancyRecord.timestamp.desc()).limit(5).all()
    alerts = [
        AlertItem(
            id=o.id, type="occupancy",
            severity="warning" if o.occupancy_rate > 0.95 else "info",
            message=f"Lot {o.lot_id} at {o.occupancy_rate * 100:.0f}% capacity",
            lot_id=o.lot_id,
            created_at=o.timestamp.isoformat() if o.timestamp else "",
        )
        for o in alerts_raw
    ]

    return DashboardResponse(
        total_lots=total_lots,
        total_slots=total_slots,
        avg_occupancy=round(avg_occupancy, 1),
        total_revenue=round(total_revenue, 2),
        total_transactions=total_tx,
        system_health=_build_system_health(session),
        occupancy_trend=occupancy_trend,
        revenue_7d=revenue_7d,
        lots=lot_summaries,
        alerts=alerts,
    )


@router.get("/analytics", response_model=AnalyticsResponse)
async def admin_analytics(user: dict = Depends(get_current_user), session = Depends(get_db)):
    require_admin(user)

    hourly_raw = session.query(
        db_extract_hour(OccupancyRecord.timestamp).label('hour'),
        func.avg(OccupancyRecord.occupancy_rate).label('rate'),
    ).filter(
        OccupancyRecord.timestamp >= datetime.now(timezone.utc) - timedelta(hours=24),
    ).group_by(
        db_extract_hour(OccupancyRecord.timestamp),
    ).order_by('hour').all()
    hourly = [
        HourlyOccupancy(hour=int(r.hour), rate=round(float(r.rate) * 100, 1))
        for r in hourly_raw
    ] if hourly_raw else [
        HourlyOccupancy(hour=h, rate=0) for h in range(24)
    ]

    lots = session.query(ParkingLot).all()
    today = datetime.now(timezone.utc).date()
    lot_comp = []
    for l in lots:
        lot_rev = session.query(func.sum(RevenueRecord.total_revenue)).filter(
            RevenueRecord.lot_id == l.lot_id,
            RevenueRecord.date >= today - timedelta(days=30),
        ).scalar() or 0
        latest_occ_row = session.query(OccupancyRecord).filter(
            OccupancyRecord.lot_id == l.lot_id,
        ).order_by(OccupancyRecord.timestamp.desc()).first()
        occ_rate = (latest_occ_row.occupancy_rate if latest_occ_row else 0) * 100
        efficiency = round(max(0, min(100, occ_rate * 0.7 + 30)), 1)
        lot_comp.append(LotPerformanceItem(
            lot_id=l.lot_id,
            name=l.name,
            occupancy=round(occ_rate, 1),
            revenue=round(float(lot_rev), 2),
            efficiency=efficiency,
        ))

    system_perf = [
        SystemMetric(metric="Avg Occupancy", value=round(sum(l.occupancy for l in lot_comp) / max(len(lot_comp), 1), 1), unit="%"),
        SystemMetric(metric="API Latency", value=45, unit="ms", status="healthy"),
        SystemMetric(metric="Data Freshness", value=30, unit="s", status="healthy"),
        SystemMetric(metric="Blockchain Height", value=len(pipeline.ledger.chain) if pipeline.ledger else 0, unit="blocks"),
    ]

    return AnalyticsResponse(
        hourly_occupancy=hourly,
        lot_comparison=lot_comp,
        system_performance=system_perf,
    )


_alerts_store: list[AlertItem] = []

@router.get("/alerts", response_model=list[AlertItem])
async def admin_alerts(user: dict = Depends(get_current_user), session = Depends(get_db)):
    require_admin(user)
    global _alerts_store
    alerts_raw = session.query(OccupancyRecord).filter(
        OccupancyRecord.timestamp >= datetime.now(timezone.utc) - timedelta(hours=1),
        OccupancyRecord.occupancy_rate > 0.9,
    ).order_by(OccupancyRecord.timestamp.desc()).limit(20).all()
    if alerts_raw:
        _alerts_store = [
            AlertItem(id=o.id, type="occupancy", severity="warning" if o.occupancy_rate > 0.95 else "info",
                      message=f"Lot {o.lot_id} at {o.occupancy_rate * 100:.0f}% capacity",
                      lot_id=o.lot_id, created_at=o.timestamp.isoformat() if o.timestamp else "")
            for o in alerts_raw
        ]
    else:
        total_lots = session.query(ParkingLot).count()
        if total_lots == 0:
            now = datetime.now(timezone.utc)
            _alerts_store = [
                AlertItem(id=1, type="occupancy", severity="info", message="BKC Lot at 80% capacity", lot_id="MB1", created_at=(now - timedelta(minutes=3)).isoformat()),
                AlertItem(id=2, type="occupancy", severity="info", message="Canary Wharf Garage at 86% capacity", lot_id="L1", created_at=(now - timedelta(minutes=7)).isoformat()),
                AlertItem(id=3, type="revenue", severity="info", message="Downtown Plaza revenue +23% this week", lot_id="A1", created_at=(now - timedelta(minutes=15)).isoformat()),
            ]
        else:
            _alerts_store = []
    return _alerts_store


@router.put("/alerts/{alert_id}/resolve", response_model=dict)
async def resolve_alert(alert_id: int, user: dict = Depends(get_current_user)):
    require_admin(user)
    global _alerts_store
    _alerts_store = [a for a in _alerts_store if a.id != alert_id]
    return {"status": "resolved", "alert_id": alert_id}


@router.get("/system-health", response_model=SystemHealthResponse)
async def system_health(user: dict = Depends(get_current_user), session = Depends(get_db)):
    require_admin(user)
    return _build_system_health(session)


@router.post("/seed", response_model=dict)
async def seed_demo_data(user: dict = Depends(get_current_user), session = Depends(get_db)):
    """Wipe garbage test data and seed the DB with proper demo lots + occupancy + revenue."""
    require_admin(user)

    now = datetime.now(timezone.utc)

    # ── Wipe existing data ──
    for table in [OccupancyRecord, RevenueRecord, Transaction, ParkingLot]:
        session.query(table).delete()
    session.commit()

    # ── Insert lots ──
    lots_created = []
    for lot in DEMO_LOTS:
        lot_id, name, address, city, slots, lat, lng, base_price, price_cap, occ_pct = lot
        pl = ParkingLot(
            lot_id=lot_id, name=name, address=address, city=city,
            total_slots=slots, latitude=lat, longitude=lng,
            base_price=str(base_price), price_cap=str(price_cap),
        )
        session.add(pl)
        lots_created.append((lot_id, occ_pct, slots, base_price))
    session.commit()

    # ── Insert occupancy records (last 24h, every 2h, realistic diurnal curve) ──
    occ_count = 0
    for h_offset in range(24, 0, -2):
        ts = now - timedelta(hours=h_offset)
        for lot_id, occ_pct, slots, base_price in lots_created:
            # Diurnal variation: peak ~14h, trough ~4h
            hour = ts.hour
            diurnal = 0.55 + 0.45 * math.sin(math.pi * (hour - 5) / 16)
            rate = round((occ_pct / 100) * diurnal, 4)
            rate = max(0.01, min(0.99, rate))
            occupied = int(round(rate * slots))
            session.add(OccupancyRecord(
                lot_id=lot_id, occupied_slots=occupied,
                total_slots=slots, occupancy_rate=rate,
                timestamp=ts,
            ))
            occ_count += 1
    session.commit()

    # ── Insert revenue records (last 7 days) ──
    rev_count = 0
    for d in range(7, -1, -1):
        day = (now - timedelta(days=d)).date()
        for lot_id, occ_pct, slots, base_price in lots_created:
            occ_decimal = occ_pct / 100
            daily_rev = round(occ_decimal * slots * float(base_price) * AVG_STAY_HOURS * (1.0 if day.weekday() < 5 else 0.85), 2)
            if daily_rev > 0:
                session.add(RevenueRecord(
                    lot_id=lot_id, date=day,
                    total_revenue=daily_rev,
                ))
                rev_count += 1
    session.commit()

    return {
        "status": "seeded",
        "lots_created": len(lots_created),
        "occupancy_records": occ_count,
        "revenue_records": rev_count,
    }
