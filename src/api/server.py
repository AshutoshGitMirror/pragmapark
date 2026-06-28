import os
import secrets
import uuid
import hashlib
import json
import logging
import sys
import asyncio
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from pathlib import Path
from sqlalchemy import text

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

from .routes.auth import router as auth_router
from .routes.lots import router as lots_router
from .routes.revenue import router as revenue_router
from .routes.wallet import router as wallet_router
from .routes.ingestion import router as ingestion_router
from .routes.micro import router as micro_router
from .routes.prediction import router as prediction_router
from .routes.pricing import router as pricing_router
from .routes.blockchain import router as blockchain_router
from .routes.digital_twin import router as digital_twin_router
from .routes.marl import router as marl_router
from .routes.sessions import router as sessions_router
from .routes.driver import router as driver_router
from .routes.admin import router as admin_router
from .routes.payments import router as payments_router
from .routes.simulation import router as simulation_router
from .routes.actuator import router as actuator_router
from .database import (
    run_migrations,
    get_db_cm,
    get_session,
    User,
    ParkingSession,
    MicroSlot,
    PrebookRecord,
    SlotReservation,
    Transaction,
)
from src.constants import TX_COMPLETED
from .utils import RateLimiter
from .auth import hash_password
from src.constants import (
    DB_INIT_MAX_RETRIES,
    MINER_INTERVAL_S,
    CLEANUP_INTERVAL_S,
    OUTBOX_INTERVAL_S,
    INGEST_INTERVAL_S,
    INGEST_RETRIES,
    SESSION_RUNNING,
    RESERVATION_ACTIVE,
    RESERVATION_CONFIRMED,
)
from src.pipeline.orchestrator import pipeline
from src.simulation.time_machine import time_machine
from src.api.workers import (
    _periodic_loop,
    _do_mining,
    _do_cleanup,
    _do_outbox,
    _do_ingest,
    _log_slot_transition as _log_slot_transition_impl,
)
from src.micro.state_engine import slot_state_engine
from src.micro.models import SlotState
from src.micro.predictor import slot_predictor

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

_BG_TASKS: list[asyncio.Task] = []


