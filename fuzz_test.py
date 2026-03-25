"""
Fuzz Testing - DermaCare AI
==========================
Basic fuzz testing for API endpoints to identify vulnerabilities.
"""
import random
import string
import logging
from typing import Dict, List, Any, Callable
import requests

logger = logging.getLogger("DermaCare_AI.fuzz_test")

BASE_URL = "http://127.0.0.1:8000"

FUZZ_PAYLOADS = {
    "xss": [
        "<script>alert('XSS')</script>",
        "javascript:alert('XSS')",
        "<img src=x onerror=alert('XSS')>",
        "' OR '1'='1",
        "<svg onload=alert('XSS')>",
        "'; DROP TABLE users;--",
        "<iframe src='javascript:alert(1)'>",
    ],
    "sql_injection": [
        "' OR 1=1--",
        "'; DELETE FROM users WHERE 1=1;--",
        "1' AND '1'='1",
        "admin'--",
        "' UNION SELECT * FROM users--",
        "1; DROP TABLE cases;--",
    ],
    "boundary": [
        "a" * 5000,
        "a" * 10000,
        "a" * 20000,
        "\x00\x00\x00",
        "🏥" * 1000,
        "测试" * 500,
        "\n" * 1000,
        "\t" * 1000,
    ],
    "null": [
        None,
        "",
        "null",
        "NULL",
        "undefined",
        "NaN",
        "undefined",
    ],
    "special_chars": [
        "<>\"'&",
        "&&||",
        "(){}[]",
        "/*--*/",
        "@#$$%^&*",
        "\\\"/'\"",
        "..//..//etc/passwd",
    ],
    "unicode": [
        "ℕℤℚℝℂ",
        "∪∩∈∉⊂⊃",
        "中文测试",
        "日本語テスト",
        "한국어테스트",
        "🇮🇳🇺🇸🇬🇧",
    ],
    "valid_age": [
        0, 1, 5, 18, 30, 50, 65, 80, 100, 150, 200, -1, -100, 999999
    ],
}


