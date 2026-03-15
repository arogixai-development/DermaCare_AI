from fastapi import APIRouter
from pydantic import BaseModel
from backend.services.drug_service import analyze_drug_interactions

router = APIRouter()

class DrugCheckRequest(BaseModel):
    drugs: list[str]

@router.post("/check-interactions")
def check_interactions(req: DrugCheckRequest):
    result = analyze_drug_interactions(req.drugs)
    return {"analysis": result}
