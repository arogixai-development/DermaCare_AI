import json
import time
from backend.services.diagnosis_service import generate_diagnosis

cases = [
    {
        "name": "Accurate Psoriasis",
        "case": {
            "patient_age": 42,
            "geographic_region": "Chennai",
            "skin_phototype": "Type III",
            "complaint": "Chronic itchy scaly plaques on elbows and knees for 6 months",
            "lesion": "Symmetric well-demarcated erythematous plaques with silvery-white scale over extensor elbows and knees",
            "symptoms": "itching, scaling"
        },
        "monte_carlo": True
    },
    {
        "name": "Accurate Fungal",
        "case": {
            "patient_age": 28,
            "geographic_region": "New York",
            "skin_phototype": "Type II",
            "complaint": "Circular itchy rash on groin area for 3 weeks",
            "lesion": "Annular erythematous plaque with central clearing and active scaly border",
            "symptoms": "itching"
        },
        "monte_carlo": True
    },
    {
        "name": "Quick Weak Input",
        "case": {
            "patient_age": 30,
            "geographic_region": "Unknown",
            "skin_phototype": "Type I",
            "complaint": "red bump",
            "lesion": "bump",
            "symptoms": "none"
        },
        "monte_carlo": False
    }
]

for c in cases:
    print(f"=== {c['name']} ===")
    t0 = time.time()
    res = generate_diagnosis(c["case"], use_monte_carlo=c["monte_carlo"])
    t1 = time.time()
    print(f"Latency: {t1-t0:.2f}s")
    print("Diagnosis:", res.get("differential_diagnosis", [{}])[0].get("condition"))
    print("Triage:", res.get("triage"))
    print("Confidence Explanation:", res.get("confidence_explanation"))
    print("Treatments:", len(res.get("treatment_plan", [])))
    print("SOAP Assessment:", res.get("soap_note", {}).get("A"))
    print("-" * 40)
