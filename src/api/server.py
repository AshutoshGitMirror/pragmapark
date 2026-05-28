import os
import secrets
import time
import uuid
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path

from .routes.prediction import router as prediction_router
from .routes.pricing import router as pricing_router
from .routes.blockchain import router as blockchain_router
from .routes.digital_twin import router as digital_twin_router
from .routes.marl import router as marl_router
from .routes.auth import router as auth_router
from .routes.lots import router as lots_router
from .routes.revenue import router as revenue_router
from .routes.admin import router as admin_router
from .routes.sessions import router as sessions_router
from .routes.payments import router as payments_router
from .routes.driver import router as driver_router
from .routes.ingestion import router as ingestion_router
from .routes.micro import router as micro_router
from .database import run_migrations, get_db_cm
from .utils import RateLimiter, rehydrate_micro_state
from src.constants import GLOBAL_RATE_LIMIT_CALLS, GLOBAL_RATE_LIMIT_WINDOW, DB_INIT_MAX_RETRIES, MINER_INTERVAL_S, CLEANUP_INTERVAL_S, OUTBOX_INTERVAL_S, INGEST_INTERVAL_S, INGEST_RETRIES, SESSION_RUNNING, RESERVATION_ACTIVE, RESERVATION_EXPIRED

logger = logging.getLogger(__name__)

_INGEST_LOCK = asyncio.Lock()
_global_rate_limiter = RateLimiter(max_calls=GLOBAL_RATE_LIMIT_CALLS, window=GLOBAL_RATE_LIMIT_WINDOW)


def _periodic_loop(name, interval_s, fn, retries=0, lock=None, use_executor=False):
    async def _run():
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(interval_s)
            if lock and lock.locked():
                continue
            for attempt in range(retries + 1):
                try:
                    if use_executor:
                        await loop.run_in_executor(None, fn)
                    elif lock:
                        async with lock:
                            fn()
                    else:
                        fn()
                    break
                except Exception as e:
                    if attempt >= retries:
                        logger.error("Periodic[%s] failed: %s", name, e)
                    else:
                        logger.warning("Periodic[%s] retry %d/%d: %s", name, attempt + 1, retries, e)
                        await asyncio.sleep(5 * (2 ** attempt))
    return _run


def _log_slot_transition(slot_id, prev_state, new_state, driver_id=""):
    try:
        from src.api.database import SlotStateLog, MicroSlot
        from src.micro.predictor import slot_predictor
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        slot_predictor.record_transition(slot_id, prev_state, new_state, now)
        with get_db_cm() as db:
            slot = db.query(MicroSlot).filter(MicroSlot.id == slot_id).first()
            db.add(SlotStateLog(
                slot_id=slot_id, lot_id=slot.lot_id if slot else "",
                previous_state=prev_state, new_state=new_state, driver_id=driver_id,
                timestamp=now,
            ))
            db.commit()
    except Exception as e:
        logger.warning("Slot transition log failed: %s", e)


def _do_mining():
    from src.pipeline.orchestrator import pipeline as p
    if p.ledger.pending_transactions:
        block = p.ledger.mine_pending()
        p.ledger.save_to_file(p.bc_path)
        logger.info("Background miner: mined block %d (%d tx)", block.index, len(block.transactions))


def _do_cleanup():
    from src.api.database import OccupancyRecord, TokenBlacklist, PredictionMetric, SlotReservation
    from datetime import datetime, timedelta, timezone
    from src.constants import DATA_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=DATA_RETENTION_DAYS)
    with get_db_cm() as db:
        deleted_occ = db.query(OccupancyRecord).filter(OccupancyRecord.timestamp < cutoff).delete()
        deleted_pred = db.query(PredictionMetric).filter(PredictionMetric.timestamp < cutoff).delete()
        expired = db.query(TokenBlacklist).filter(TokenBlacklist.expires_at < datetime.now(timezone.utc)).delete()
        expired_res = db.query(SlotReservation).filter(
            SlotReservation.status == RESERVATION_ACTIVE,
            SlotReservation.expires_at < datetime.now(timezone.utc),
        ).update({"status": RESERVATION_EXPIRED}, synchronize_session=False)
        db.commit()
        if deleted_occ or deleted_pred or expired or expired_res:
            logger.info("Cleanup: removed %d occupancy, %d predictions, %d expired tokens, %d expired reservations", deleted_occ, deleted_pred, expired, expired_res)


