import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.database import engine, Base
from src.api.routes import sessions, lots, driver, admin, auth, revenue, digital_twin, payments

app = FastAPI(title="Smart Parking Pro", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(lots.router, prefix="/api/v1")
app.include_router(driver.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(revenue.router, prefix="/api/v1")
app.include_router(digital_twin.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "healthy", "version": "3.0.0"}
