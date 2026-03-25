"""
Performance Benchmark - DermaCare AI
==================================
Load and performance testing for API endpoints.
"""
import requests
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"


def get_auth_token():
    """Get authentication token."""
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "arogixai@gmail.com",
        "password": "Arogix9345@"
    })
    if r.status_code == 200:
        return r.json().get("access_token")
    return None


def benchmark_endpoint(url: str, method: str = "GET", headers: dict = None, 
                      data: dict = None, num_requests: int = 10) -> dict:
    """
    Benchmark a single endpoint.
    
    Returns timing statistics.
    """
    timings = []
    errors = 0
    status_codes = {}
    
    for i in range(num_requests):
        start = time.time()
        try:
            if method == "GET":
                r = requests.get(url, headers=headers, timeout=30)
            else:
                r = requests.post(url, json=data, headers=headers, timeout=30)
            
            duration = (time.time() - start) * 1000
            timings.append(duration)
            
            status_codes[r.status_code] = status_codes.get(r.status_code, 0) + 1
            
            if r.status_code >= 400:
                errors += 1
                
        except Exception as e:
            errors += 1
            timings.append(0)
    
    if timings:
        return {
            "endpoint": url,
            "requests": num_requests,
            "errors": errors,
            "min_ms": round(min(timings), 2),
            "max_ms": round(max(timings), 2),
            "avg_ms": round(statistics.mean(timings), 2),
            "median_ms": round(statistics.median(timings), 2),
            "stdev_ms": round(statistics.stdev(timings) if len(timings) > 1 else 0, 2),
            "status_codes": status_codes
        }
    return {"endpoint": url, "error": "No timings recorded"}


def concurrent_benchmark(url: str, headers: dict, data: dict, 
                        concurrent_users: int, total_requests: int) -> dict:
    """
    Benchmark with concurrent users.
    
    Simulates multiple simultaneous users.
    """
    results = []
    errors = 0
    
    def make_request():
        start = time.time()
        try:
            r = requests.post(url, json=data, headers=headers, timeout=60)
            return (time.time() - start) * 1000, r.status_code
        except Exception as e:
            return None, None
    
    with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
        futures = [executor.submit(make_request) for _ in range(total_requests)]
        
        for future in as_completed(futures):
            duration, status = future.result()
            if duration:
                results.append(duration)
            if status and status >= 400:
                errors += 1
    
    if results:
        return {
            "concurrent_users": concurrent_users,
            "total_requests": total_requests,
            "successful": len(results),
            "errors": errors,
            "throughput_rps": round(total_requests / (sum(results) / 1000), 2) if results else 0,
            "avg_ms": round(statistics.mean(results), 2),
            "p50_ms": round(statistics.median(results), 2),
            "p95_ms": round(sorted(results)[int(len(results) * 0.95)] if results else 0, 2),
            "max_ms": round(max(results), 2) if results else 0,
        }
    return {"error": "No results"}


def run_benchmarks():
    """Run all performance benchmarks."""
    print("\n" + "=" * 60)
    print("PERFORMANCE BENCHMARK - DermaCare AI")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    token = get_auth_token()
    if not token:
        print("[ERROR] Cannot authenticate. Exiting.")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n--- Benchmark 1: Health Endpoint ---")
    health_result = benchmark_endpoint(f"{BASE_URL}/health", headers=headers, num_requests=20)
    print(f"  Requests: {health_result['requests']}")
    print(f"  Avg: {health_result['avg_ms']}ms, Min: {health_result['min_ms']}ms, Max: {health_result['max_ms']}ms")
    print(f"  Errors: {health_result['errors']}")
    
    print("\n--- Benchmark 2: Diagnosis API (Sequential) ---")
    diagnosis_data = {
        "complaint": "Test rash for benchmark",
        "lesion": "Red patch on arm",
        "symptoms": "Itchy",
        "patient_age": 35,
        "geographic_region": "Urban"
    }
    diagnosis_result = benchmark_endpoint(
        f"{BASE_URL}/diagnosis", 
        method="POST",
        headers=headers,
        data=diagnosis_data,
        num_requests=5
    )
    print(f"  Requests: {diagnosis_result['requests']}")
    print(f"  Avg: {diagnosis_result['avg_ms']}ms")
    print(f"  Min: {diagnosis_result['min_ms']}ms, Max: {diagnosis_result['max_ms']}ms")
    print(f"  Errors: {diagnosis_result['errors']}")
    
    print("\n--- Benchmark 3: Concurrent Load Test (Diagnosis) ---")
    concurrent_result = concurrent_benchmark(
        f"{BASE_URL}/diagnosis",
        headers=headers,
        data=diagnosis_data,
        concurrent_users=2,
        total_requests=4
    )
    print(f"  Concurrent users: {concurrent_result['concurrent_users']}")
    print(f"  Total requests: {concurrent_result['total_requests']}")
    print(f"  Successful: {concurrent_result['successful']}")
    print(f"  Throughput: {concurrent_result['throughput_rps']} req/s")
    print(f"  Avg: {concurrent_result['avg_ms']}ms, P50: {concurrent_result['p50_ms']}ms, P95: {concurrent_result['p95_ms']}ms")
    
    print("\n--- Benchmark Summary ---")
    print(f"Health endpoint: {health_result['avg_ms']}ms avg")
    print(f"Diagnosis API: {diagnosis_result['avg_ms']}ms avg (sequential)")
    print(f"Diagnosis throughput: {concurrent_result['throughput_rps']} req/s")
    
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    return {
        "health": health_result,
        "diagnosis_sequential": diagnosis_result,
        "diagnosis_concurrent": concurrent_result
    }


if __name__ == "__main__":
    run_benchmarks()
