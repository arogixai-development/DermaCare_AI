"""
Auth Middleware - DermaCare AI
==============================
JWT token verification for protected routes.
"""
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Callable
import logging

from backend.auth.jwt_handler import verify_token

logger = logging.getLogger("DermaCare_AI.auth")

security = HTTPBearer(auto_error=False)


async def verify_access_token(request: Request) -> Optional[dict]:
    """
    Verify the access token from Authorization header.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Decoded token payload if valid, None otherwise
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        return None
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    
    token = parts[1]
    payload = verify_token(token, token_type="access")
    
    return payload


async def require_auth(request: Request) -> dict:
    """
    Dependency that requires valid authentication.
    
    Raises:
        HTTPException: If token is missing or invalid
    """
    payload = await verify_access_token(request)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return payload


async def optional_auth(request: Request) -> Optional[dict]:
    """
    Dependency that optionally validates authentication.
    
    Returns:
        Decoded token payload if valid, None otherwise
    """
    return await verify_access_token(request)
