"""
Auth Routes - DermaCare AI
=========================
Authentication endpoints: login, register, refresh, logout.
With rate limiting and brute force protection.
"""
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
import secrets
import logging

from backend.database.db_postgres import get_db, engine, Base, DB_IS_POSTGRES
from backend.models.user_model import User
from backend.auth.password import hash_password, verify_password
from backend.auth.jwt_handler import (
    create_access_token, 
    create_refresh_token, 
    verify_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)
from backend.auth.middleware import require_auth
from backend.auth.rate_limiter import (
    check_login_rate_limit,
    record_failed_login,
    record_successful_login
)

logger = logging.getLogger("DermaCare_AI.auth")


def _ensure_user_schema_compatibility() -> None:
    """
    Backfill required auth columns for existing databases without migrations.
    Fixes older SQLite/PostgreSQL databases missing users.token_version.
    """
    try:
        inspector = inspect(engine)
        if "users" not in inspector.get_table_names():
            return

        column_names = {col["name"] for col in inspector.get_columns("users")}
        if "token_version" in column_names:
            return

        with engine.begin() as conn:
            if DB_IS_POSTGRES:
                conn.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 1"
                    )
                )
            else:
                conn.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN token_version INTEGER NOT NULL DEFAULT 1"
                    )
                )
        logger.info("Applied schema compatibility fix: users.token_version")
    except Exception as exc:
        logger.warning("Schema compatibility check failed: %s", exc)


Base.metadata.create_all(bind=engine)
_ensure_user_schema_compatibility()

router = APIRouter(prefix="/auth", tags=["Authentication"])

DEFAULT_ADMIN_USERNAME = "arogixai@gmail.com"
DEFAULT_ADMIN_PASSWORD = "Arogix9345@"

def init_default_admin(db: Session):
    """Create default admin user on first startup."""
    existing = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
    if not existing:
        admin = User(
            username=DEFAULT_ADMIN_USERNAME,
            email=DEFAULT_ADMIN_USERNAME,
            hashed_password=hash_password(DEFAULT_ADMIN_PASSWORD),
            is_admin=True,
            is_active=True
        )
        db.add(admin)
        db.commit()
        logger.info(f"Default admin created. Username: {DEFAULT_ADMIN_USERNAME}")

try:
    db_init = next(get_db())
    init_default_admin(db_init)
except Exception:
    pass


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None


class UserResponse(BaseModel):
    username: str
    email: Optional[str] = None
    is_admin: bool
    user_id: int


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, credentials: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate user and return tokens. Rate limited for brute force protection."""
    
    await check_login_rate_limit(request, credentials.username)
    
    user = db.query(User).filter(User.username == credentials.username).first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        attempt_info = record_failed_login(request, credentials.username)
        if attempt_info["locked"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked due to {attempt_info['attempts']} failed attempts. Try again in {attempt_info['lockout_minutes']} minutes."
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid username or password. {attempt_info['remaining_attempts']} attempts remaining."
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    record_successful_login(request, credentials.username)
    
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    
    # Include token_version in tokens for rotation security
    token_version = user.token_version or 1
    access_token = create_access_token({"sub": user.username, "user_id": user.id, "token_version": token_version})
    refresh_token = create_refresh_token({"sub": user.username, "user_id": user.id, "token_version": token_version})
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: Optional[RefreshRequest] = None, request: Request = None, response: Response = None, db: Session = Depends(get_db)):
    """Refresh access token using refresh token from secure cookie or request body."""
    token = request.cookies.get("refresh_token") if request else None
    if not token and payload:
        token = payload.refresh_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )

    verified_payload = verify_token(token, token_type="refresh")

    if not verified_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    username = verified_payload.get("sub")
    token_version_from_payload = verified_payload.get("token_version", 1)
    
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # SECURITY: Verify token version matches
    # If password was changed or logout was forced, token_version won't match
    current_version = user.token_version or 1
    if token_version_from_payload != current_version:
        logger.warning(f"Token version mismatch for user {username}: payload={token_version_from_payload}, db={current_version}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please login again."
        )
    
    # Create new tokens with updated version
    new_access_token = create_access_token({
        "sub": user.username, 
        "user_id": user.id,
        "token_version": current_version
    })
    new_refresh_token = create_refresh_token({
        "sub": user.username, 
        "user_id": user.id,
        "token_version": current_version
    })
    
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )
    
    logger.info(f"Token refreshed for user {username}")
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
def logout(response: Response):
    """Clear refresh token cookie."""
    response.delete_cookie(key="refresh_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_current_user(payload: dict = Depends(require_auth)):
    """Get current authenticated user info."""
    return UserResponse(
        username=payload.get("sub"),
        email=None,
        is_admin=payload.get("user_id", 0) == 1,
        user_id=payload.get("user_id", 0)
    )


@router.post("/register", response_model=UserResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user (admin only in production)."""
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    if request.email:
        existing_email = db.query(User).filter(User.email == request.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        is_admin=False,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
        user_id=user.id,
    )


@router.get("/init-admin")
def init_admin(db: Session = Depends(get_db)):
    """Initialize default admin user. Call this once after deployment."""
    try:
        existing = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
        if existing:
            return {"message": "Admin already exists", "username": existing.username}
        
        admin = User(
            username=DEFAULT_ADMIN_USERNAME,
            email=DEFAULT_ADMIN_USERNAME,
            hashed_password=hash_password(DEFAULT_ADMIN_PASSWORD),
            is_admin=True,
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        logger.info(f"Admin user created: {DEFAULT_ADMIN_USERNAME}")
        
        return {
            "message": "Admin created successfully",
            "username": DEFAULT_ADMIN_USERNAME,
            "password": DEFAULT_ADMIN_PASSWORD
        }
    except Exception as e:
        logger.error(f"Error creating admin: {e}")
        return {"error": str(e), "message": "Failed to create admin"}
