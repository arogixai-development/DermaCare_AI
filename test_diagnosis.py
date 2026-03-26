
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.getcwd())))

from backend.services.diagnosis_service import generate_diagnosis

case_data = {
    "patient_age": 35,
    "geographic_region": "Tropical",
    "complaint": "Itchy red rash on hands for 2 weeks",
    "lesion": "Erythematous vesicular patches on dorsal hands with oozing",
    "symptoms": "Intense itching worse at night, burning sensation",
    "tests": ""
}

print("Testing DermaCare AI Diagnosis Service")
print("=" * 50)
print(f"Patient: {case_data['patient_age']}yo from {case_data['geographic_region']}")
print(f"Complaint: {case_data['complaint']}")
print(f"Lesion: {case_data['lesion']}")
print(f"Symptoms: {case_data['symptoms']}")
print("=" * 50)
print()

try:
    print("Generating diagnosis...")
    result = generate_diagnosis(case_data)
    print(f"Status: {'SUCCESS' if result else 'FAILED'}")
    print()
    
    # Check if it's using fallback or LLM
    if "monte_carlo_uncertainty" in result:
        print("Using LLM-generated response (Glass Box AI)")
        print(f"  - Monte Carlo Uncertainty: {result.get('monte_carlo_uncertainty', 'N/A')}")
        print(f"  - Glass Box Features: {result.get('glass_box_features', [])}")
    else:
        print("Using fallback response")
    
    print()
    print("Diagnosis Result:")
    print("-" * 50)
    
    # Show key results
    if "differential_diagnosis" in result:
        print("\nTop Diagnoses:")
        for dx in result["differential_diagnosis"][:3]:
            print(f"  - {dx.get('condition', 'Unknown')} ({dx.get('probability', 'N/A')})")
            features = dx.get('supporting_features', [])
            if features:
                print(f"    Features: {', '.join(features[:2])}")
    
    if "clinical_reasoning" in result:
        reasoning = result['clinical_reasoning']
        print(f"\nClinical Reasoning:")
        print(f"  {reasoning[:300]}...")
    
    if "triage" in result:
        print(f"\nTriage Level: {result['triage']}")
    
    print()
    print("Full JSON output:")
    print(json.dumps(result, indent=2))
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
