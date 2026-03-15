from pydantic import BaseModel
from typing import Optional
from enum import Enum

class FitzpatrickScale(str, Enum):
    I = "I"
    II = "II"
    III = "III"
    IV = "IV"
    V = "V"
    VI = "VI"
    UNKNOWN = "UNKNOWN"

class DiagnosisRequest(BaseModel):
    context: str
    complaint: str
    lesion: str
    symptoms: str
    tests: str
    geographic_region: str
    patient_age: int
    skin_phototype: Optional[FitzpatrickScale] = FitzpatrickScale.UNKNOWN
    occupation: Optional[str] = None
