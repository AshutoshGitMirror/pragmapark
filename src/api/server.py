import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
from .database import init_db

app = FastAPI(
    title="Pragma Smart Parking API",
    description="Startup-Grade Smart Parking Management Platform",
    version="2.0.0",
)

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=ALLOWED_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

dashboard_dir = Path(__file__).parent.parent / "dashboard"
static_dir = dashboard_dir / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_app():
    html_path = dashboard_dir / "templates" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>Pragma Smart Parking</h1><p>Dashboard not found</p>")

ALLOWED_PAGES = {"index", "dashboard", "driver", "admin", "login", "app"}

@app.get("/app/{page_name:path}", response_class=HTMLResponse, include_in_schema=False)
async def serve_page(page_name: str):
    clean_name = page_name.strip("/").split(".")[0]
    if clean_name not in ALLOWED_PAGES:
        return HTMLResponse("<h1>Page not found</h1>", status_code=404)
    html_path = dashboard_dir / "templates" / f"{clean_name}.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>Page not found</h1>", status_code=404)

@app.on_event("startup")
async def on_startup():
    init_db()

@app.get("/api/v1/health")
async def health():
    return {"status": "healthy", "service": "pragma", "version": "2.0.0", "layers": 6}