def generate_random_string(length: int = 10) -> str:
    """Generate random alphanumeric string."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def create_fuzz_payload(base: Dict[str, Any], field: str, payload: Any) -> Dict[str, Any]:
    """Create a fuzz payload by modifying one field."""
    result = base.copy()
    result[field] = payload
    return result


def fuzz_diagnosis_endpoint(token: str, verbose: bool = True) -> Dict[str, Any]:
    """
    Fuzz test the diagnosis endpoint.
    
    Returns dict with test results.
    """
    results = {
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "blocked": 0,
        "crashes": 0,
        "vulnerabilities": [],
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    
    base_payload = {
        "complaint": "Test rash for fuzzing",
        "lesion": "Red patch on arm",
        "symptoms": "Itchy",
        "patient_age": 35,
        "geographic_region": "Urban",
    }
    
    fields_to_fuzz = ["complaint", "lesion", "symptoms", "patient_age", "geographic_region"]
    
    if verbose:
        print("\n[Fuzz Testing: /diagnosis endpoint]")
    
    for category, payloads in FUZZ_PAYLOADS.items():
        for payload in payloads:
            results["total_tests"] += 1
            
            fuzz_data = base_payload.copy()
            fuzz_data[fields_to_fuzz[0]] = payload if not isinstance(payload, int) else str(payload)
            
            try:
                response = requests.post(
                    f"{BASE_URL}/diagnosis",
                    json=fuzz_data,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code in [200, 422]:
                    results["passed"] += 1
                    if verbose:
                        print(f"  [{category}] Payload handled: {str(payload)[:30]}...")
                
                elif response.status_code == 413:
                    results["blocked"] += 1
                    if verbose:
                        print(f"  [{category}] BLOCKED (too large): {str(payload)[:30]}...")
                
                elif response.status_code == 401:
                    results["failed"] += 1
                    if verbose:
                        print(f"  [{category}] Auth failed")
                
                else:
                    results["failed"] += 1
                    if verbose:
                        print(f"  [{category}] Unexpected {response.status_code}")
                        
            except requests.exceptions.Timeout:
                results["crashes"] += 1
                if verbose:
                    print(f"  [{category}] TIMEOUT - potential DoS")
                    
            except Exception as e:
                results["crashes"] += 1
                if verbose:
                    print(f"  [{category}] ERROR: {str(e)[:50]}...")
    
    if verbose:
        print(f"\n  Results: {results['passed']}/{results['total_tests']} passed")
        print(f"  Blocked: {results['blocked']}, Crashes: {results['crashes']}")
    
    return results


def fuzz_soap_endpoint(token: str, verbose: bool = True) -> Dict[str, Any]:
    """Fuzz test the SOAP endpoint."""
    results = {
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "blocked": 0,
        "crashes": 0,
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    
    base_payload = {
        "case_id": "test_case",
        "complaint": "Test complaint",
        "lesion": "Test lesion",
        "patient_age": 30,
    }
    
    if verbose:
        print("\n[Fuzz Testing: /soap endpoint]")
    
    for category, payloads in FUZZ_PAYLOADS.items():
        for payload in payloads:
            results["total_tests"] += 1
            
            fuzz_data = base_payload.copy()
            fuzz_data["complaint"] = str(payload)
            
            try:
                response = requests.post(
                    f"{BASE_URL}/soap",
                    json=fuzz_data,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code in [200, 422]:
                    results["passed"] += 1
                elif response.status_code == 413:
                    results["blocked"] += 1
                else:
                    results["failed"] += 1
                    
            except requests.exceptions.Timeout:
                results["crashes"] += 1
            except Exception:
                results["crashes"] += 1
    
    if verbose:
        print(f"\n  Results: {results['passed']}/{results['total_tests']} passed")
    
    return results


def fuzz_auth_endpoint(verbose: bool = True) -> Dict[str, Any]:
    """Fuzz test auth endpoints."""
    results = {
        "total_tests": 0,
        "sql_injection_blocked": 0,
        "xss_blocked": 0,
        "rate_limited": 0,
    }
    
    if verbose:
        print("\n[Fuzz Testing: /auth endpoints]")
    
    for payload in FUZZ_PAYLOADS["sql_injection"]:
        results["total_tests"] += 1
        try:
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={"username": payload, "password": "test"},
                timeout=5
            )
            if response.status_code in [401, 429]:
                results["sql_injection_blocked"] += 1
                if verbose:
                    print(f"  [SQLi] Blocked: {payload[:30]}...")
        except:
            pass
    
    for payload in FUZZ_PAYLOADS["xss"]:
        results["total_tests"] += 1
        try:
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={"username": payload, "password": "test"},
                timeout=5
            )
            if response.status_code == 401:
                results["xss_blocked"] += 1
        except:
            pass
    
    if verbose:
        print(f"\n  SQL Injection blocked: {results['sql_injection_blocked']}")
        print(f"  XSS payloads blocked: {results['xss_blocked']}")
    
    return results


def run_fuzz_tests(verbose: bool = True) -> Dict[str, Any]:
    """
    Run all fuzz tests.
    
    Returns comprehensive fuzz test results.
    """
    if verbose:
        print("\n" + "=" * 60)
        print("FUZZ TESTING SUITE - DermaCare AI")
        print("=" * 60)
    
    try:
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "arogixai@gmail.com", "password": "Arogix9345@"},
            timeout=10
        )
        if login_response.status_code != 200:
            return {"error": "Authentication failed - cannot run fuzz tests"}
        
        token = login_response.json().get("access_token")
    except Exception as e:
        return {"error": f"Cannot connect to backend: {e}"}
    
    results = {
        "diagnosis_endpoint": fuzz_diagnosis_endpoint(token, verbose),
        "soap_endpoint": fuzz_soap_endpoint(token, verbose),
        "auth_endpoint": fuzz_auth_endpoint(verbose),
    }
    
    if verbose:
        print("\n" + "=" * 60)
        print("FUZZ TEST SUMMARY")
        print("=" * 60)
        total = results["diagnosis_endpoint"]["total_tests"] + results["soap_endpoint"]["total_tests"]
        blocked = results["diagnosis_endpoint"]["blocked"] + results["soap_endpoint"]["blocked"]
        print(f"Total fuzz tests: {total}")
        print(f"Malicious payloads blocked: {blocked}")
        print(f"Crashes detected: {results['diagnosis_endpoint']['crashes'] + results['soap_endpoint']['crashes']}")
    
    return results


if __name__ == "__main__":
    results = run_fuzz_tests(verbose=True)
    print(f"\nResults: {results}")
