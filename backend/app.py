from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging
from typing import Callable
from backend.routes.diagnosis_routes import router as diagnosis_router
from backend.routes.soap_routes import router as soap_router
from backend.routes.drug_routes import router as drug_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DermaCare_AI")

app = FastAPI(
    title="DermaCare AI",
    description="Offline Dermatology Clinical Decision Support",
    version="0.1"
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

# Add CORS middleware to allow a frontend to access this backend later locally
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Can be locked down later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*"]
)

app.include_router(diagnosis_router)
app.include_router(soap_router)
app.include_router(drug_router)

# Healthcheck home route
@app.get("/")
def home():
    return {"status": "ok", "message": "DermaCare AI Engine Running"}

# Health check endpoint
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "DermaCare AI Backend",
        "version": "0.1",
        "timestamp": time.time()
    }

# Performance metrics endpoint
@app.get("/metrics")
def get_metrics():
    """Basic performance metrics endpoint"""
    import psutil
    import os
    
    return {
        "cpu_usage": psutil.cpu_percent(interval=1),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent,
        "process_id": os.getpid(),
        "uptime": time.time() - psutil.boot_time()
    }

# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error", "error": str(exc)}
    )
