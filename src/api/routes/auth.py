import hashlib
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.exc import IntegrityError
from src.api.database import get_db, User as UserModel, TokenBlacklist
from src.api.auth import hash_password, verify_password, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from src.api.utils import RateLimiter
from src.api.schemas import RegisterRequest, LoginRequest, AuthResponse, AuthUser, LogoutResponse

logger = logging.getLogger(__name__)

_register_limiter = RateLimiter(max_calls=5, window=60.0)
_login_ip_limiter = RateLimiter(max_calls=10, window=60.0)
_login_account_limiter = RateLimiter(max_calls=5, window=60.0)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

import re

_PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]).{8,128}$")

def _validate_password(pw: str):
    if not _PASSWORD_RE.match(pw):
        raise HTTPException(400, "Password must be 8-128 chars with upper, lower, digit, and special character")

@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, request: Request, session = Depends(get_db)):
    _validate_password(req.password)
    client_ip = request.client.host if request.client else "unknown"
    if not _register_limiter.check(f"register:{client_ip}"):
        raise HTTPException(429, "Too many registration attempts")
    try:
        db_user = UserModel(
            email=req.email,
            hashed_password=hash_password(req.password),
            full_name=req.full_name,
            role="driver",
            organization=req.organization,
        )
        session.add(db_user)
        session.flush()
        token = create_access_token({"sub": db_user.email, "role": db_user.role, "user_id": db_user.id})
        session.commit()
        return AuthResponse(access_token=token, user=AuthUser(
            id=int(db_user.id), email=str(db_user.email), full_name=str(db_user.full_name),
            role=str(db_user.role), organization=str(db_user.organization or ""),
        ))
    except IntegrityError:
        session.rollback()
        raise HTTPException(400, "Email already registered")
    except Exception:
        session.rollback()
        logger.exception("Registration failed")
        raise HTTPException(500, "Registration failed")

@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, request: Request, session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    if not _login_ip_limiter.check(f"login:{client_ip}"):
        raise HTTPException(429, "Too many login attempts from this IP")
    if not _login_account_limiter.check(f"login_account:{req.email}"):
        raise HTTPException(429, "Too many login attempts for this account")
    user = session.query(UserModel).filter(UserModel.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token({"sub": user.email, "role": user.role, "user_id": user.id})
    return AuthResponse(access_token=token, user=AuthUser(
        id=int(user.id), email=str(user.email), full_name=str(user.full_name),
        role=str(user.role), organization=str(user.organization or ""),
    ))

@router.post("/logout", response_model=LogoutResponse)
async def logout(request: Request, current_user: dict = Depends(get_current_user), db = Depends(get_db)):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(400, "No token provided")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        existing = db.query(TokenBlacklist).filter(TokenBlacklist.token_hash == token_hash).first()
        if not existing:
            bl = TokenBlacklist(
                token_hash=token_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            )
            db.add(bl)
            db.commit()
        return LogoutResponse(message="logged_out")
    except Exception:
        db.rollback()
        logger.exception("Logout failed")
        raise HTTPException(500, "Logout failed")

@router.get("/me", response_model=AuthUser)
async def get_me(current_user: dict = Depends(get_current_user), session = Depends(get_db)):
    db_user = session.query(UserModel).filter(UserModel.email == current_user.get("sub")).first()
    if not db_user:
        raise HTTPException(404, "User not found")
    return AuthUser(
        id=int(db_user.id), email=str(db_user.email), full_name=str(db_user.full_name),
        role=str(db_user.role), organization=str(db_user.organization or ""),
    )