def _do_outbox():
    from src.pipeline.orchestrator import pipeline as p
    from src.api.ledger_outbox import process_pending
    with get_db_cm() as db:
        try:
            processed = process_pending(db, p)
            if processed:
                logger.info("Outbox flush processed %d pending ledger entries", processed)
        except Exception:
            db.rollback()
            logger.error("event=periodic.outbox.failed")
            raise


_last_ingest_hash: str = ""

def _do_ingest():
    from src.pipeline.orchestrator import pipeline as p
    from src.api.database import ParkingLot, OccupancyRecord
    global _last_ingest_hash
    with get_db_cm() as db:
        rows = db.query(ParkingLot.lot_id, ParkingLot.total_slots).order_by(ParkingLot.lot_id).all()
        current_hash = str([(r.lot_id, r.total_slots) for r in rows])
        if current_hash == _last_ingest_hash:
            return
        _last_ingest_hash = current_hash
        for row in rows:
            db.add(OccupancyRecord(**p.simulate_ingest(db, row)))
        db.commit()
        logger.info("event=periodic.ingest.completed lots=%d", len(rows))


def _seed_startup():
    import random, uuid, hashlib, os
    from datetime import datetime, timedelta, timezone
    from src.api.database import User, ParkingLot, OccupancyRecord, Transaction, RevenueRecord, ParkingSession, PredictionMetric, LedgerOutbox
    from src.api.auth import hash_password
    from src.pipeline.orchestrator import pipeline as pl
    try:
        with get_db_cm() as db:
            # ── Users ──────────────────────────────────────────────
            users = {}
            for email, pw, name, role, org in [
                ("admin@pragma.io", "admin123", "Platform Admin", "admin", "Pragma Systems"),
                ("owner@pragma.io", "owner123", "Jane Lotowner", "lot_owner", "Downtown Parking LLC"),
            ] + [(f"driver{d}@demo.io", "demo123", f"Demo Driver {d}", "driver", "") for d in range(1, 6)]:
                u = db.query(User).filter(User.email == email).first()
                if not u:
                    u = User(email=email, hashed_password=hash_password(pw), full_name=name, role=role, organization=org)
                    db.add(u); db.flush()
                    logger.info("Seed: user %s (%s)", email, role)
                users[email] = u
            db.commit()
            admin_id = db.query(User.id).filter(User.email == "admin@pragma.io").scalar()
            owner_id = db.query(User.id).filter(User.email == "owner@pragma.io").scalar()
            driver_ids = [str(db.query(User.email).filter(User.email == f"driver{d}@demo.io").scalar() or f"driver{d}@demo.io") for d in range(1, 6)]

            # ── Lots ───────────────────────────────────────────────
            owner_lots = {"A1", "A2", "B1", "L1", "SF1", "SG1"}
            lots_data = [
                ("A1","Downtown Plaza","123 Main St",500,52.48,-1.89,15.0,"Birmingham",50.0),
                ("A2","Station Approach","45 Railway Rd",350,52.47,-1.90,12.0,"Birmingham",45.0),
                ("B1","Market Square","78 Market St",200,52.48,-1.88,10.0,"Birmingham",30.0),
                ("L1","Canary Wharf Garage","1 Bank St",800,51.50,-0.02,25.0,"London",80.0),
                ("L2","King's Cross","90 Euston Rd",600,51.53,-0.12,20.0,"London",65.0),
                ("M1","Deansgate","50 Deansgate",400,53.48,-2.25,14.0,"Manchester",40.0),
                ("M2","Piccadilly Tower","1 Piccadilly",300,53.48,-2.24,12.0,"Manchester",35.0),
                ("NY1","Times Square Hub","1 Times Sq",1000,40.76,-73.98,35.0,"New York",120.0),
                ("NY2","Madison Ave Garage","200 Madison Ave",500,40.75,-73.98,30.0,"New York",100.0),
                ("SF1","Financial District","300 California St",600,37.79,-122.40,28.0,"San Francisco",90.0),
                ("SF2","Mission Lot","500 Mission St",350,37.76,-122.40,22.0,"San Francisco",75.0),
                ("TK1","Shibuya Central","2-1 Dogenzaka",300,35.66,139.70,30.0,"Tokyo",100.0),
                ("TK2","Shinjuku Tower","1-1-1 Nishi-Shinjuku",400,35.69,139.70,28.0,"Tokyo",90.0),
                ("DB1","Dubai Mall Lot","Financial Center Rd",1500,25.20,55.27,40.0,"Dubai",150.0),
                ("DB2","Marina Park","Dubai Marina",700,25.08,55.14,35.0,"Dubai",120.0),
                ("SG1","Orchard Road","333A Orchard Rd",500,1.30,103.83,22.0,"Singapore",60.0),
                ("SG2","Marina Bay","10 Bayfront Ave",600,1.28,103.86,26.0,"Singapore",70.0),
                ("MB1","BKC Lot","Bandra Kurla Complex",700,19.07,72.87,12.0,"Mumbai",30.0),
                ("MB2","Nariman Point","1 Nariman Point",400,18.93,72.82,10.0,"Mumbai",25.0),
                ("BR1","Potsdamer Platz","Potsdamer Str 1",500,52.51,13.37,18.0,"Berlin",50.0),
                ("BR2","Alexanderplatz","Alexanderplatz 1",400,52.52,13.41,16.0,"Berlin",45.0),
            ]
            now = datetime.now(timezone.utc)
            lot_ids = []
            for lot_id, name, addr, slots, lat, lng, price, city, cap in lots_data:
                lot = db.query(ParkingLot).filter(ParkingLot.lot_id == lot_id).first()
                if lot:
                    lot_ids.append(lot_id)
                    continue
                oid = owner_id if lot_id in owner_lots else admin_id
                lot = ParkingLot(lot_id=lot_id, name=name, address=addr, city=city, total_slots=slots, latitude=lat, longitude=lng, base_price=price, price_cap=cap, owner_id=oid)
                db.add(lot); db.flush()
                lot_ids.append(lot_id)
                logger.info("Seed: lot %s (%s)", lot_id, name)

            # ── Historical occupancy (90 days, time-aware) ─────────
            def _occ_for_hour(h, is_weekend):
                if is_weekend:
                    if 0 <= h < 6: return random.uniform(0.05, 0.15)
                    if 6 <= h < 9: return random.uniform(0.10, 0.30)
                    if 9 <= h < 12: return random.uniform(0.30, 0.55)
                    if 12 <= h < 15: return random.uniform(0.45, 0.70)
                    if 15 <= h < 18: return random.uniform(0.50, 0.75)
                    if 18 <= h < 21: return random.uniform(0.40, 0.65)
                    return random.uniform(0.15, 0.35)
                else:
                    if 0 <= h < 6: return random.uniform(0.05, 0.12)
                    if 6 <= h < 8: return random.uniform(0.10, 0.40)
                    if 8 <= h < 10: return random.uniform(0.60, 0.90)
                    if 10 <= h < 13: return random.uniform(0.65, 0.85)
                    if 13 <= h < 15: return random.uniform(0.45, 0.70)
                    if 15 <= h < 17: return random.uniform(0.50, 0.75)
                    if 17 <= h < 19: return random.uniform(0.70, 0.95)
                    if 19 <= h < 22: return random.uniform(0.40, 0.70)
                    return random.uniform(0.10, 0.30)

            for lid in lot_ids:
                lot_obj = db.query(ParkingLot).filter(ParkingLot.lot_id == lid).first()
                if not lot_obj: continue
                bp = float(lot_obj.base_price)
                ts = lot_obj.total_slots
                db.query(PredictionMetric).filter(PredictionMetric.lot_id == lid).delete()
                db.query(ParkingSession).filter(ParkingSession.lot_id == lid).delete()
                db.query(RevenueRecord).filter(RevenueRecord.lot_id == lid).delete()
                db.query(Transaction).filter(Transaction.lot_id == lid).delete()
                db.query(OccupancyRecord).filter(OccupancyRecord.lot_id == lid).delete()
                for days_ago in range(90):
                    for h in range(6, 23, 2):
                        d = now - timedelta(days=days_ago)
                        is_weekend = d.weekday() >= 5
                        occ = _occ_for_hour(h, is_weekend) * random.uniform(0.85, 1.15)
                        occ = min(max(occ, 0.02), 0.98)
                        ts_record = d.replace(hour=h, minute=random.randint(0, 59), second=0, microsecond=0)
                        op = ts_record
                        flux = random.uniform(-8, 8)
                        price_adj = round(bp * (1 + (occ - 0.5) * 0.6), 2)
                        occupied = int(round(occ * ts))
                        db.add(OccupancyRecord(lot_id=lid, occupied_slots=occupied, total_slots=ts, occupancy_rate=round(occ, 3), net_flux=round(flux, 2), price=price_adj, timestamp=ts_record))
                        db.add(Transaction(tx_hash=f"0x{uuid.uuid4().hex}", lot_id=lid, driver_id=f"driver_{random.randint(1,200)}", action="park", amount=round(price_adj * random.uniform(0.5, 2.5), 2), duration_minutes=random.randint(30, 240), timestamp=ts_record))
                        daily_key = op.replace(hour=0, minute=0, second=0, microsecond=0)
                        db.add(RevenueRecord(lot_id=lid, date=daily_key, total_transactions=random.randint(30, 300), total_revenue=round(price_adj * random.randint(30, 300), 2), avg_price=price_adj, avg_occupancy=round(occ, 3)))
                logger.info("Seed: %s history (90d)", lid)
            db.commit()
            logger.info("Seed: history complete")

            # ── Active parking sessions (20) ───────────────────────
            lot_pool = list(lot_ids)
            for i in range(20):
                lid = random.choice(lot_pool)
                did = driver_ids[i % len(driver_ids)]
                slot_num = random.randint(1, 20)
                start_offset = random.randint(10, 180)
                start = now - timedelta(minutes=start_offset)
                entry_price = float(db.query(ParkingLot.base_price).filter(ParkingLot.lot_id == lid).scalar() or 10)
                sid = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
                db.add(ParkingSession(session_id=sid, lot_id=lid, driver_id=did, slot=slot_num, start_time=start, entry_price=entry_price, status="running", payment_method=random.choice(["card", "wallet", "upi"])))
                db.add(PredictionMetric(lot_id=lid, session_id=sid, predicted_occupancy=round(random.uniform(0.3, 0.9), 3), model_version="rf+xgb_ensemble_v2"))
            db.commit()
            logger.info("Seed: 20 active sessions")

        # ── Blockchain pre-mine (3 blocks) ─────────────────────────
        _bc_lot_ids = db.query(ParkingLot.lot_id).all()
        _bc_lot_ids = [r[0] for r in _bc_lot_ids]
        for b in range(3):
            for _ in range(30):
                pl.ledger.add_transaction({"type": "session_fee", "session_id": hashlib.sha256(os.urandom(32)).hexdigest()[:16], "lot_id": random.choice(_bc_lot_ids), "driver_id": f"driver_{b}_{random.randint(1,100)}", "action": "park", "amount": round(random.uniform(5, 50), 2)})
            pl.ledger.mine_pending()
        pl.ledger.save_to_file(pl.bc_path)
        logger.info("Seed: pre-mined 3 blocks (%d total)", len(pl.ledger.chain))
    except Exception as e:
        logger.warning("Startup seed skipped: %s", e)
        import traceback; traceback.print_exc()
    try:
        from scripts.seed_micro import seed as seed_micro
        seed_micro()
    except (Exception, SystemExit) as e:
        logger.warning("Micro slot auto-seed skipped: %s", e)
    rehydrate_micro_state()

