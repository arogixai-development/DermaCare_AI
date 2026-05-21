import json
from backend.services.diagnosis_service import generate_diagnosis

case = {
    "patient_age": 28,
    "geographic_region": "NY",
    "skin_phototype": "Type II",
    "complaint": "itchy red patch",
    "lesion": "small patch",
    "symptoms": "itching"
}

res = generate_diagnosis(case, use_monte_carlo=False)
print(json.dumps(res, indent=2))
