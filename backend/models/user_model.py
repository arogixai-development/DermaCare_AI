"""
User Model - DermaCare AI
========================
SQLAlchemy ORM model for user authentication.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.sql import func
from backend.database.db import Base


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
    
    def __repr__(self):
        return f"<User(username={self.username}, is_admin={self.is_admin})>"
