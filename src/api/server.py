from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.prediction import router as prediction_router
from .routes.pricing import router as pricing_router
from .routes.blockchain import router as blockchain_router
from .routes.digital_twin import router as digital_twin_router
from .routes.marl import router as marl_router

app = FastAPI(
    title="Gemini Smart Parking API",
    description="6-Layer Hybrid Smart Parking System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prediction_router)
app.include_router(pricing_router)
app.include_router(blockchain_router)
app.include_router(digital_twin_router)
app.include_router(marl_router)


@app.get("/")
async def root():
    return {
        "service": "Gemini Smart Parking",
        "version": "1.0.0",
        "layers": ["iot", "ml", "blockchain", "rl", "digital_twin", "api"],
        "status": "operational",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "layers": 6}
