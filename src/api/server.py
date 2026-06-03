import os
import secrets
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import httpx

from .routes.auth import router as auth_router
from .routes.lots import router as lots_router
from .routes.revenue import router as revenue_router
from .routes.wallet import router as wallet_router
from .routes.ingestion import router as ingestion_router
from .routes.micro import router as micro_router
from .database import run_migrations
from src.constants import DB_INIT_MAX_RETRIES

logger = logging.getLogger(__name__)

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001").rstrip("/")

_ML_PREFIXES = (
    "/api/v1/predict/",
    "/api/v1/pricing/",
    "/api/v1/blockchain/",
    "/api/v1/digital-twin/",
    "/api/v1/marl/",
    "/api/v1/sessions/",
    "/api/v1/driver/",
    "/api/v1/admin/",
    "/api/v1/payments/",
    "/api/v1/simulation/",
)

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
                import asyncio
                await asyncio.sleep(2 ** attempt)
            else:
                logger.critical("All DB init attempts failed")
                raise
    logger.info("Pragma main service ready — ML routes proxy to %s", ML_SERVICE_URL)
    yield


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

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        from .utils import RateLimiter
        _global_rate_limiter = RateLimiter(max_calls=100, window=60.0)
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
    response.headers["Content-Security-Policy"] = f"default-src 'self'; script-src 'self' 'nonce-{nonce}' 'strict-dynamic'; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://unpkg.com; img-src 'self' https://*.tile.openstreetmap.org data:; font-src 'self' data: https://cdnjs.cloudflare.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests"
    if response.headers.get("server"):
        del response.headers["server"]
    if any(request.url.path.startswith(p) for p in ("/api/",)):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

@app.middleware("http")
async def ml_proxy_middleware(request: Request, call_next):
    path = request.url.path
    if not any(path.startswith(p) for p in _ML_PREFIXES):
        return await call_next(request)
    target = f"{ML_SERVICE_URL}{path}"
    if request.url.query:
        target += "?" + request.url.query
    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)
    try:
        body = await request.body()
    except Exception:
        body = b""
    headers = dict(request.headers)
    headers.pop("host", None)
    try:
        async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
            resp = await client.request(
                method=request.method,
                url=target,
                headers=headers,
                content=body,
            )
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:2000]}
            return JSONResponse(
                status_code=resp.status_code,
                content=data,
                headers={k: v for k, v in resp.headers.items() if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")},
            )
    except httpx.ConnectError:
        logger.warning("ML service unreachable at %s", ML_SERVICE_URL)
        return JSONResponse(
            status_code=502,
            content={"detail": "ML service unavailable", "ml_service": ML_SERVICE_URL},
        )
    except httpx.TimeoutException:
        logger.warning("ML service timeout at %s", ML_SERVICE_URL)
        return JSONResponse(
            status_code=504,
            content={"detail": "ML service timed out"},
        )
    except Exception as e:
        logger.error("ML proxy error: %s", e)
        return JSONResponse(
            status_code=502,
            content={"detail": "ML proxy error"},
        )

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

app.include_router(auth_router)
app.include_router(lots_router)
app.include_router(revenue_router)
app.include_router(wallet_router)
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
    if not html_path.exists() and clean_name in {"admin", "dashboard", "login", "app"}:
        html_path = dashboard_dir / "templates" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text().replace("__NONCE__", request.state.nonce))
    return HTMLResponse("<h1>Page not found</h1>", status_code=404)

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "pragma-main", "version": "2.0.0", "layers": 6}

@app.get("/api/v1/ready")
async def ready():
    db_ok = False
    try:
        from .database import get_db_cm
        from sqlalchemy import text
        with get_db_cm() as db:
            db.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    return {"ready": db_ok, "database": db_ok}
