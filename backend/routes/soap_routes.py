from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from backend.services.soap_service import generate_soap_optimized, get_soap_stats

router = APIRouter()

class SOAPRequest(BaseModel):
    case_id: Optional[str] = Field(default=None, max_length=100)
    complaint: Optional[str] = Field(default=None, max_length=2000)
    lesion: Optional[str] = Field(default=None, max_length=2000)
    symptoms: Optional[str] = Field(default=None, max_length=2000)
    duration: Optional[str] = Field(default=None, max_length=500)
    medical_history: Optional[str] = Field(default=None, max_length=1000)
    region: Optional[str] = Field(default=None, max_length=100)
    patient_age: Optional[int] = Field(default=None, ge=0, le=120)
    diagnoses: Optional[List[str]] = Field(default=None, max_length=20)
    treatment: Optional[List[str]] = Field(default=None, max_length=50)
    tests: Optional[List[str]] = Field(default=None, max_length=30)

@router.post("/soap")
def soap(req: SOAPRequest):
    """Generate SOAP note - accepts full case data for fresh generation"""
    try:
        # Build case data dict from request
        case_data = {
            "case_id": req.case_id,
            "complaint": req.complaint,
            "lesion": req.lesion,
            "symptoms": req.symptoms,
            "duration": req.duration,
            "medical_history": req.medical_history,
            "geographic_region": req.region,
            "patient_age": req.patient_age,
            "diagnoses_list": req.diagnoses or [],
            "treatment_list": req.treatment or [],
            "tests_list": req.tests or []
        }
        result = generate_soap_optimized(case_data)
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
