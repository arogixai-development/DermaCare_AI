
"""
Comprehensive Test Suite - DermaCare AI
======================================
Tests:
1. Authentication (login, register, logout)
2. API endpoints (diagnosis, soap, drug interaction)
3. AI relevance - ensures diagnosis matches user input
4. Glass Box AI features
5. Rate limiting
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"
TEST_RESULTS = []

def log_test(name, passed, message="", details=None):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status}: {name}")
    if message:
        print(f"      {message}")
    if details:
        for k, v in details.items():
            print(f"      {k}: {v}")
    TEST_RESULTS.append({
        "name": name,
        "passed": passed,
        "message": message,
        "details": details
    })

def test_authentication():
    print("\n" + "=" * 60)
    print("TEST SUITE: Authentication")
    print("=" * 60)
    
    # Test Login
    print("\n[1.1] Testing Login...")
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "arogixai@gmail.com",
        "password": "Arogix9345@"
    })
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        log_test("Login", True, f"Token received: {token[:20]}...")
        return token
    else:
        log_test("Login", False, f"Status: {response.status_code}, Response: {response.text}")
        return None

def test_api_endpoints(token):
    print("\n" + "=" * 60)
    print("TEST SUITE: API Endpoints")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test Health
    print("\n[2.1] Testing Health Check...")
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        data = response.json()
        log_test("Health Check", True, f"Ollama: {data.get('ollama_connected')}, Model: {data.get('model')}")
    else:
        log_test("Health Check", False, f"Status: {response.status_code}")
    
    # Test Diagnosis with patient-specific data
    print("\n[2.2] Testing Diagnosis API (Patient-Specific)...")
    diagnosis_data = {
        "complaint": "Painful ulcer on lower lip for 3 weeks",
        "lesion": "Single deep ulcer with rolled borders on lower lip, 1.5cm diameter",
        "symptoms": "Painful when eating, slight bleeding, no fever",
        "patient_age": 28,
        "geographic_region": "Urban"
    }
    
    print(f"    Input: {diagnosis_data['patient_age']}yo, Urban")
    print(f"    Complaint: {diagnosis_data['complaint']}")
    print(f"    Lesion: {diagnosis_data['lesion']}")
    
    response = requests.post(f"{BASE_URL}/diagnosis", json=diagnosis_data, headers=headers, timeout=180)
    
    if response.status_code == 200:
        data = response.json()
        
        # Check if diagnosis is relevant to the input
        diagnoses = data.get("differential_diagnosis", [])
        top_diagnosis = diagnoses[0].get("condition", "") if diagnoses else ""
        
        # AI Relevance Check
        lip_keywords = ["lip", "mouth", "oral", "ulcer", "cancrum", "aphthous"]
        relevant_to_lip = any(kw in top_diagnosis.lower() for kw in lip_keywords)
        
        print(f"\n    AI Top Diagnosis: {top_diagnosis}")
        print(f"    Relevant to lip ulcer? {'YES' if relevant_to_lip else 'NO - WARNING'}")
        
        log_test("Diagnosis API", True, f"Status: 200", {
            "Top Diagnosis": top_diagnosis,
            "Probability": diagnoses[0].get("probability", "N/A") if diagnoses else "N/A",
            "AI Relevant to Input": relevant_to_lip
        })
        
        return data
    else:
        log_test("Diagnosis API", False, f"Status: {response.status_code}, {response.text}")
        return None

def test_ai_relevance(token, diagnosis_result):
    print("\n" + "=" * 60)
    print("TEST SUITE: AI Relevance Analysis")
    print("=" * 60)
    
    if not diagnosis_result:
        log_test("AI Relevance", False, "No diagnosis result to analyze")
        return False
    
    diagnoses = diagnosis_result.get("differential_diagnosis", [])
    clinical_reasoning = diagnosis_result.get("clinical_reasoning", "")
    
    print(f"\n[3.1] Checking if diagnoses relate to lip ulcer...")
    
    # Expected conditions for lip ulcer (expanded keywords)
    expected_keywords = ["lip", "mouth", "oral", "ulcer", "herpes", "stomatitis",
                        "aphthous", "behcet", "beh", "traumatic", "cancrum", "impetigo", 
                        "syphilis", "carcinoma", "cancer", "infectious", "viral", "bacterial",
                        "autoimmune", "immune"]
    
    all_relevant = True
    for dx in diagnoses[:3]:
        condition = dx.get("condition", "").lower()
        probability = dx.get("probability", "0%")
        features = dx.get("supporting_features", [])
        
        is_relevant = any(kw in condition for kw in expected_keywords)
        if not is_relevant:
            all_relevant = False
            print(f"    [!] {condition} ({probability}) - MAY NOT BE RELEVANT to lip ulcer")
        else:
            print(f"    [OK] {condition} ({probability}) - Relevant")
    
    log_test("AI Relevance", all_relevant, 
             "All top diagnoses relevant to patient input" if all_relevant else "Some diagnoses may not be relevant")
    
    # Check clinical reasoning mentions lip/mouth
    print(f"\n[3.2] Checking clinical reasoning...")
    reasoning_relevant = any(kw in clinical_reasoning.lower() for kw in ["lip", "oral", "mouth", "ulcer"])
    log_test("Clinical Reasoning Relevance", reasoning_relevant, 
             f"Mentions lip/oral: {reasoning_relevant}")
    
    return all_relevant

def test_glass_box_ai(diagnosis_result):
    print("\n" + "=" * 60)
    print("TEST SUITE: Glass Box AI Features")
    print("=" * 60)
    
    if not diagnosis_result:
        log_test("Glass Box AI", False, "No diagnosis result")
        return
    
    print(f"\n[4.1] Monte Carlo Uncertainty...")
    uncertainty = diagnosis_result.get("uncertainty_flags", {})
    monte_carlo = uncertainty.get("monte_carlo_enabled", False)
    confidence = uncertainty.get("overall_confidence", "N/A")
    interval = uncertainty.get("confidence_interval", [])
    
    log_test("Monte Carlo Enabled", monte_carlo, f"Confidence: {confidence}")
    if interval:
        log_test("Confidence Interval", True, f"[{interval[0]:.1f}%, {interval[1]:.1f}%]")
    
    print(f"\n[4.2] Gated Multimodal Architecture...")
    gmu = diagnosis_result.get("gmu_analysis", {})
    image_quality = gmu.get("image_quality_gate", "N/A")
    metadata_weight = gmu.get("multimodal_weights", {}).get("metadata", "N/A")
    
    log_test("Image Quality Gate", image_quality != "N/A", f"Quality: {image_quality}")
    log_test("Metadata Weight", True, f"Weight: {metadata_weight}")
    
    print(f"\n[4.3] Safety Checks...")
    safety = diagnosis_result.get("safety_checks", {})
    adversarial = safety.get("adversarial_check_passed", False)
    
    log_test("Adversarial Safety", adversarial, f"Check passed: {adversarial}")

def test_soap_generation(token, case_data):
    print("\n" + "=" * 60)
    print("TEST SUITE: SOAP Note Generation")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"\n[5.1] Testing SOAP Generation for lip ulcer case...")
    response = requests.post(f"{BASE_URL}/soap", json={
        "case_id": "test_lip_ulcer",
        "complaint": case_data["complaint"],
        "lesion": case_data["lesion"],
        "symptoms": case_data["symptoms"],
        "region": case_data["geographic_region"],
        "patient_age": case_data["patient_age"],
        "diagnoses": [
            "Aphthous Stomatitis",
            "Herpes Simplex Virus",
            "Traumatic Ulcer"
        ],
        "treatment": [
            "Topical Antiseptic rinse",
            "Analgesic gel for pain"
        ],
        "tests": ["Biopsy if persistent"]
    }, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        soap_note = data.get("soap_note", "")
        
        # soap_note can be string or dict
        if isinstance(soap_note, str):
            subjective = soap_note
            mentions_patient = "28" in soap_note or "Urban" in soap_note or "lip" in soap_note.lower()
        else:
            subjective = soap_note.get("S", "") or soap_note.get("SUBJECTIVE", "")
            mentions_patient = "28" in subjective or "Urban" in subjective or "lip" in subjective.lower()
        
        log_test("SOAP Generation", True, f"Status: 200")
        log_test("SOAP Uses Patient Data", mentions_patient, 
                 "References patient info" if mentions_patient else "Does not reference patient info")
        
        print(f"\n    SOAP Note (first 200 chars):")
        print(f"    {str(soap_note)[:200]}...")
    else:
        log_test("SOAP Generation", False, f"Status: {response.status_code}")
        if response.status_code == 422:
            print(f"    Error: {response.text[:200]}")

def test_drug_interaction(token):
    print("\n" + "=" * 60)
    print("TEST SUITE: Drug Interaction Checker")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"\n[6.1] Testing Drug Interaction Check...")
    response = requests.post(f"{BASE_URL}/check-interactions", json={
        "drugs": ["Acyclovir", "Topical Corticosteroid", "Ibuprofen"]
    }, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        interactions = data.get("interactions", [])
        
        log_test("Drug Interaction API", True, f"Found {len(interactions)} interactions")
        
        if interactions:
            print(f"\n    Interactions found:")
            for ix in interactions[:3]:
                print(f"    - {ix.get('drug1')} + {ix.get('drug2')}: {ix.get('severity', 'N/A')}")
    else:
        log_test("Drug Interaction API", False, f"Status: {response.status_code}")

def test_rate_limiting():
    print("\n" + "=" * 60)
    print("TEST SUITE: Rate Limiting (Security)")
    print("=" * 60)
    
    print(f"\n[7.1] Testing with invalid credentials (to test rate limiting)...")
    
    failed_attempts = 0
    for i in range(3):
        response = requests.post(f"{BASE_URL}/auth/login", json={
            "username": "arogixai@gmail.com",
            "password": "wrong_password_123"
        })
        if response.status_code == 401:
            failed_attempts += 1
            print(f"    Failed attempt {i+1}: 401 as expected")
    
    log_test("Failed Login Tracking", failed_attempts == 3, 
             f"{failed_attempts}/3 failed attempts detected")
    
    # Try one more to check remaining attempts message
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "arogixai@gmail.com",
        "password": "wrong_password_123"
    })
    
    if response.status_code == 401:
        data = response.json()
        detail = data.get("detail", "")
        has_remaining = "remaining" in detail.lower()
        log_test("Rate Limit Warning", has_remaining, f"Message: {detail[:80]}...")

def run_comprehensive_test():
    print("\n" + "=" * 60)
    print("DERMACARE AI - COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backend: {BASE_URL}")
    
    # 1. Authentication
    token = test_authentication()
    if not token:
        print("\n[FATAL] Cannot authenticate. Aborting tests.")
        return
    
    # 2. API Endpoints with patient-specific data
    diagnosis_result = test_api_endpoints(token)
    
    # 3. AI Relevance Analysis
    test_ai_relevance(token, diagnosis_result)
    
    # 4. Glass Box AI Features
    test_glass_box_ai(diagnosis_result)
    
    # 5. SOAP Generation
    case_data = {
        "complaint": "Painful ulcer on lower lip for 3 weeks",
        "lesion": "Single deep ulcer with rolled borders on lower lip",
        "symptoms": "Painful when eating, slight bleeding",
        "patient_age": 28,
        "geographic_region": "Urban"
    }
    test_soap_generation(token, case_data)
    
    # 6. Drug Interaction
    test_drug_interaction(token)
    
    # 7. Rate Limiting
    test_rate_limiting()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in TEST_RESULTS if r["passed"])
    total = len(TEST_RESULTS)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    print("\nDetailed Results:")
    for r in TEST_RESULTS:
        status = "[OK]" if r["passed"] else "[X]"
        print(f"  {status} {r['name']}")
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return passed == total

if __name__ == "__main__":
    success = run_comprehensive_test()
    exit(0 if success else 1)
