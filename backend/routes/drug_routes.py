from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import List, Annotated
from backend.services.drug_service import analyze_drug_interactions

router = APIRouter()

class DrugCheckRequest(BaseModel):
    drugs: Annotated[List[str], Field(min_length=1, max_length=20)]
    
    @field_validator('drugs')
    @classmethod
    def validate_drug_names(cls, v):
        return [drug.strip()[:200] for drug in v if drug.strip()]

@router.post("/check-interactions")
def check_interactions(req: DrugCheckRequest):
    try:
        result = analyze_drug_interactions(req.drugs)
        return {"analysis": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drug interaction check failed: {str(e)}")
