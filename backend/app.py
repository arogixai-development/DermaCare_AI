"""
DermaCare AI - FastAPI Backend Application
========================================
Secure, local-only medical AI application for dermatology diagnosis.
"""
import os
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"[CONFIG] Loaded environment from {env_path}")
else:
    print("[WARNING] No .env file found. Using default configuration.")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging
from typing import Callable

# Import routers
from backend.routes.diagnosis_routes import router as diagnosis_router
from backend.routes.soap_routes import router as soap_router
from backend.routes.drug_routes import router as drug_router
from backend.routes.case_routes import router as case_router
from backend.routes.auth_routes import router as auth_router

# Import auth middleware
from backend.auth.middleware import require_auth

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DermaCare_AI")

app = FastAPI(
    title="DermaCare AI",
    description="Secure Local Dermatology Clinical Decision Support System",
    version="1.0.0"
)

# Add performance monitoring middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next: Callable):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logger.info(f"{request.method} {request.url.path} - {process_time:.4f}s")
    return response

# CORS origins - configurable via environment
import os
_allowed_origins_env = os.getenv("CORS_ORIGINS", "")
ALLOWED_ORIGINS = (
    [origin.strip() for origin in _allowed_origins_env.split(",")]
    if _allowed_origins_env
    else [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3010",
        "http://127.0.0.1:3010",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Trusted host middleware - configurable for production
_allowed_hosts_env = os.getenv("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = (
    [host.strip() for host in _allowed_hosts_env.split(",")]
    if _allowed_hosts_env
    else ["localhost", "127.0.0.1", "*.localhost"]
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=ALLOWED_HOSTS,
)

# Register routers
app.include_router(auth_router, tags=["Authentication"])
app.include_router(diagnosis_router, tags=["Diagnosis"])
app.include_router(soap_router, tags=["SOAP Notes"])
app.include_router(drug_router, tags=["Drug Checker"])
app.include_router(case_router, tags=["Cases"])

# Healthcheck home route
@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "DermaCare AI Backend Running",
        "version": "1.0.0",
        "security": "JWT Authentication Required"
    }

# Public health check endpoint
@app.get("/health")
def health_check():
    from backend.ai_engine.ollama_client import check_ollama_connection
    from backend.config import get_model_name
    from backend.database.db_postgres import is_db_postgres, get_db_info
    
    status = check_ollama_connection()
    
    db_info = get_db_info()
    return {
        "status": "healthy" if status["connected"] else "degraded",
        "ollama_connected": status["connected"],
        "model": get_model_name(),
        "gpu_acceleration": "enabled" if status.get("gpu_available") else "disabled",
        "ollama_error": status.get("error"),
        "database_type": db_info.get("type", "unknown"),
        "database_host": db_info.get("host", "N/A"),
        "version": "1.0.0",
        "security": "JWT Authentication Required"
    }

# Performance metrics endpoint
@app.get("/metrics")
def get_metrics():
    """Basic performance metrics endpoint"""
    import psutil
    import os
    
    return {
        "cpu_usage": psutil.cpu_percent(interval=0.1),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent,
        "process_id": os.getpid(),
    }

# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error", "error": str(exc)}
    )
