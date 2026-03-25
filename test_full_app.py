
import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("DermaCare AI - Full Application Test")
print("=" * 60)

# Step 1: Login
print("\n[1] Testing Authentication...")
login_data = {
    "username": "arogixai@gmail.com",
    "password": "Arogix9345@"
}
try:
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if response.status_code == 200:
        token = response.json().get("access_token")
        print("    Login: SUCCESS")
    else:
        print(f"    Login: FAILED ({response.status_code})")
        print(f"    {response.text}")
        exit(1)
except Exception as e:
    print(f"    Login: ERROR - {e}")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}

# Step 2: Test Diagnosis
print("\n[2] Testing Diagnosis API...")
diagnosis_data = {
    "complaint": "Itchy red rash on hands for 2 weeks",
    "lesion": "Erythematous vesicular patches on dorsal hands with oozing",
    "symptoms": "Intense itching worse at night, burning sensation",
    "patient_age": 35,
    "geographic_region": "Tropical"
}

try:
    response = requests.post(f"{BASE_URL}/diagnosis", json=diagnosis_data, headers=headers, timeout=180)
    print(f"    Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        
        print("\n" + "=" * 60)
        print("DIAGNOSIS RESULTS")
        print("=" * 60)
        
        # Patient info
        print(f"\nPatient: {result.get('patient_age', 'N/A')} years old")
        print(f"Region: {result.get('geographic_region', 'N/A')}")
        print(f"Complaint: {result.get('complaint', 'N/A')}")
        print(f"Inference Time: {result.get('_inference_time', 'N/A')}")
        print(f"Model: {result.get('_model', 'N/A')}")
        
        # Differential Diagnoses
        print("\n--- Differential Diagnoses ---")
        for dx in result.get("differential_diagnosis", []):
            print(f"  {dx.get('condition', 'Unknown')} ({dx.get('probability', 'N/A')})")
        
        # Clinical Reasoning
        print("\n--- Clinical Reasoning ---")
        print(f"  {result.get('clinical_reasoning', 'N/A')}")
        
        # SOAP Note
        print("\n--- SOAP Note ---")
        soap = result.get("soap_note", {})
        if isinstance(soap, dict):
            print(f"  S: {soap.get('S', 'N/A')}")
            print(f"  O: {soap.get('O', 'N/A')}")
            print(f"  A: {soap.get('A', 'N/A')}")
            print(f"  P: {soap.get('P', 'N/A')}")
        
        # Treatment Plan
        print("\n--- Treatment Plan ---")
        for tx in result.get("treatment_plan", []):
            print(f"  Medication: {tx.get('medication', 'N/A')}")
            print(f"  Application: {tx.get('application', 'N/A')}")
            print(f"  Duration: {tx.get('duration', 'N/A')}")
        
        # Triage
        print(f"\n--- Triage Level ---")
        print(f"  {result.get('triage', 'N/A')}")
        
        # Glass Box AI Features
        print("\n--- Glass Box AI Features ---")
        uncertainty = result.get("uncertainty_flags", {})
        print(f"  Monte Carlo Enabled: {uncertainty.get('monte_carlo_enabled', False)}")
        print(f"  Confidence: {uncertainty.get('overall_confidence', 'N/A')}")
        print(f"  Confidence Interval: {uncertainty.get('confidence_interval', 'N/A')}")
        
        gmu = result.get("gmu_analysis", {})
        print(f"  Image Quality Gate: {gmu.get('image_quality_gate', 'N/A')}")
        print(f"  Metadata Weight: {gmu.get('multimodal_weights', {}).get('metadata', 'N/A')}")
        
        safety = result.get("safety_checks", {})
        print(f"  Adversarial Check: {'PASSED' if safety.get('adversarial_check_passed', False) else 'FAILED'}")
        
        print("\n" + "=" * 60)
        print("TEST RESULT: SUCCESS")
        print("=" * 60)
        
    else:
        print(f"    Diagnosis: FAILED")
        print(f"    {response.text}")
        
except Exception as e:
    print(f"    Diagnosis: ERROR - {e}")
    import traceback
    traceback.print_exc()

# Step 3: Test SOAP Generation
print("\n[3] Testing SOAP Generation...")
soap_data = {
    "diagnosis_data": diagnosis_data,
    "differential_diagnosis": result.get("differential_diagnosis", []) if 'result' in dir() else []
}
try:
    response = requests.post(f"{BASE_URL}/soap", json=soap_data, headers=headers, timeout=60)
    print(f"    SOAP Generation: {response.status_code}")
    if response.status_code == 200:
        soap_result = response.json()
        print(f"    SOAP Generated: {soap_result.get('status', 'N/A')}")
except Exception as e:
    print(f"    SOAP Generation: ERROR - {e}")

# Step 4: Test Drug Interaction Check
print("\n[4] Testing Drug Interaction Check...")
drug_data = {
    "drugs": ["Topical Corticosteroid", "Antihistamine", "Ibuprofen"]
}
try:
    response = requests.post(f"{BASE_URL}/check-interactions", json=drug_data, headers=headers, timeout=30)
    print(f"    Drug Interaction Check: {response.status_code}")
    if response.status_code == 200:
        drug_result = response.json()
        print(f"    Interactions: {len(drug_result.get('interactions', []))} found")
except Exception as e:
    print(f"    Drug Interaction Check: ERROR - {e}")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETED")
print("=" * 60)
