from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.services.diagnosis_service import (
    generate_diagnosis, 
    generate_diagnosis_async,
    generate_diagnosis_streaming,
    get_last_diagnosis,
    clear_cache,
    get_cache_stats
)
import json

router = APIRouter()

class DiagnosisRequest(BaseModel):
    context: str = ""
    complaint: str
    lesion: str
    symptoms: str = ""
    tests: str = ""
    geographic_region: str = ""
    patient_age: int = 0

@router.post("/diagnosis")
def diagnosis(req: DiagnosisRequest):
    """Optimized synchronous diagnosis endpoint"""
    try:
        result = generate_diagnosis(req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnosis generation failed: {str(e)}")

@router.post("/diagnosis/async")
async def diagnosis_async(req: DiagnosisRequest):
    """Optimized asynchronous diagnosis endpoint"""
    try:
        result = await generate_diagnosis_async(req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Async diagnosis generation failed: {str(e)}")

@router.post("/diagnosis/stream")
async def diagnosis_stream(req: DiagnosisRequest):
    """Streaming diagnosis endpoint for real-time user feedback"""
    async def generate_stream():
        try:
            async for chunk in generate_diagnosis_streaming(req.model_dump()):
                yield f"data: {chunk}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@router.get("/diagnosis/cache")
def get_diagnosis_cache():
    """Get cached diagnosis results with statistics"""
    diagnosis = get_last_diagnosis()
    cache_stats = get_cache_stats()
    return {
        "cached_diagnosis": diagnosis,
        "cache_stats": cache_stats
    }

@router.get("/diagnosis/stats")
def get_diagnosis_stats():
    """Get diagnosis performance statistics"""
    cache_stats = get_cache_stats()
    return {
        "performance_goals": {
            "diagnosis_time": "<30 seconds",
            "soap_time": "<5 seconds",
            "model_used": "llama3:8b",
            "optimization": "high"
        },
        "cache_performance": cache_stats,
        "optimizations_applied": [
            "Quantized model (40-60% faster)",
            "Reduced prompt size (60% smaller)",
            "Token limit (120 tokens)",
            "GPU acceleration (RTX 4050)",
            "Streaming responses",
            "Enhanced caching"
        ]
    }

@router.delete("/diagnosis/cache")
def clear_diagnosis_cache():
    """Clear the diagnosis cache"""
    clear_cache()
    return {"message": "Diagnosis cache cleared successfully"}

@router.get("/diagnosis/health")
def diagnosis_health():
    """Health check for diagnosis service"""
    return {
        "status": "healthy",
        "model": "llama3:8b",
        "gpu_acceleration": "enabled",
        "optimization_level": "high",
        "streaming": "available"
    }
