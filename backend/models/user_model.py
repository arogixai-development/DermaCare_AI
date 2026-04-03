"""
User Model - DermaCare AI
========================
SQLAlchemy ORM model for user authentication.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.sql import func
from backend.database.db_postgres import Base


class User(Base):
    """SQLAlchemy model for user accounts."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, nullable=True)
    
    # Security: Token rotation tracking
    # When password is changed, this version increments, invalidating all old tokens
    token_version = Column(Integer, default=1, nullable=False)
    
    def __repr__(self):
        return f"<User(username={self.username}, is_admin={self.is_admin})>"
    
    def increment_token_version(self):
        """Increment token version to invalidate old tokens."""
        self.token_version = (self.token_version or 1) + 1
        return self.token_version
