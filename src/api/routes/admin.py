from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from pydantic import BaseModel

from src.api.database import get_session
from src.api.auth import get_current_user

router = APIRouter()

class PriceUpdateRequest(BaseModel):
    lot_id: str
    price: float

@router.post("/admin/price")
def update_price(req: PriceUpdateRequest, db=Depends(get_session),
                 user=Depends(get_current_user)):
    from src.api.database import ParkingLot
    lot = db.query(ParkingLot).filter(ParkingLot.lot_id == req.lot_id).first()
    if not lot:
        return {"error": "Lot not found"}
    lot.base_price = req.price
    lot.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"lot_id": req.lot_id, "new_price": req.price}