def _restart_background_tasks():
    for t in _BG_TASKS:
        t.cancel()
    _BG_TASKS.clear()
    speedup = max(1, time_machine.speedup)
    try:
        _BG_TASKS.extend(
            [
                asyncio.create_task(
                    _periodic_loop(
                        "miner",
                        max(1, MINER_INTERVAL_S // speedup),
                        _do_mining,
                        use_executor=True,
                    )()
                ),
                asyncio.create_task(
                    _periodic_loop(
                        "cleanup",
                        max(1, CLEANUP_INTERVAL_S // speedup),
                        _do_cleanup,
                    )()
                ),
                asyncio.create_task(
                    _periodic_loop(
                        "outbox",
                        max(1, OUTBOX_INTERVAL_S // speedup),
                        _do_outbox,
                    )()
                ),
                asyncio.create_task(
                    _periodic_loop(
                        "ingest",
                        max(1, INGEST_INTERVAL_S // speedup),
                        _do_ingest,
                        retries=INGEST_RETRIES,
                    )()
                ),
            ]
        )
        logger.info("event=tasks.restarted speedup=%d", speedup)
    except RuntimeError:
        logger.critical(
            "event=tasks.restart_failed speedup=%d "
            "Background pipeline (miner/cleanup/outbox/ingest) "
            "is NOT running",
            speedup,
            exc_info=True,
        )


def _log_slot_transition(slot_id, prev_s, new_s):
    """Stub — real persistence is in workers._log_slot_transition.
    The workers version is registered as the on_transition callback below."""
    logger.info("Slot %d: %s -> %s", slot_id, prev_s, new_s)


def _bootstrap_micro():
    """Sync SlotStateEngine + SlotPredictor from active DB parking sessions
    and prebook/reservation records. Without this, the state engine starts
    empty on every server restart and all micro slots show as AVAILABLE
    regardless of real occupancy.
    Restores three states: OCCUPIED (running sessions), PREBOOKED
    (active prebooks), and RESERVED (confirmed prebooks)."""
    try:
        db = get_session()
        boot_count = prob_count = 0

        # 1. OCCUPIED — currently running parking sessions
        running = (
            db.query(ParkingSession)
            .filter(
                ParkingSession.status == SESSION_RUNNING,
                ParkingSession.slot > 0,
            )
            .all()
        )
        for sess in running:
            slot = (
                db.query(MicroSlot)
                .filter(
                    MicroSlot.lot_id == sess.lot_id,
                    MicroSlot.slot_index == sess.slot,
                )
                .first()
            )
            if slot:
                slot_state_engine.set_state(slot.id, SlotState.OCCUPIED)
                boot_count += 1
                slot_predictor.predict(slot.id)
                prob_count += 1

        # 2. PREBOOKED — prebook records in 'active' state (not yet confirmed)
        active_prebooks = (
            db.query(PrebookRecord)
            .filter(
                PrebookRecord.status == RESERVATION_ACTIVE,
                PrebookRecord.slot_index > 0,
            )
            .all()
        )
        for pb in active_prebooks:
            # Avoid overwriting OCCUPIED from running session
            slot = (
                db.query(MicroSlot)
                .filter(
                    MicroSlot.lot_id == pb.lot_id,
                    MicroSlot.slot_index == pb.slot_index,
                )
                .first()
            )
            if (
                slot
                and slot_state_engine.get_state(slot.id) == SlotState.AVAILABLE
            ):
                slot_state_engine.set_state(slot.id, SlotState.PREBOOKED)
                boot_count += 1
                slot_predictor.predict(slot.id)
                prob_count += 1

        # 3. RESERVED — prebook records in 'confirmed' state (reservation
        # active)
        confirmed_prebooks = (
            db.query(PrebookRecord)
            .filter(
                PrebookRecord.status == RESERVATION_CONFIRMED,
                PrebookRecord.slot_index > 0,
            )
            .all()
        )
        for pb in confirmed_prebooks:
            slot = (
                db.query(MicroSlot)
                .filter(
                    MicroSlot.lot_id == pb.lot_id,
                    MicroSlot.slot_index == pb.slot_index,
                )
                .first()
            )
            # Avoid overwriting OCCUPIED — a running session may have started
            # on this slot
            if (
                slot
                and slot_state_engine.get_state(slot.id) == SlotState.AVAILABLE
            ):
                slot_state_engine.set_state(slot.id, SlotState.RESERVED)
                boot_count += 1
                slot_predictor.predict(slot.id)
                prob_count += 1

        # 4. RESERVED — SlotReservation records in 'active' state (micro-system
        # reservations)
        active_reservations = (
            db.query(SlotReservation)
            .filter(
                SlotReservation.status == RESERVATION_ACTIVE,
            )
            .all()
        )
        for sr in active_reservations:
            if slot_state_engine.get_state(sr.slot_id) == SlotState.AVAILABLE:
                slot_state_engine.set_state(sr.slot_id, SlotState.RESERVED)
                boot_count += 1
                slot_predictor.predict(sr.slot_id)
                prob_count += 1

        db.close()
        if boot_count or prob_count:
            logger.info(
                "event=micro.bootstrapped state=%d predictor=%d",
                boot_count,
                prob_count,
            )
    except Exception as e:
        logger.warning("event=micro.bootstrap.failed reason=%s", e)


def _bootstrap_blockchain():
    """Mine completed DB Transaction records into the in-memory blockchain
    ledger. Seed data creates Transaction ORM rows directly without adding
    them to the ledger's pending pool, so the blockchain stays at genesis
    block until this runs.
    Batches 50 transactions per block to keep PoW mining time reasonable."""
    try:
        db = get_session()
        completed = (
            db.query(Transaction)
            .filter(Transaction.status == TX_COMPLETED)
            .order_by(Transaction.id)
            .all()
        )
        if not completed:
            db.close()
            return

        existing_hashes = set()
        for block in pipeline.ledger.chain:
            for tx in block.transactions:
                h = tx.get("tx_hash") or tx.get("hash")
                if h:
                    existing_hashes.add(h)

        pending_add = [
            t for t in completed if t.tx_hash not in existing_hashes
        ]
        if not pending_add:
            db.close()
            logger.info(
                "event=blockchain.bootstrap.synced txns=%d", len(completed))
            return

        mined = 0
        BATCH = 50
        for i in range(0, len(pending_add), BATCH):
            batch = pending_add[i:i + BATCH]
            tx_list = [
                {
                    "db_id": t.id,
                    "tx_hash": t.tx_hash,
                    "driver_id": t.driver_id,
                    "lot_id": t.lot_id or "",
                    "action": t.action,
                    "amount": float(t.amount) if t.amount else 0.0,
                    "duration_minutes": t.duration_minutes or 0,
                    "session_id": t.session_id or "",
                    "timestamp": t.timestamp.replace(tzinfo=timezone.utc).isoformat() if t.timestamp else "",
                }
                for t in batch
            ]
            pipeline.ledger.add_transaction({
                "batch_hash": hashlib.sha256(
                    json.dumps(tx_list, sort_keys=True, default=str).encode()
                ).hexdigest(),
                "count": len(tx_list),
                "transactions": tx_list,
            })
            block = pipeline.ledger.mine_pending()
            ref = f"blk-{block.index}#{block.hash[:16]}"
            for t in batch:
                t.blockchain_ref = ref
            mined += len(batch)

        db.commit()
        db.close()
        pipeline.ledger.save_to_file(pipeline.bc_path)
        logger.info(
            "event=blockchain.bootstrap.completed blocks=%d txns=%d",
            pipeline.ledger.last_block.index,
            mined,
        )
    except Exception as e:
        logger.warning("event=blockchain.bootstrap.failed reason=%s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(DB_INIT_MAX_RETRIES):
        try:
            run_migrations()
            logger.info("Database initialized successfully")
            break
        except Exception as e:
            logger.warning(
                "DB init attempt %d/%d failed: %s",
                attempt + 1,
                DB_INIT_MAX_RETRIES,
                e,
            )
            if attempt < DB_INIT_MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
            else:
                logger.critical("All DB init attempts failed")
                raise

    try:
        time_machine.cleanup_stale_snapshots()
    except Exception:
        logger.warning("event=snapshot_cleanup_failed", exc_info=True)

    try:
        from src.api.database import AppLock, DB_URL

        if not DB_URL.startswith("sqlite"):
            with get_db_cm() as _s:
                if _s.query(AppLock).filter(AppLock.id == 1).first() is None:
                    _s.add(AppLock(id=1, name="orchestrator"))
                    _s.commit()
    except Exception:
        logger.warning("event=applock_seed_failed", exc_info=True)

    try:
        from src.api.database import ParkingSession
        from src.constants import SESSION_STALE_HOURS

        cutoff = datetime.now(timezone.utc) - \
            timedelta(hours=SESSION_STALE_HOURS)
        with get_db_cm() as _s:
            stale = (
                _s.query(ParkingSession)
                .filter(
                    ParkingSession.status == "running",
                    ParkingSession.start_time < cutoff,
                )
                .all()
            )
            for s in stale:
                s.status = "cancelled"
                s.end_time = datetime.now(timezone.utc).replace(tzinfo=None)
            if stale:
                _s.commit()
                logger.info(
                    "Auto-cancelled %d stale sessions (cutoff=%s)",
                    len(stale),
                    cutoff.isoformat(),
                )
    except Exception:
        logger.warning("event=stale_session_cleanup_failed", exc_info=True)

    # Wire up slot state transition logging: state engine → SlotStateLog
    # persistence
    slot_state_engine.on_transition(_log_slot_transition_impl)
    logger.info("event=slot_logger.registered")

    # Bootstrap in-memory state engine + predictor from active DB parking
    # sessions
    _bootstrap_micro()

    # No background model loading or blockchain bootstrap on cold start:
    # ML models (RF 30MB + XGB 1MB) load lazily on first prediction request,
    # and blockchain seed-data bootstrap is a one-off management operation.
    # Keeps cold-start within 512MB free tier budget — eager loading here
    # pushes memory over the limit and causes OOM kills within ~2 minutes.
    _restart_background_tasks()
    logger.info("Pragma service ready")
    yield

    for t in _BG_TASKS:
        t.cancel()
    await asyncio.gather(*_BG_TASKS, return_exceptions=True)


app = FastAPI(
    title="Pragma Smart Parking API",
    description="Startup-Grade Smart Parking Management Platform",
    version="2.0.0",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8080,http://localhost:8989,"
        "http://127.0.0.1:8989,https://ashutoshgitmirror.github.io,"
        "https://pragma-4szs.onrender.com",
    ).split(",")
]
cors_allow_creds = (
    os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
)
if ALLOWED_ORIGINS == ["*"]:
    cors_allow_creds = False
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=cors_allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

_global_rate_limiter = RateLimiter(
    max_calls=10000 if os.environ.get("PRAGMA_ENV") == "testing" else 100,
    window=60.0,
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        if not _global_rate_limiter.check(f"global:{client_ip}"):
            return JSONResponse(
                status_code=429, content={"detail": "Too many requests"}
            )
    return await call_next(request)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-Id", uuid.uuid4().hex[:12])
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
    return response


@app.middleware("http")
async def csrf_protection_middleware(request: Request, call_next):
    """Validate Origin header on state-changing requests to prevent CSRF.

    This works because:
    - All state-changing API requests from the SPA use
      Content-Type: application/json
      which triggers CORS preflight (OPTIONS) that the CORS middleware
      handles.
    - The actual POST/PUT/DELETE request includes an Origin header
      set by the browser.
    - An attacker's site cannot spoof the Origin header —
      the browser sets it.
    - We reject requests whose Origin doesn't match an allowed origin.
    - Same-origin requests (Origin absent or null/none) are allowed.
    """
    if request.method in (
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ) and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        # Allow missing Origin (same-origin requests from browser
        # tabs, curl, etc.)
        if origin:
            # Same-origin: if Origin matches own server host, always
            # allow. This prevents CSRF on any deployment domain
            # without manual whitelisting.
            server_origin = f"{request.url.scheme}://{request.url.hostname}"
            if request.url.port:
                server_origin += f":{request.url.port}"
            if origin == server_origin:
                allowed = True
            else:
                allowed = False
                for allowed_origin in ALLOWED_ORIGINS:
                    if allowed_origin == "*":
                        allowed = True
                        break
                    if origin == allowed_origin:
                        allowed = True
                        break
            if not allowed and origin != "null":
                logger.warning(
                    "event=csrf.rejected method=%s path=%s origin=%s",
                    request.method,
                    request.url.path,
                    origin,
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Cross-site request forbidden"},
                )
    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    nonce = secrets.token_hex(16)
    request.state.nonce = nonce
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "geolocation=(), camera=(), microphone=(), "
        "payment=(), usb=(), magnetometer=(), "
        "accelerometer=(), gyroscope=()"
    )
    spa_built = spa_dir.exists()
    if spa_built:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com "
            "https://unpkg.com https://api.fontshare.com "
            "https://fonts.googleapis.com; "
            "img-src 'self' https://*.tile.openstreetmap.org "
            "https://*.basemaps.cartocdn.com data: blob:; "
            "font-src 'self' data: https://cdnjs.cloudflare.com "
            "https://api.fontshare.com https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'; "
            "upgrade-insecure-requests"
        )
    else:
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' 'strict-dynamic'; "
            f"style-src 'self' 'unsafe-inline' "
            f"https://cdnjs.cloudflare.com https://unpkg.com "
            f"https://fonts.googleapis.com; "
            f"img-src 'self' https://*.tile.openstreetmap.org "
            f"https://*.basemaps.cartocdn.com data:; "
            f"font-src 'self' data: https://cdnjs.cloudflare.com "
            f"https://fonts.gstatic.com; "
            f"connect-src 'self'; "
            f"frame-ancestors 'none'; "
            f"base-uri 'self'; "
            f"form-action 'self'; "
            f"upgrade-insecure-requests"
        )
    if response.headers.get("server"):
        del response.headers["server"]
    if any(request.url.path.startswith(p) for p in ("/api/",)):
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, proxy-revalidate"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif "/assets/" in request.url.path and response.status_code == 200:
        # Content-hashed assets: cache forever
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
        )
    elif (
        request.url.path == "/"
        or request.url.path.startswith("/frontend/")
        or request.url.path.startswith("/app/")
        or request.url.path in (
            "/login", "/dashboard", "/lots", "/analytics",
            "/revenue", "/map", "/micro-slots", "/alerts", "/settings",
        )
    ):
        response.headers["Cache-Control"] = (
            "no-cache, no-store, must-revalidate"
        )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    errors = [
        {"loc": e["loc"], "msg": e["msg"], "type": e["type"]}
        for e in exc.errors()
    ]
    logger.warning(
        "Validation error req=%s path=%s: %s",
        getattr(request.state, "request_id", "unknown"),
        request.url.path,
        errors,
    )
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request input", "errors": errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "Unhandled exception req=%s path=%s: %s",
        req_id,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": req_id},
    )


