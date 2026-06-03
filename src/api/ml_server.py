"""Standalone ML / pipeline service for pragmapark.

Runs pipeline-heavy routes (predict, pricing, blockchain, digital-twin,
marl, sessions, driver, admin, payments) as a separate Render service.
Keeps ML model memory (sklearn, xgboost) isolated from the main API.
"""
import os
import secrets
import uuid
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_BG_TASKS: list[asyncio.Task] = []

def _restart_background_tasks():
    from src.api.workers import _periodic_loop, _do_mining, _do_cleanup, _do_outbox, _do_ingest
    from src.simulation.time_machine import time_machine
    from src.constants import MINER_INTERVAL_S, CLEANUP_INTERVAL_S, OUTBOX_INTERVAL_S, INGEST_INTERVAL_S, INGEST_RETRIES
    for t in _BG_TASKS:
        t.cancel()
    _BG_TASKS.clear()
    speedup = max(1, time_machine.speedup)
    try:
        loop = asyncio.get_running_loop()
        _BG_TASKS.extend([
            asyncio.create_task(_periodic_loop("miner", max(1, MINER_INTERVAL_S // speedup), _do_mining, use_executor=True)()),
            asyncio.create_task(_periodic_loop("cleanup", max(1, CLEANUP_INTERVAL_S // speedup), _do_cleanup)()),
            asyncio.create_task(_periodic_loop("outbox", max(1, OUTBOX_INTERVAL_S // speedup), _do_outbox)()),
            asyncio.create_task(_periodic_loop("ingest", max(1, INGEST_INTERVAL_S // speedup), _do_ingest, retries=INGEST_RETRIES)()),
        ])
        logger.info("event=tasks.restarted speedup=%d", speedup)
    except RuntimeError:
        pass

def _log_slot_transition(slot_id, prev_s, new_s):
    logger.info("Slot %d: %s -> %s", slot_id, prev_s, new_s)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.api.database import run_migrations
    from src.constants import DB_INIT_MAX_RETRIES
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
                logger.critical("All DB init attempts failed")
                raise

    from src.simulation.time_machine import time_machine
    try:
        time_machine.cleanup_stale_snapshots()
    except Exception:
        pass
    logger.info("event=startup speedup=%d", time_machine.speedup)
    yield

    for t in _BG_TASKS:
        t.cancel()
    await asyncio.gather(*_BG_TASKS, return_exceptions=True)


app = FastAPI(
    title="Pragma ML Service",
    description="Pipeline-heavy routes (predict, pricing, blockchain, etc.)",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-Id", uuid.uuid4().hex[:12])
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
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

@app.get("/api/v1/health")
async def health():
    from src.pipeline.orchestrator import pipeline
    return {
        "status": "ok",
        "service": "pragma-ml",
        "ml_models": {
            "rf": pipeline.predictor.rf is not None,
            "xgb": pipeline.predictor.xgb is not None,
            "meta": pipeline.predictor.meta is not None,
        },
        "blockchain": {
            "chain_length": len(pipeline.ledger.chain),
            "valid": pipeline.ledger.validate_chain(),
        },
    }

@app.get("/api/v1/ready")
async def ready():
    from src.pipeline.orchestrator import pipeline
    rf_ok = pipeline.predictor.rf is not None
    xgb_ok = pipeline.predictor.xgb is not None
    bc_ok = len(pipeline.ledger.chain) > 0
    return {
        "ready": rf_ok and xgb_ok and bc_ok,
        "models_loaded": rf_ok and xgb_ok,
        "blockchain": bc_ok,
    }
