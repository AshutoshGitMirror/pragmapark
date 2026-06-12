import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.api.database import get_db_cm, User as UserModel, TokenBlacklist


_SECRET_FILE = os.getenv(
    "JWT_SECRET_FILE",
    os.path.join(os.path.dirname(__file__), "..", ".jwt_secret"),
)


def _get_secret():
    secret = os.getenv("JWT_SECRET")
    if secret:
        return secret
    if os.getenv("PRAGMA_ENV") == "production":
        raise RuntimeError("JWT_SECRET must be set in production environment")
    try:
        with open(_SECRET_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        secret = secrets.token_hex(32)
        try:
            os.makedirs(os.path.dirname(_SECRET_FILE), exist_ok=True)
            with open(_SECRET_FILE, "w") as f:
                f.write(secret)
        except OSError:
            raise RuntimeError(
                "Could not write JWT_SECRET_FILE; set JWT_SECRET env var"
            )
        return secret


SECRET_KEY: str = _get_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": True, "require_exp": True},
        )
        if "sub" not in payload:
            raise HTTPException(
                status_code=401, detail="Invalid token: missing subject"
            )
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
):
    # 1. Try HttpOnly cookie
    token = request.cookies.get(COOKIE_NAME)
    if token:
        payload = _validate_token(token)
        if payload is not None:
            return payload
    # 2. Fallback to Authorization Bearer header
    if credentials is not None:
        payload = _validate_token(credentials.credentials)
        if payload is not None:
            return payload
    raise HTTPException(status_code=401, detail="Not authenticated")


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
):
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    with get_db_cm() as session:
        blacklisted = (
            session.query(TokenBlacklist)
            .filter(
                TokenBlacklist.token_hash
                == hashlib.sha256(credentials.credentials.encode()).hexdigest()
            )
            .first()
        )
        if blacklisted:
            return None
        db_user = (
            session.query(UserModel)
            .filter(UserModel.email == payload.get("sub"))
            .first()
        )
        if db_user and db_user.role != payload.get("role"):
            payload["role"] = db_user.role
        return payload


COOKIE_NAME = "pragma_token"


def _validate_token(token: str) -> dict | None:
    """Validate JWT, check blacklist, update role from DB.
    Returns payload or None."""
    try:
        payload = decode_token(token)
    except HTTPException:
        return None
    with get_db_cm() as session:
        blacklisted = (
            session.query(TokenBlacklist)
            .filter(
                TokenBlacklist.token_hash
                == hashlib.sha256(token.encode()).hexdigest()
            )
            .first()
        )
        if blacklisted:
            return None
        db_user = (
            session.query(UserModel)
            .filter(UserModel.email == payload.get("sub"))
            .first()
        )
        if db_user and db_user.role != payload.get("role"):
            payload["role"] = db_user.role
        return payload


def set_auth_cookie(response, token: str, max_age_minutes: int | None = None):
    """Set the pragma_token HttpOnly cookie on a response."""
    if max_age_minutes is None:
        max_age_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
    secure = os.environ.get("PRAGMA_ENV") == "production"
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age_minutes * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
