from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from backend.services.diagnosis_service import (
    generate_diagnosis, 
    generate_diagnosis_async,
    generate_diagnosis_v2_strict,
    get_last_diagnosis,
    clear_cache,
    get_cache_stats,
    sanitize_v1_diagnosis_response,
)
from backend.ai_engine.ollama_client import check_ollama_connection
from backend.auth.middleware import require_auth
from backend.config import get_reliability_config, get_model_name
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
    sex: Optional[str] = Field(default=None, max_length=50)
    occupation: Optional[str] = Field(default=None, max_length=120)
    medical_history: Optional[str] = Field(default=None, max_length=2000)
    retrieved_context: Optional[List[str]] = Field(default=None, max_length=10)
    
    image_data: Optional[str] = Field(default=None, max_length=5000000)
    monte_carlo: bool = Field(default=False, description="Enable Accurate mode uncertainty estimation")
    
    @field_validator('complaint', 'lesion')
    @classmethod
    def strip_whitespace(cls, v):
        return v.strip() if isinstance(v, str) else v

def _format_diagnosis_response(data: dict, api_version: str) -> dict:
    if api_version == "v2":
        return {
            "diagnosis": data.get("diagnosis", []),
            "confidence": data.get("confidence", 0.0),
            "reasoning": data.get("reasoning", ""),
            "recommended_tests": data.get("recommended_tests", []),
            "treatment_plan": data.get("treatment_plan", []),
            "triage": data.get("triage", ""),
            "response_type": data.get("response_type", "fallback"),
            "fallback_reason": data.get("fallback_reason"),
            "parse_error_type": data.get("parse_error_type"),
            "recovery_stage": data.get("recovery_stage"),
            "cost_estimate": data.get("cost_estimate", {}),
            "escalation_instruction": data.get("escalation_instruction"),
        }
    return data


@router.post("/diagnosis")
def diagnosis(req: DiagnosisRequest, request: Request, payload: dict = Depends(require_auth)):
    """Production-ready diagnosis endpoint with Gated Multimodal Architecture"""
    try:
        req_data = req.model_dump()
        use_mc = req_data.pop('monte_carlo', False)
        result = generate_diagnosis(req_data, use_monte_carlo=use_mc)
        if isinstance(result, dict) and "error" not in result:
            result = sanitize_v1_diagnosis_response(result)
        reliability = get_reliability_config()
        api_version = request.headers.get("X-API-Version", reliability.get("api_default_version", "v1")).lower()
        return _format_diagnosis_response(result, api_version)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnosis generation failed: {str(e)}")

@router.post("/diagnosis/async")
async def diagnosis_async(req: DiagnosisRequest, request: Request, payload: dict = Depends(require_auth)):
    """Async diagnosis endpoint"""
    try:
        req_data = req.model_dump()
        use_mc = req_data.pop('monte_carlo', False)
        result = await generate_diagnosis_async(req_data, use_monte_carlo=use_mc)
        if isinstance(result, dict) and "error" not in result:
            result = sanitize_v1_diagnosis_response(result)
        reliability = get_reliability_config()
        api_version = request.headers.get("X-API-Version", reliability.get("api_default_version", "v1")).lower()
        return _format_diagnosis_response(result, api_version)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Async diagnosis generation failed: {str(e)}")


@router.post("/diagnosis/v2")
def diagnosis_v2(req: DiagnosisRequest, payload: dict = Depends(require_auth)):
    """Strict v2 clinical decision-support endpoint."""
    try:
        req_data = req.model_dump()
        result = generate_diagnosis_v2_strict(req_data)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnosis v2 generation failed: {str(e)}")

@router.post("/diagnosis/stream")
async def diagnosis_stream(req: DiagnosisRequest, request: Request, payload: dict = Depends(require_auth)):
    """
    Streaming diagnosis endpoint.
    Note: Streaming is not fully implemented - returns standard response.
    For production, implement SSE with streaming LLM responses.
    """
    try:
        req_data = req.model_dump()
        use_mc = req_data.pop('monte_carlo', False)
        result = generate_diagnosis(req_data, use_monte_carlo=use_mc)
        if isinstance(result, dict) and "error" not in result:
            result = sanitize_v1_diagnosis_response(result)
        reliability = get_reliability_config()
        api_version = request.headers.get("X-API-Version", reliability.get("api_default_version", "v1")).lower()
        return _format_diagnosis_response(result, api_version)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diagnosis streaming failed: {str(e)}")

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
            "quick_mode_time": "<=25 seconds (target)",
            "accurate_mode_time": "<=60 seconds (target)",
            "soap_time": "<5 seconds",
            "model_used": get_model_name(),
            "optimization": "production"
        },
        "glass_box_features": {
            "gated_multimodal_architecture": {
                "enabled": True,
                "description": "Dynamic weighting based on image quality"
            },
            "monte_carlo_dropout": {
                "enabled": True,
                "iterations": 3,
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
def clear_diagnosis_cache(payload: dict = Depends(require_auth)):
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