@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(DB_INIT_MAX_RETRIES):
        try:
            run_migrations()
            logger.info("Database initialized successfully")
            break
        except Exception as e:
            logger.warning("DB init attempt %d/%d failed: %s", attempt + 1, DB_INIT_MAX_RETRIES, e)
            if attempt < DB_INIT_MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                logger.critical("All DB init attempts failed, starting without DB")
                raise
    from src.pipeline.orchestrator import pipeline
    logger.info("Blockchain loaded: %d blocks, %d pending tx", len(pipeline.ledger.chain), len(pipeline.ledger.pending_transactions))
    _seed_startup()
    from src.micro.state_engine import slot_state_engine
    slot_state_engine.on_transition(_log_slot_transition)
    try:
        from src.api.database import MicroSlot
        from src.micro.predictor import slot_predictor
        with get_db_cm() as _pw_db:
            _all_slots = _pw_db.query(MicroSlot.id).all()
            for (sid,) in _all_slots:
                slot_predictor.predict(sid)
            if _all_slots:
                logger.info("Pre-warmed slot predictor for %d slots", len(_all_slots))
    except Exception as e:
        logger.warning("Slot predictor pre-warm skipped: %s", e)

    tasks = [
        asyncio.create_task(_periodic_loop("miner", MINER_INTERVAL_S, _do_mining, use_executor=True)()),
        asyncio.create_task(_periodic_loop("cleanup", CLEANUP_INTERVAL_S, _do_cleanup)()),
        asyncio.create_task(_periodic_loop("outbox", OUTBOX_INTERVAL_S, _do_outbox)()),
        asyncio.create_task(_periodic_loop("ingest", INGEST_INTERVAL_S, _do_ingest, retries=INGEST_RETRIES, lock=_INGEST_LOCK)()),
    ]
    yield
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    try:
        from src.pipeline.orchestrator import pipeline as p
        if p.ledger.pending_transactions:
            p.ledger.mine_pending()
            p.ledger.save_to_file(p.bc_path)
            logger.info("event=shutdown.blockchain.flushed pending=%d", len(p.ledger.pending_transactions))
    except Exception as e:
        logger.error("event=shutdown.blockchain.failed error=%s", e)


