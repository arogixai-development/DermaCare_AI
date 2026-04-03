from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from backend.database.db_postgres import get_db, engine, Base
from backend.services.case_service import upsert_case, get_all_cases, get_case_by_id, delete_case
from backend.auth.middleware import require_auth

# Create tables gracefully if they don't exist
try:
    Base.metadata.create_all(bind=engine)
except Exception:
    pass

router = APIRouter()

# Schema for incoming frontend data to validate API payloads
class CaseSchema(BaseModel):
    case_id: str
    timestamp: str
    context: Optional[str] = ""
    complaint: Optional[str] = ""
    lesion: Optional[str] = ""
    symptoms: Optional[str] = ""
    tests: Optional[str] = ""
    skin_phototype: Optional[str] = "UNKNOWN"
    geographic_region: Optional[str] = ""
    patient_age: Optional[int] = None
    occupation: Optional[str] = ""
    ai_diagnosis: Optional[str] = ""
    status: Optional[str] = "completed"

def get_user_id_from_payload(payload: dict) -> str:
    """Extract user_id from auth payload."""
    # payload contains {'user_id': xxx, 'email': xxx, 'exp': xxx}
    return str(payload.get("user_id", ""))

@router.post("/cases")
def create_or_update_case(case_data: CaseSchema, db: Session = Depends(get_db), payload: dict = Depends(require_auth)):
    try:
        user_id = get_user_id_from_payload(payload)
        result = upsert_case(db, case_data.model_dump(), user_id=user_id)
        return {"message": "Case saved successfully", "case_id": result.case_id}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/cases")
def get_cases(db: Session = Depends(get_db), payload: dict = Depends(require_auth)):
    try:
        user_id = get_user_id_from_payload(payload)
        cases = get_all_cases(db, user_id=user_id)
        return {"cases": cases}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db), payload: dict = Depends(require_auth)):
    try:
        user_id = get_user_id_from_payload(payload)
        case = get_case_by_id(db, case_id, user_id=user_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return {"case": case}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/cases/{case_id}")
def remove_case(case_id: str, db: Session = Depends(get_db), payload: dict = Depends(require_auth)):
    try:
        user_id = get_user_id_from_payload(payload)
        success = delete_case(db, case_id, user_id=user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Case not found")
        return {"message": "Case deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
