import time
import json
import requests

def test_backend_speed():
    payload = {
        "context": "rural clinic",
        "patient_age": 28,
        "geographic_region": "Tropical",
        "skin_phototype": "III",
        "occupation": "Farmer",
        "complaint": "Circular red itchy patch on the forearm.",
        "lesion": "Ring-shaped red plaque with slight scaling.",
        "symptoms": "Intense itching",
        "tests": "None"
    }
    
    start_time = time.time()
    print("Sending request to backend...")
    try:
        # Check if backend is alive first
        res = requests.get("http://127.0.0.1:8000/")
        print(f"Backend Health: {res.json()}")
        
        # Test diagnosis
        res = requests.post("http://127.0.0.1:8000/diagnosis", json=payload, timeout=300)
        end_time = time.time()
        
        print(f"Status Code: {res.status_code}")
        print(f"Time Taken: {end_time - start_time:.2f} seconds")
        print("AI Response Preview:")
        print(res.json().get('analysis', '')[:200] + "...")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_backend_speed()
