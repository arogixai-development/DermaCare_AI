"""
JWT Handler - DermaCare AI
=========================
Handles JWT token creation and validation.
"""
import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import jwt, JWTError

logger = logging.getLogger("DermaCare_AI.auth")

# Get configuration from environment or generate secure defaults
def _get_secret_key() -> str:
    """Get JWT secret key from environment or generate one."""
    secret = os.getenv("SECRET_KEY")
    if not secret:
        # Generate a new secret for this session
        secret = secrets.token_urlsafe(64)
        logger.warning("SECRET_KEY not set in environment. Using generated key. Sessions will not persist across restarts.")
    return secret

SECRET_KEY = _get_secret_key()
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary containing claims (e.g., {"sub": user_id})
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: Dictionary containing claims (e.g., {"sub": user_id})
        
    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token string
        token_type: Expected token type ("access" or "refresh")
        
    Returns:
        Decoded token payload if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verify token type
        if payload.get("type") != token_type:
            logger.warning(f"Token type mismatch: expected {token_type}, got {payload.get('type')}")
            return None
        
        return payload
        
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        return None


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token without verification (for debugging).
    
    Args:
        token: The JWT token string
        
    Returns:
        Decoded payload if valid format, None otherwise
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
    except JWTError:
        return None
