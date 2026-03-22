"""
Password Utilities - DermaCare AI
=================================
Secure password hashing using bcrypt.
"""
import bcrypt
import logging

logger = logging.getLogger("DermaCare_AI.auth")

BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with 12 rounds.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against a bcrypt hash.
    
    Args:
        password: Plain text password to verify
        hashed: Bcrypt hash to verify against
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        password_bytes = password.encode('utf-8')
        hashed_bytes = hashed.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        logger.warning(f"Password verification failed: {e}")
        return False
