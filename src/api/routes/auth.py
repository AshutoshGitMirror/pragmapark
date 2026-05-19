from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from src.api.database import get_session, User as UserModel
from src.api.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = ""
    role: str = "lot_owner"
    organization: str = ""

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

@router.post("/register")
async def register(req: RegisterRequest):
    session = get_session()
    try:
        existing = session.query(UserModel).filter(UserModel.email == req.email).first()
        if existing:
            raise HTTPException(400, "Email already registered")
        db_user = UserModel(
            email=req.email,
            hashed_password=hash_password(req.password),
            full_name=req.full_name,
            role=req.role,
            organization=req.organization,
        )
        session.add(db_user)
        session.flush()
        token = create_access_token({"sub": db_user.email, "role": db_user.role, "user_id": db_user.id})
        session.commit()
        return AuthResponse(access_token=token, user={
            "id": db_user.id, "email": db_user.email, "name": db_user.full_name,
            "role": db_user.role, "org": db_user.organization,
        })
    finally:
        session.close()

@router.post("/login")
async def login(req: LoginRequest):
    session = get_session()
    try:
        user = session.query(UserModel).filter(UserModel.email == req.email).first()
        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(401, "Invalid credentials")
        token = create_access_token({"sub": user.email, "role": user.role, "user_id": user.id})
        return AuthResponse(access_token=token, user={
            "id": user.id, "email": user.email, "name": user.full_name,
            "role": user.role, "org": user.organization,
        })
    finally:
        session.close()

@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    session = get_session()
    try:
        db_user = session.query(UserModel).filter(UserModel.email == current_user.get("sub")).first()
        if not db_user:
            raise HTTPException(404, "User not found")
        return {
            "id": db_user.id, "email": db_user.email, "name": db_user.full_name,
            "role": db_user.role, "org": db_user.organization,
        }
    finally:
        session.close()
