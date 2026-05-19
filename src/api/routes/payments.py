from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.database import get_session
from src.api.auth import get_current_user

router = APIRouter()

class PaymentRequest(BaseModel):
    session_id: str
    driver_id: str
    amount: float
    lot_id: str

@router.post("/payments/process")
def process_payment(req: PaymentRequest, db=Depends(get_session),
                    user=Depends(get_current_user)):
    from src.pipeline.orchestrator import pipeline
    return pipeline.process_payment(req.session_id, req.driver_id, req.amount, req.lot_id)
