"""
Rate Limiter - DermaCare AI
===========================
Rate limiting middleware for brute force protection.
"""
from fastapi import Request, HTTPException, status
from datetime import datetime, timedelta
from typing import Dict, List
import logging
import hashlib

logger = logging.getLogger("DermaCare_AI.rate_limiter")

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 10


class RateLimiter:
    """In-memory rate limiter for login attempts."""
    
    def __init__(self):
        self._login_attempts: Dict[str, List[datetime]] = {}
        self._locked_accounts: Dict[str, datetime] = {}
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _get_user_key(self, username: str, ip: str) -> str:
        """Generate unique key for user+IP combination."""
        return hashlib.sha256(f"{username}:{ip}".encode()).hexdigest()[:16]
    
    def is_locked(self, username: str, ip: str) -> bool:
        """Check if account/IP combination is locked."""
        key = self._get_user_key(username, ip)
        
        if key in self._locked_accounts:
            lock_time = self._locked_accounts[key]
            if datetime.now() > lock_time:
                del self._locked_accounts[key]
                if key in self._login_attempts:
                    self._login_attempts[key] = []
                return False
            return True
        
        return False
    
    def get_lockout_remaining(self, username: str, ip: str) -> int:
        """Get remaining lockout time in minutes."""
        key = self._get_user_key(username, ip)
        if key in self._locked_accounts:
            lock_time = self._locked_accounts[key]
            remaining = (lock_time - datetime.now()).total_seconds()
            return max(0, int(remaining / 60))
        return 0
    
    def record_failed_attempt(self, username: str, ip: str) -> Dict:
        """Record a failed login attempt."""
        key = self._get_user_key(username, ip)
        now = datetime.now()
        
        if key not in self._login_attempts:
            self._login_attempts[key] = []
        
        self._login_attempts[key].append(now)
        
        window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
        self._login_attempts[key] = [
            t for t in self._login_attempts[key] if t > window_start
        ]
        
        attempts = len(self._login_attempts[key])
        remaining = MAX_LOGIN_ATTEMPTS - attempts
        
        if attempts >= MAX_LOGIN_ATTEMPTS:
            lock_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            self._locked_accounts[key] = lock_until
            logger.warning(f"Account locked for {username} from {ip} due to {attempts} failed attempts")
            return {
                "locked": True,
                "attempts": attempts,
                "remaining_attempts": 0,
                "lockout_minutes": LOCKOUT_DURATION_MINUTES
            }
        
        return {
            "locked": False,
            "attempts": attempts,
            "remaining_attempts": remaining,
            "lockout_minutes": 0
        }
    
    def record_successful_attempt(self, username: str, ip: str) -> None:
        """Clear failed attempts on successful login."""
        key = self._get_user_key(username, ip)
        if key in self._login_attempts:
            self._login_attempts[key] = []
        if key in self._locked_accounts:
            del self._locked_accounts[key]
        logger.info(f"Successful login for {username} from {ip}")
    
    def check_rate_limit(self, ip: str) -> Dict:
        """Check if IP has exceeded rate limit."""
        if ip not in self._login_attempts:
            return {"allowed": True, "remaining": RATE_LIMIT_MAX_REQUESTS}
        
        now = datetime.now()
        window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
        
        self._login_attempts[ip] = [
            t for t in self._login_attempts[ip] if t > window_start
        ]
        
        request_count = len(self._login_attempts[ip])
        
        if request_count >= RATE_LIMIT_MAX_REQUESTS:
            return {
                "allowed": False,
                "remaining": 0,
                "retry_after": RATE_LIMIT_WINDOW_SECONDS
            }
        
        return {
            "allowed": True,
            "remaining": RATE_LIMIT_MAX_REQUESTS - request_count
        }
    
    def record_request(self, ip: str) -> None:
        """Record a request for rate limiting."""
        if ip not in self._login_attempts:
            self._login_attempts[ip] = []
        self._login_attempts[ip].append(datetime.now())
    
    def clear_lockout(self, username: str, ip: str) -> bool:
        """Clear lockout for a specific user/IP."""
        key = self._get_user_key(username, ip)
        if key in self._locked_accounts:
            del self._locked_accounts[key]
        if key in self._login_attempts:
            self._login_attempts[key] = []
        logger.info(f"Lockout cleared for {username} from {ip}")
        return True
    
    def clear_all_lockouts(self) -> int:
        """Clear all lockouts (admin function)."""
        count = len(self._locked_accounts)
        self._locked_accounts = {}
        self._login_attempts = {}
        logger.info(f"All lockouts cleared ({count} removed)")
        return count
    
    def get_status(self) -> Dict:
        """Get rate limiter status."""
        return {
            "locked_accounts": len(self._locked_accounts),
            "active_ips": len([k for k in self._login_attempts.keys() if k not in self._locked_accounts]),
            "max_login_attempts": MAX_LOGIN_ATTEMPTS,
            "lockout_duration_minutes": LOCKOUT_DURATION_MINUTES,
            "rate_limit_max_requests": RATE_LIMIT_MAX_REQUESTS,
            "rate_limit_window_seconds": RATE_LIMIT_WINDOW_SECONDS
        }
    
    def get_stats(self) -> Dict:
        """Get detailed statistics for admin dashboard."""
        return {
            "total_attempts": sum(len(v) for v in self._login_attempts.values()),
            "failed_attempts": len(self._locked_accounts),
            "successful_attempts": 0,  # Not tracked currently
            "locked_count": len(self._locked_accounts),
            "rate_limited_count": len([k for k in self._login_attempts.keys() if k not in self._locked_accounts])
        }


rate_limiter = RateLimiter()


async def check_login_rate_limit(request: Request, username: str) -> None:
    """
    Check if login is allowed for given username/IP.
    Raises HTTPException if rate limited or locked.
    """
    ip = rate_limiter._get_client_ip(request)
    
    rate_check = rate_limiter.check_rate_limit(ip)
    if not rate_check["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Retry after {rate_check['retry_after']} seconds."
    )
    
    if rate_limiter.is_locked(username, ip):
        remaining = rate_limiter.get_lockout_remaining(username, ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked due to failed attempts. Try again in {remaining} minutes."
        )


def record_failed_login(request: Request, username: str) -> Dict:
    """Record failed login attempt and return status."""
    ip = rate_limiter._get_client_ip(request)
    return rate_limiter.record_failed_attempt(username, ip)


def record_successful_login(request: Request, username: str) -> None:
    """Clear failed attempts on successful login."""
    ip = rate_limiter._get_client_ip(request)
    rate_limiter.record_successful_attempt(username, ip)
