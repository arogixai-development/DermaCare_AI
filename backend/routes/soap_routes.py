from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.services.soap_service import generate_soap_optimized, get_soap_stats

router = APIRouter()

class SOAPRequest(BaseModel):
    case: str = ""

@router.post("/soap")
def soap(req: SOAPRequest):
    """Optimized SOAP generation - NO LLM calls, instant response"""
    try:
        result = generate_soap_optimized(req.case)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SOAP generation failed: {str(e)}")

@router.get("/soap/stats")
def get_soap_statistics():
    """Get SOAP generation performance statistics"""
    return get_soap_stats()

@router.get("/soap/health")
def soap_health():
    """Health check for SOAP service"""
    return {
        "status": "healthy",
        "processing_time": "<5 seconds (instant)",
        "llm_calls": "0 (eliminated)",
        "optimization": "maximum",
        "method": "Python logic only"
    }