app = FastAPI(
    title="Pragma Smart Parking API",
    description="Startup-Grade Smart Parking Management Platform",
    version="2.0.0",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")]
cors_allow_creds = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
if ALLOWED_ORIGINS == ["*"]:
    cors_allow_creds = False
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=cors_allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

_API_PREFIXES = ("/api/",)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        if not _global_rate_limiter.check(f"global:{client_ip}"):
            return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    return await call_next(request)

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-Id", uuid.uuid4().hex[:12])
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
    return response

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    nonce = secrets.token_hex(16)
    request.state.nonce = nonce
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Content-Security-Policy"] = f"default-src 'self'; script-src 'self' 'nonce-{nonce}' 'strict-dynamic'; style-src 'self' 'unsafe-inline'; img-src 'self' https://*.tile.openstreetmap.org data:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests"
    if response.headers.get("server"):
        del response.headers["server"]
    path = request.url.path
    if any(path.startswith(p) for p in _API_PREFIXES):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    else:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    logger.warning("Validation error req=%s path=%s: %s", getattr(request.state, "request_id", "unknown"), request.url.path, errors)
    return JSONResponse(status_code=422, content={"detail": "Invalid request input", "errors": errors})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "unknown")
    logger.error("Unhandled exception req=%s path=%s: %s", req_id, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": req_id})


app.include_router(prediction_router)
app.include_router(pricing_router)
app.include_router(blockchain_router)
app.include_router(digital_twin_router)
app.include_router(marl_router)
app.include_router(auth_router)
app.include_router(lots_router)
app.include_router(revenue_router)
app.include_router(admin_router)
app.include_router(sessions_router)
app.include_router(payments_router)
app.include_router(driver_router)
app.include_router(ingestion_router)
app.include_router(micro_router)

dashboard_dir = Path(__file__).parent.parent / "dashboard"
static_dir = dashboard_dir / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_app(request: Request):
    html_path = dashboard_dir / "templates" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text().replace("__NONCE__", request.state.nonce))
    return HTMLResponse("<h1>Pragma Smart Parking</h1><p>Dashboard not found</p>")

