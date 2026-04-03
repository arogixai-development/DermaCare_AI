"""
PostgreSQL Database Configuration - DermaCare AI Production
=========================================================
PostgreSQL connection setup for Oracle Cloud deployment.
"""
import os
import logging
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool, QueuePool

logger = logging.getLogger("DermaCare_AI.database")


def get_database_url() -> str:
    """
    Get PostgreSQL connection URL from environment.
    Format: postgresql://user:password@host:port/dbname
    """
    # Try DATABASE_URL first (full connection string)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    
    # Build from individual components
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "dermacare")
    db_user = os.getenv("DB_USER", "dermacare")
    db_password = os.getenv("DB_PASSWORD", "")
    
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def create_postgres_engine():
    """
    Create PostgreSQL engine with production settings.
    """
    database_url = get_database_url()
    
    # Parse URL for logging (without password)
    parsed = urlparse(database_url)
    safe_url = f"postgresql://{parsed.username}:***@{parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}"
    logger.info(f"[DB] Connecting to PostgreSQL: {safe_url}")
    
    try:
        engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
        
        # Set PostgreSQL-specific settings
        @event.listens_for(engine, "connect")
        def set_postgres_settings(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            
            # Performance settings
            cursor.execute("SET statement_timeout = '60s'")
            cursor.execute("SET lock_timeout = '10s'")
            cursor.execute("SET idle_in_transaction_session_timeout = '5min'")
            cursor.execute("SET timezone = 'UTC'")
            
            cursor.close()
        
        logger.info("[DB] PostgreSQL engine created successfully")
        return engine, True
        
    except Exception as e:
        logger.error(f"[DB] Failed to create PostgreSQL engine: {e}")
        raise


def create_sqlite_fallback():
    """
    Fallback to SQLite if PostgreSQL is unavailable.
    Used for local development only.
    """
    logger.warning("[DB] PostgreSQL unavailable, falling back to SQLite")
    
    from backend.database.db import engine, SessionLocal, Base, get_db_info
    
    return engine, False


def create_engine_with_fallback():
    """
    Try PostgreSQL first, fall back to SQLite.
    """
    try:
        return create_postgres_engine()
    except Exception as e:
        logger.warning(f"[DB] PostgreSQL connection failed: {e}")
        return create_sqlite_fallback()


# Create engine based on environment
def get_engine_type() -> str:
    """Determine which database to use."""
    db_url = os.getenv("DATABASE_URL", "")
    db_host = os.getenv("DB_HOST", "")
    
    if db_url.startswith("postgresql://") or db_host:
        return "postgresql"
    return "sqlite"


# Export the appropriate engine
if get_engine_type() == "postgresql":
    engine, DB_IS_POSTGRES = create_postgres_engine()
else:
    from backend.database.db import engine as sqlite_engine, SQLCIPHER_ENABLED
    engine = sqlite_engine
    DB_IS_POSTGRES = False

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    from backend.models.user_model import User
    from backend.models.case_model import CaseRecord
    
    Base.metadata.create_all(bind=engine)


def get_db_info() -> dict:
    """Get database configuration info."""
    if DB_IS_POSTGRES:
        database_url = get_database_url()
        parsed = urlparse(database_url)
        
        return {
            "type": "postgresql",
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip('/'),
            "user": parsed.username,
        }
    else:
        return {
            "type": "sqlite",
            "encrypted": False,
        }


def is_db_postgres() -> bool:
    """Check if using PostgreSQL."""
    return DB_IS_POSTGRES
