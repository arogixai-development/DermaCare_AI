"""
Database Configuration - DermaCare AI
====================================
SQLCipher-encrypted SQLite database with secure key management.
"""
import os
import secrets
import hashlib
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'dermacare.db')


def get_encryption_key() -> str:
    """
    Get or generate SQLCipher encryption key.
    Key is derived from environment variable or generated securely.
    """
    env_key = os.getenv("SQLCIPHER_KEY")
    
    if env_key:
        return env_key
    
    key_file = os.path.join(BASE_DIR, '.db_key')
    
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            return f.read().strip()
    
    new_key = secrets.token_urlsafe(32)
    
    with open(key_file, 'w') as f:
        f.write(new_key)
    
    os.chmod(key_file, 0o600)
    
    return new_key


def create_sqlcipher_engine():
    """
    Create SQLCipher-enabled SQLite engine.
    Falls back to plain SQLite if pysqlcipher3 not available.
    """
    encryption_key = get_encryption_key()
    
    try:
        from pysqlcipher3 import dbapi2 as sqlite3
        
        engine = create_engine(
            f"sqlite+pysqlcipher:///:memory:",
            connect_args={
                "db": DB_PATH,
                "passphrase": encryption_key,
            },
            pool_pre_ping=True,
        )
        
        @event.listens_for(engine, "connect")
        def set_sqlcipher_key(dbapi_connection, connection_record):
            dbapi_connection.execute(f"PRAGMA key = '{encryption_key}'")
            dbapi_connection.execute("PRAGMA cipher_page_size = 4096")
            dbapi_connection.execute("PRAGMA kdf_iter = 256000")
            dbapi_connection.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
            dbapi_connection.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")
        
        print("[DB] SQLCipher encryption enabled (AES-256)")
        return engine, True
        
    except ImportError:
        print("=" * 60)
        print("[WARNING] pysqlcipher3 not available!")
        print("[WARNING] Database is using UNENCRYPTED SQLite!")
        print("[WARNING] Patient data is NOT PROTECTED!")
        print("")
        print("To enable encryption, install pysqlcipher3:")
        print("  pip install pysqlcipher3")
        print("")
        print("Or set SQLCIPHER_KEY in .env file:")
        print("  SQLCIPHER_KEY=your-secure-key")
        print("=" * 60)
        
        engine = create_engine(
            f"sqlite:///{DB_PATH}",
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        
        return engine, False


engine, SQLCIPHER_ENABLED = create_sqlcipher_engine()
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
    from backend.models.case_model import Case
    
    Base.metadata.create_all(bind=engine)


def get_db_info() -> dict:
    """Get database configuration info (without sensitive data)."""
    return {
        "database_path": DB_PATH,
        "sqlcipher_enabled": SQLCIPHER_ENABLED,
        "database_size_mb": os.path.getsize(DB_PATH) / (1024 * 1024) if os.path.exists(DB_PATH) else 0,
        "encryption": "AES-256" if SQLCIPHER_ENABLED else "None",
    }


def is_db_encrypted() -> bool:
    """Check if database is currently encrypted."""
    return SQLCIPHER_ENABLED