ALLOWED_PAGES = {"index", "dashboard", "driver", "admin", "login", "app"}

@app.get("/app/{page_name:path}", response_class=HTMLResponse, include_in_schema=False)
async def serve_page(request: Request, page_name: str):
    clean_name = page_name.strip("/").replace("/", "_").split(".")[0]
    if clean_name not in ALLOWED_PAGES:
        return HTMLResponse("<h1>Page not found</h1>", status_code=404)
    html_path = dashboard_dir / "templates" / f"{clean_name}.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text().replace("__NONCE__", request.state.nonce))
    return HTMLResponse("<h1>Page not found</h1>", status_code=404)


def _readiness():
    db_ok = bc_ok = models_ok = False
    try:
        with get_db_cm() as db:
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
            db_ok = True
    except Exception as e:
        logger.warning("event=readiness.database.failed error=%s", e)
    try:
        from src.pipeline.orchestrator import pipeline
        bc_ok = pipeline is not None and len(pipeline.ledger.chain) > 0
        pipeline._ensure_models()
        models_ok = pipeline.predictor.rf is not None and pipeline.predictor.xgb is not None
    except Exception as e:
        logger.warning("event=readiness.blockchain_or_models.failed error=%s", e)
    return {"ready": db_ok and bc_ok and models_ok, "database": db_ok,
            "blockchain": bc_ok, "models_loaded": models_ok, "uptime_seconds": time.monotonic()}


@app.get("/api/v1/health")
async def health():
    r = _readiness()
    return {
        "status": "healthy" if r["ready"] else "degraded",
        "service": "pragma", "version": "2.0.0", "layers": 6,
        "dependencies": {"database": r["database"], "blockchain": r["blockchain"]},
    }

@app.get("/api/v1/ready")
async def ready():
    return _readiness()
