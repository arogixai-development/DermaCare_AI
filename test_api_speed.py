"""
Test script to measure actual API response time
"""
import requests
import time
import json

API_BASE = "http://127.0.0.1:8000"

def login():
    """Login and get token"""
    response = requests.post(
        f"{API_BASE}/api/auth/login",
        json={"username": "arogix", "password": "Arogix9345@"}
    )
    if response.ok:
        return response.json().get("access_token")
    print(f"Login failed: {response.status_code}")
    return None

def test_diagnosis(token):
    """Test diagnosis endpoint"""
    headers = {"Authorization": f"Bearer {token}"}
    
    test_cases = [
        {
            "complaint": "Red itchy rash on arms",
            "lesion": "Circular, scaly patches",
            "symptoms": "Itching, dry skin",
            "patient_age": 35,
            "geographic_region": "Tamil Nadu",
            "skin_phototype": "Type IV",
            "monte_carlo": False
        }
    ]
    
    for i, case in enumerate(test_cases):
        print(f"\n[Test {i+1}] Sending diagnosis request...")
        print(f"Payload: {json.dumps({k: v for k, v in case.items() if k != 'monte_carlo'}, indent=2)}")
        
        start = time.time()
        response = requests.post(
            f"{API_BASE}/api/diagnosis",
            json=case,
            headers=headers,
            timeout=120
        )
        elapsed = time.time() - start
        
        print(f"Status: {response.status_code}")
        print(f"Time: {elapsed:.2f} seconds")
        
        if response.ok:
            data = response.json()
            print(f"Response keys: {list(data.keys())[:5]}...")
            if "_inference_time" in data:
                print(f"Inference time from response: {data['_inference_time']}")
        else:
            print(f"Error: {response.text[:200]}")

def main():
    print("=" * 50)
    print("DermaCare AI - API Speed Test")
    print("=" * 50)
    
    # Check backend health
    print("\n[Health Check]")
    health = requests.get(f"{API_BASE}/health").json()
    print(f"Ollama Connected: {health.get('ollama_connected')}")
    print(f"Model: {health.get('model')}")
    
    # Login
    print("\n[Login]")
    token = login()
    if not token:
        return
    print(f"Login successful, token: {token[:20]}...")
    
    # Test diagnosis
    print("\n[Diagnosis Test - Quick Mode]")
    test_diagnosis(token)

if __name__ == "__main__":
    main()
