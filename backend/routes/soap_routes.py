from fastapi import APIRouter
from pydantic import BaseModel
from backend.services.soap_service import generate_soap

router = APIRouter()

class SOAPRequest(BaseModel):
    case: str

@router.post("/soap")
def soap(req: SOAPRequest):
    result = generate_soap(req.case)
    return {"soap_note": result}
