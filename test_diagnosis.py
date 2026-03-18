
import sys
import os
import asyncio
import json

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.getcwd())))

from backend.services.diagnosis_service import generate_diagnosis

case_data = {
    "patient_age": 45,
    "geographic_region": "North America",
    "complaint": "Itchy red rash on elbows",
    "lesion": "Symmetric erythematous plaques with silvery scale",
    "symptoms": "Itching, mild burning, bleeding when scratched (Auspitz sign)",
    "tests": "None"
}

print("Running diagnosis test...")
try:
    result = generate_diagnosis(case_data)
    print("Result:")
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
