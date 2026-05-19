from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone

from src.api.database import get_session
from src.api.auth import get_current_user, pwd_context
from pydantic import BaseModel

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "driver"

@router.post("/auth/login")
def login(req: LoginRequest, db=Depends(get_session)):
    from src.api.database import Driver
    driver = db.query(Driver).filter(Driver.driver_id == req.username).first()
    if not driver or not pwd_context.verify(req.password, driver.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token_data = {
        "sub": driver.driver_id, "role": driver.role,
        "exp": datetime.now(timezone.utc).timestamp() + 86400,
    }
    from jose import jwt
    import os
    secret = os.getenv("JWT_SECRET", "dev-secret")
    token = jwt.encode(token_data, secret, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}

@router.post("/auth/register")
def register(req: RegisterRequest, db=Depends(get_session)):
    from src.api.database import Driver
    exists = db.query(Driver).filter(Driver.driver_id == req.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="User exists")
    driver = Driver(
        driver_id=req.username,
        password_hash=pwd_context.hash(req.password),
        role=req.role,
    )
    db.add(driver)
    db.commit()
    return {"status": "created", "driver_id": driver.driver_id}
