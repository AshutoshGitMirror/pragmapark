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
from .database import init_db, run_migrations, get_session
from .utils import RateLimiter
from src.constants import GLOBAL_RATE_LIMIT_CALLS, GLOBAL_RATE_LIMIT_WINDOW, DB_INIT_MAX_RETRIES, MINER_INTERVAL_S, CLEANUP_INTERVAL_S, OUTBOX_INTERVAL_S, INGEST_INTERVAL_S, INGEST_RETRIES, LAYER_NAMES, SESSION_RUNNING, SESSION_CANCELLED, RESERVATION_ACTIVE, RESERVATION_EXPIRED

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


def _rehydrate_micro_state():
    try:
        from src.api.database import SlotReservation
        from src.api.database import get_session as _re_session
        from datetime import datetime, timezone
        from src.micro.state_engine import slot_state_engine

        db = _re_session()
        try:
            now = datetime.now(timezone.utc)
            active = db.query(SlotReservation).filter(
                SlotReservation.status == RESERVATION_ACTIVE,
                SlotReservation.expires_at > now,
            ).all()
            recovered = 0
            for res in active:
                remaining_s = max(int((res.expires_at - now).total_seconds()), 1)
                if slot_state_engine.reserve(res.slot_id, res.driver_id, remaining_s):
                    recovered += 1
            if recovered:
                logger.info("Rehydrated %d/%d active reservations into state engine", recovered, len(active))
        finally:
            db.close()
    except ImportError:
        logger.warning("Micro state engine unavailable, skipping rehydration")
    except Exception as e:
        logger.warning("Micro state rehydration skipped: %s", e)


def _log_slot_transition(slot_id, prev_state, new_state, driver_id=""):
    try:
        from src.api.database import get_session, SlotStateLog, MicroSlot
        from src.micro.predictor import slot_predictor
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        slot_predictor.record_transition(slot_id, prev_state, new_state, now)
        db = get_session()
        try:
            slot = db.query(MicroSlot).filter(MicroSlot.id == slot_id).first()
            db.add(SlotStateLog(
                slot_id=slot_id, lot_id=slot.lot_id if slot else "",
                previous_state=prev_state, new_state=new_state, driver_id=driver_id,
                timestamp=now,
            ))
            db.commit()
        finally:
            db.close()
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
    db = get_session()
    try:
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
    except Exception:
        db.rollback()
        logger.error("event=periodic.cleanup.failed")
        raise
    finally:
        db.close()


def _do_outbox():
    from src.api.database import get_session as db_session
    from src.pipeline.orchestrator import pipeline as p
    from src.api.ledger_outbox import process_pending
    db = db_session()
    try:
        processed = process_pending(db, p)
        if processed:
            logger.info("Outbox flush processed %d pending ledger entries", processed)
    except Exception:
        db.rollback()
        logger.error("event=periodic.outbox.failed")
        raise
    finally:
        db.close()


_last_ingest_hash: str = ""

def _do_ingest():
    from src.pipeline.orchestrator import pipeline as p
    from src.api.database import ParkingLot, OccupancyRecord
    from datetime import datetime, timezone
    from sqlalchemy import func, text
    global _last_ingest_hash
    db = get_session()
    try:
        rows = db.query(ParkingLot.lot_id, ParkingLot.total_slots).order_by(ParkingLot.lot_id).all()
        current_hash = str([(r.lot_id, r.total_slots) for r in rows])
        if current_hash == _last_ingest_hash:
            return
        _last_ingest_hash = current_hash
        for row in rows:
            db.add(OccupancyRecord(**p.simulate_ingest(db, row)))
        db.commit()
        logger.info("event=periodic.ingest.completed lots=%d", len(rows))
    except Exception:
        db.rollback()
        logger.error("event=periodic.ingest.failed")
        raise
    finally:
        db.close()


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
    try:
        from src.api.database import ParkingSession
        from src.api.database import get_session as db_session
        from datetime import datetime, timezone
        recovery_db = db_session()
        try:
            stale = recovery_db.query(ParkingSession).filter(
                ParkingSession.status == SESSION_RUNNING,
            ).count()
            if stale:
                logger.info("Startup: found %d active sessions in DB (no action taken)", stale)
        finally:
            recovery_db.close()
    except Exception as e:
        logger.warning("Startup session check skipped: %s", e)
    from src.pipeline.orchestrator import pipeline
    logger.info("Blockchain loaded: %d blocks, %d pending tx", len(pipeline.ledger.chain), len(pipeline.ledger.pending_transactions))
    try:
        from scripts.seed_micro import seed as seed_micro
        seed_micro()
    except (Exception, SystemExit) as e:
        logger.warning("Micro slot auto-seed skipped: %s", e)
    _rehydrate_micro_state()
    from src.micro.state_engine import slot_state_engine
    slot_state_engine.on_transition(_log_slot_transition)
    try:
        from src.api.database import MicroSlot, get_session as _pw_session
        from src.micro.predictor import slot_predictor
        _pw_db = _pw_session()
        try:
            _all_slots = _pw_db.query(MicroSlot.id).all()
            for (sid,) in _all_slots:
                slot_predictor.predict(sid)
            if _all_slots:
                logger.info("Pre-warmed slot predictor for %d slots", len(_all_slots))
        finally:
            _pw_db.close()
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
    db = None
    try:
        db = get_session()
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.warning("event=readiness.database.failed error=%s", e)
    finally:
        if db:
            db.close()
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
