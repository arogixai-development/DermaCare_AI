from fastapi import APIRouter
from pydantic import BaseModel
from backend.services.diagnosis_service import generate_diagnosis

router = APIRouter()

class DiagnosisRequest(BaseModel):
    context: str
    complaint: str
    lesion: str
    symptoms: str
    tests: str

@router.post("/diagnosis")
def diagnosis(req: DiagnosisRequest):
    result = generate_diagnosis(req.model_dump())
    return {"analysis": result}
