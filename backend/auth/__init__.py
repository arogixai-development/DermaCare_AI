"""
Authentication Module - DermaCare AI
==================================
JWT-based authentication for secure local deployment.
"""

from .jwt_handler import create_access_token, verify_token, decode_token
from .password import hash_password, verify_password

__all__ = [
    "create_access_token",
    "verify_token", 
    "decode_token",
    "hash_password",
    "verify_password"
]
