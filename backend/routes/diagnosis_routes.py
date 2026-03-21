from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from backend.services.diagnosis_service import (
    generate_diagnosis, 
    generate_diagnosis_async,
    get_last_diagnosis,
    clear_cache,
    get_cache_stats
)
from backend.ai_engine.ollama_client import check_ollama_connection, OllamaConnectionError
import json

router = APIRouter()

class DiagnosisRequest(BaseModel):
    context: str = Field(default="", max_length=1000)
    complaint: str = Field(max_length=2000)
    lesion: str = Field(max_length=2000)
    symptoms: str = Field(default="", max_length=2000)
    tests: str = Field(default="", max_length=1000)
    geographic_region: str = Field(default="", max_length=100)
    patient_age: int = Field(ge=0, le=120)
    
    lesion_history: Optional[str] = Field(default=None, max_length=1000)
    history_duration: Optional[str] = Field(default=None, max_length=100)
    change_pattern: Optional[str] = Field(default=None, max_length=200)
    previous_biopsies: Optional[str] = Field(default=None, max_length=500)
    
    image_data: Optional[str] = Field(default=None, max_length=5000000)
    
    @field_validator('complaint', 'lesion')
    @classmethod
    def strip_whitespace(cls, v):
        return v.strip() if isinstance(v, str) else v

@router.post("/diagnosis")
def diagnosis(req: DiagnosisRequest):
    """Production-ready diagnosis endpoint with Gated Multimodal Architecture"""
    try:
        status = check_ollama_connection()
        if not status["connected"]:
            raise HTTPException(
                status_code=503,
                detail=f"AI Backend Offline: {status['error']}"
            )
        
        result = generate_diagnosis(req.model_dump())
        return result
    except HTTPException:
        raise
    except OllamaConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnosis generation failed: {str(e)}")

@router.post("/diagnosis/async")
async def diagnosis_async(req: DiagnosisRequest):
    """Async diagnosis endpoint"""
    try:
        result = await generate_diagnosis_async(req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Async diagnosis generation failed: {str(e)}")

@router.post("/diagnosis/stream")
async def diagnosis_stream(req: DiagnosisRequest):
    """Streaming diagnosis endpoint"""
    async def generate_stream():
        try:
            async for chunk in generate_diagnosis_streaming(req.model_dump()):
                yield f"data: {chunk}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@router.get("/diagnosis/cache")
def get_diagnosis_cache():
    """Get cached diagnosis with statistics"""
    diagnosis = get_last_diagnosis()
    cache_stats = get_cache_stats()
    return {
        "cached_diagnosis": diagnosis,
        "cache_stats": cache_stats
    }

@router.get("/diagnosis/stats")
def get_diagnosis_stats():
    """Get Glass Box AI system statistics"""
    cache_stats = get_cache_stats()
    return {
        "system": "DermaCare AI - Glass Box Edition",
        "architecture": "Gated Multimodal Architecture (GMU)",
        "performance_goals": {
            "diagnosis_time": "<30 seconds",
            "soap_time": "<5 seconds",
            "model_used": "llama3.1",
            "optimization": "production"
        },
        "glass_box_features": {
            "gated_multimodal_architecture": {
                "enabled": True,
                "description": "Dynamic weighting based on image quality"
            },
            "monte_carlo_dropout": {
                "enabled": True,
                "iterations": 5,
                "description": "Multiple inferences for uncertainty estimation"
            },
            "adversarial_safety": {
                "enabled": True,
                "description": "Safe refusal for non-dermatological images"
            },
            "metadata_weighting": {
                "enabled": True,
                "description": "History-based malignancy risk adjustment"
            },
            "confidence_intervals": {
                "enabled": True,
                "description": "Honest confidence reporting"
            }
        },
        "cache_performance": cache_stats,
        "optimizations_applied": [
            "Gated Multimodal Architecture",
            "Monte Carlo Uncertainty Estimation",
            "Image Quality Gate",
            "History Gate (opens on low quality)",
            "Adversarial Safety Checks",
            "Metadata-Weighted Diagnosis"
        ]
    }

@router.delete("/diagnosis/cache")
def clear_diagnosis_cache():
    """Clear diagnosis cache"""
    clear_cache()
    return {"message": "Diagnosis cache cleared successfully"}

@router.get("/diagnosis/health")
def diagnosis_health():
    """Health check with Glass Box status"""
    status = check_ollama_connection()
    from backend.config import get_model_name
    return {
        "status": "healthy" if status["connected"] else "degraded",
        "ollama_connected": status["connected"],
        "ollama_models": status["models"],
        "ollama_error": status["error"],
        "model": get_model_name(),
        "gpu_acceleration": "enabled" if status["connected"] else "unavailable",
        "optimization_level": "glass_box",
        "streaming": "available" if status["connected"] else "unavailable",
        "glass_box_features": {
            "gated_multimodal": "active",
            "monte_carlo": "active",
            "adversarial_safety": "active",
            "metadata_weighting": "active"
        },
        "instructions": "If Ollama shows offline, run: `ollama serve` in a terminal"
    }