app.include_router(auth_router)
app.include_router(lots_router)
app.include_router(revenue_router)
app.include_router(wallet_router)
app.include_router(ingestion_router)
app.include_router(micro_router)
app.include_router(prediction_router)
app.include_router(pricing_router)
app.include_router(blockchain_router)
app.include_router(digital_twin_router)
app.include_router(marl_router)
app.include_router(sessions_router)
app.include_router(driver_router)
app.include_router(admin_router)
app.include_router(payments_router)
app.include_router(simulation_router)
app.include_router(actuator_router)

spa_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
spa_assets_dir = spa_dir / "assets"
if spa_dir.exists() and spa_assets_dir.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(spa_assets_dir)),
        name="spa_assets",
    )
    app.mount(
        "/frontend",
        StaticFiles(directory=str(spa_dir), html=True),
        name="frontend",
    )

    @app.get("/favicon.svg", include_in_schema=False)
    async def serve_spa_favicon():
        favicon_path = spa_dir / "favicon.svg"
        if favicon_path.exists():
            return FileResponse(str(favicon_path), media_type="image/svg+xml")
        return HTMLResponse(status_code=404)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def serve_spa_root(request: Request):
        try:
            html = (spa_dir / "index.html").read_text()
        except FileNotFoundError:
            return HTMLResponse(
                "<h1>Frontend not built</h1>"
                "<p>Run <code>npm run build</code> "
                "in the frontend directory.</p>",
                status_code=503,
            )
        return HTMLResponse(html)

    @app.get(
        "/app/{full_path:path}",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    async def serve_spa_app(request: Request, full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404, content={"detail": "Not found"}
            )
        try:
            html = (spa_dir / "index.html").read_text()
        except FileNotFoundError:
            return HTMLResponse(
                "<h1>Frontend not built</h1>"
                "<p>Run <code>npm run build</code> "
                "in the frontend directory.</p>",
                status_code=503,
            )
        return HTMLResponse(html)

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    @app.get(
        "/dashboard", response_class=HTMLResponse, include_in_schema=False
    )
    @app.get("/lots", response_class=HTMLResponse, include_in_schema=False)
    @app.get(
        "/analytics", response_class=HTMLResponse, include_in_schema=False
    )
    @app.get("/revenue", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/map", response_class=HTMLResponse, include_in_schema=False)
    @app.get(
        "/micro-slots", response_class=HTMLResponse, include_in_schema=False
    )
    @app.get("/alerts", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/settings", response_class=HTMLResponse, include_in_schema=False)
    async def serve_spa_direct(request: Request):
        try:
            html = (spa_dir / "index.html").read_text()
        except FileNotFoundError:
            return HTMLResponse(
                "<h1>Frontend not built</h1>"
                "<p>Run <code>npm run build</code> "
                "in the frontend directory.</p>",
                status_code=503,
            )
        return HTMLResponse(html)
else:
    dashboard_dir = Path(__file__).parent.parent / "dashboard"
    static_dir = dashboard_dir / "static"
    if static_dir.exists():
        app.mount(
            "/static", StaticFiles(directory=str(static_dir)), name="static"
        )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def serve_app(request: Request):
        loading_path = dashboard_dir / "templates" / "loading.html"
        if loading_path.exists():
            return HTMLResponse(
                loading_path.read_text().replace(
                    "__NONCE__", request.state.nonce
                )
            )
        html_path = dashboard_dir / "templates" / "index.html"
        if html_path.exists():
            return HTMLResponse(
                html_path.read_text().replace("__NONCE__", request.state.nonce)
            )
        return HTMLResponse(
            "<h1>Pragma Smart Parking</h1><p>Dashboard not found</p>"
        )

    ALLOWED_PAGES = {"index", "dashboard", "driver", "admin", "login", "app"}

    @app.get(
        "/app/{page_name:path}",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    async def serve_page(request: Request, page_name: str):
        clean_name = page_name.strip("/").replace("/", "_").split(".")[0]
        if clean_name not in ALLOWED_PAGES:
            return HTMLResponse("<h1>Page not found</h1>", status_code=404)
        html_path = dashboard_dir / "templates" / f"{clean_name}.html"
        if not html_path.exists() and clean_name in {
            "admin",
            "dashboard",
            "login",
            "app",
        }:
            html_path = dashboard_dir / "templates" / "index.html"
        if html_path.exists():
            return HTMLResponse(
                html_path.read_text().replace("__NONCE__", request.state.nonce)
            )
        return HTMLResponse("<h1>Page not found</h1>", status_code=404)


@app.get("/api/v1/health")
async def health():
    db_ok = False
    try:
        with get_db_cm() as db:
            db.execute(text("SELECT 1"))
            db_ok = True
    except Exception:  # nosec — db_ok stays False, health returns degraded
        pass
    rf_ok = pipeline.predictor.rf is not None
    xgb_ok = pipeline.predictor.xgb is not None
    meta_ok = pipeline.predictor.meta is not None
    models_ok = rf_ok and xgb_ok
    chain_valid = pipeline.ledger.validate_chain()
    return {
        "status": "healthy" if (db_ok and models_ok) else "degraded",
        "service": "pragma",
        "version": "2.0.0",
        "database": db_ok,
        "models": {
            "rf": rf_ok,
            "xgb": xgb_ok,
            "meta": meta_ok,
            "all_loaded": models_ok,
        },
        "blockchain": {
            "chain_length": len(pipeline.ledger.chain),
            "valid": chain_valid,
        },
    }


@app.get("/api/v1/ready")
async def ready():
    db_ok = False
    try:
        with get_db_cm() as db:
            db.execute(text("SELECT 1"))
            db_ok = True
    except Exception:  # nosec — db_ok stays False, ready returns false
        pass
    models_ok = (
        pipeline.predictor.rf is not None
        and pipeline.predictor.xgb is not None
    )
    ok = db_ok and models_ok
    return {"ready": ok, "database": db_ok, "models_loaded": models_ok}
