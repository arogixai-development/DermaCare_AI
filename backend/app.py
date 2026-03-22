"""
DermaCare AI - FastAPI Backend Application
========================================
Secure, local-only medical AI application for dermatology diagnosis.
"""
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

# SECURITY: CORS restricted to local origins only
# Only allow requests from localhost:3000 and 127.0.0.1:3000
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3010",
    "http://127.0.0.1:3010",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# SECURITY: Trusted host middleware - only allow local access
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.localhost"],
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
    
    status = check_ollama_connection()
    return {
        "status": "healthy" if status["connected"] else "degraded",
        "ollama_connected": status["connected"],
        "model": get_model_name(),
        "gpu_acceleration": "enabled" if status["connected"] else "unavailable",
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
