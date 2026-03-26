"""
Rate Limit Dashboard - DermaCare AI
================================
Frontend API for login attempt monitoring.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from backend.auth.middleware import require_auth
from backend.auth.rate_limiter import rate_limiter

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/login-attempts")
def get_login_attempts(payload: dict = Depends(require_auth)):
    """Get login attempt statistics."""
    stats = rate_limiter.get_stats()
    return {
        "status": "ok",
        "total_attempts": stats.get("total_attempts", 0),
        "failed_attempts": stats.get("failed_attempts", 0),
        "successful_attempts": stats.get("successful_attempts", 0),
        "locked_accounts": stats.get("locked_count", 0),
        "rate_limited_ips": stats.get("rate_limited_count", 0)
    }


@router.post("/login-attempts/clear")
def clear_login_attempts(payload: dict = Depends(require_auth)):
    """Clear all login attempts and lockouts (admin only)."""
    # Check if user is admin
    user_id = payload.get("user_id", 0)
    if user_id != 1:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    cleared_count = rate_limiter.clear_all_lockouts()
    return {
        "status": "ok",
        "message": f"Cleared {cleared_count} lockout(s)"
    }


@router.get("/security-stats")
def get_security_stats(payload: dict = Depends(require_auth)):
    """Get comprehensive security statistics."""
    return {
        "status": "ok",
        "rate_limiting": {
            "enabled": True,
            "max_login_attempts": 5,
            "lockout_duration_minutes": 30,
            "rate_limit_window_seconds": 60,
            "rate_limit_max_requests": 10
        },
        "security_features": {
            "jwt_auth": True,
            "password_hashing": True,
            "input_sanitization": True,
            "sqlcipher_encryption": True,
            "token_rotation": True
        }
    }


@router.get("/security-stats")
def get_security_stats(payload: dict = Depends(require_auth)):
    """Get comprehensive security statistics."""
    return {
        "status": "ok",
        "rate_limiting": {
            "enabled": True,
            "max_login_attempts": 5,
            "lockout_duration_minutes": 30,
            "rate_limit_window_seconds": 60,
            "rate_limit_max_requests": 10
        },
        "security_features": {
            "jwt_auth": True,
            "password_hashing": True,
            "input_sanitization": True,
            "sqlcipher_encryption": True
        }
    }
