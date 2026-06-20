import hashlib
import logging
import os
import re
from typing import cast
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from sqlalchemy.exc import IntegrityError
from src.api.database import get_db, User as UserModel, TokenBlacklist, is_sqlite
from src.api.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    get_current_user,
    set_auth_cookie,
    COOKIE_NAME,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from src.api.utils import DBRateLimiter
from src.constants import DRIVER_DEFAULT_BALANCE
from src.api.schemas import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    AuthUser,
    LogoutResponse,
)

logger = logging.getLogger(__name__)

_register_limiter = DBRateLimiter(max_calls=5, window=60.0, prefix="register")
_login_ip_limiter = DBRateLimiter(max_calls=60, window=60.0, prefix="login_ip")
_login_account_limiter = DBRateLimiter(
    max_calls=15, window=60.0, prefix="login_account"
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def _validate_password(pw: str):
    """Validate password strength without being user-hostile.

    Requirements:
      - At least 8 characters
      - At least one lowercase letter
      - At least one uppercase letter
      - At least one digit
    No maximum length (password managers generate long strings).
    No arbitrary special-character requirements.
    """
    if len(pw) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if not re.search(r"[a-z]", pw):
        raise HTTPException(400, "Password must contain a lowercase letter")
    if not re.search(r"[A-Z]", pw):
        raise HTTPException(400, "Password must contain an uppercase letter")
    if not re.search(r"\d", pw):
        raise HTTPException(400, "Password must contain a digit")


@router.post("/register", response_model=AuthResponse)
async def register(
    req: RegisterRequest,
    request: Request,
    response: Response,
    session=Depends(get_db),
):
    _validate_password(req.password)
    client_ip = request.client.host if request.client else "unknown"
    if not _register_limiter.check(f"register:{client_ip}"):
        raise HTTPException(429, "Too many registration attempts")
    if req.role and req.role != "driver":
        if os.environ.get("PRAGMA_ENV") != "testing":
            raise HTTPException(
                400, "Elevated roles require admin or invite flow"
            )
        if req.role not in ("admin", "lot_owner", "driver"):
            raise HTTPException(400, "Invalid role")
    role = (
        req.role if req.role in ("admin", "lot_owner", "driver") else "driver"
    )
    try:
        db_user = UserModel(
            email=req.email,
            hashed_password=hash_password(req.password),
            full_name=req.full_name,
            role=role,
            organization=req.organization,
        )
        session.add(db_user)
        session.flush()
        token = create_access_token(
            {
                "sub": db_user.email,
                "role": db_user.role,
                "user_id": db_user.id,
                "full_name": db_user.full_name,
                "organization": db_user.organization or "",
            }
        )
        session.commit()
        set_auth_cookie(response, token)
        return AuthResponse(
            access_token=token,
            user=AuthUser(
                id=cast(int, db_user.id),
                email=str(db_user.email),
                full_name=str(db_user.full_name),
                role=str(db_user.role),
                organization=str(db_user.organization or ""),
            ),
        )
    except IntegrityError:
        session.rollback()
        raise HTTPException(400, "Email already registered")
    except Exception:
        session.rollback()
        logger.exception("Registration failed")
        raise HTTPException(500, "Registration failed")


@router.post("/login", response_model=AuthResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    session=Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    if not _login_ip_limiter.check(f"login:{client_ip}"):
        raise HTTPException(429, "Too many login attempts from this IP")
    if not _login_account_limiter.check(f"login_account:{req.email}"):
        raise HTTPException(429, "Too many login attempts for this account")
    user = (
        session.query(UserModel).filter(UserModel.email == req.email).first()
    )
    if not user:
        raise HTTPException(401, "Invalid credentials")
    try:
        if not verify_password(req.password, user.hashed_password):
            raise HTTPException(401, "Invalid credentials")
    except Exception:
        logger.exception(
            "event=password_verify_failed user=%s", req.email
        )
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token(
        {
            "sub": user.email,
            "role": user.role,
            "user_id": user.id,
            "full_name": user.full_name,
            "organization": user.organization or "",
        }
    )
    set_auth_cookie(response, token)
    return AuthResponse(
        access_token=token,
        user=AuthUser(
            id=int(user.id),
            email=str(user.email),
            full_name=str(user.full_name),
            role=str(user.role),
            organization=str(user.organization or ""),
        ),
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        token = request.cookies.get(COOKIE_NAME, "")
    if not token:
        raise HTTPException(400, "No token provided")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        existing = (
            db.query(TokenBlacklist)
            .filter(TokenBlacklist.token_hash == token_hash)
            .first()
        )
        if not existing:
            payload = decode_token(token)
            exp_ts = payload.get("exp")
            if exp_ts:
                expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
            else:
                expires_at = datetime.now(timezone.utc) + timedelta(
                    minutes=ACCESS_TOKEN_EXPIRE_MINUTES
                )
            bl = TokenBlacklist(
                token_hash=token_hash,
                expires_at=expires_at,
            )
            db.add(bl)
            db.commit()
        # Clear the auth cookie
        response.delete_cookie(key=COOKIE_NAME, path="/")
        return LogoutResponse(message="logged_out")
    except Exception:
        db.rollback()
        logger.exception("Logout failed")
        raise HTTPException(500, "Logout failed")


@router.get("/me", response_model=AuthUser)
async def get_me(
    current_user: dict = Depends(get_current_user),
):
    return AuthUser(
        id=current_user.get("user_id", 0),
        email=current_user.get("sub", ""),
        full_name=current_user.get("full_name", ""),
        role=current_user.get("role", "driver"),
        organization=current_user.get("organization", ""),
    )


class SeedResponse(BaseModel):
    seeded: int
    message: str


@router.post("/seed", response_model=SeedResponse)
async def seed_users(db=Depends(get_db)):
    """Manually seed admin and driver users. Idempotent (updates existing)."""
    logger.info("event=seed.start")
    seed_data = [
        ("admin@pragma.io", "admin123", "Platform Admin", "admin", "Pragma Systems", None),
        ("owner@pragma.io", "owner123", "Jane Lotowner", "lot_owner", "Downtown Parking LLC", None),
        ("driver@pragma.io", "driver123", "Default Driver", "driver", "Pragma Drivers", DRIVER_DEFAULT_BALANCE),
        ("planner@pragma.io", "planner123", "City Planner", "city_planner", "City Traffic Dept", None),
        ("sensor@pragma.io", "sensor123", "IoT Sensor Gateway", "sensor", "Pragma IoT", None),
    ]
    try:
        count = 0
        for email, pw, name, role, org, balance in seed_data:
            existing = db.query(UserModel).filter(UserModel.email == email).first()
            if existing:
                existing.hashed_password = hash_password(pw)
                existing.full_name = name
            else:
                u = UserModel(
                    email=email,
                    hashed_password=hash_password(pw),
                    full_name=name,
                    role=role,
                    organization=org,
                )
                if balance is not None:
                    u.balance = float(balance)
                db.add(u)
            count += 1
        db.commit()
        logger.info("event=seed.complete users=%d", count)
        return SeedResponse(seeded=count, message=f"{count} users seeded/reset")
    except Exception as e:
        db.rollback()
        logger.exception("event=seed.failed error=%s", e)
        raise HTTPException(500, f"Seed failed: {e}")
