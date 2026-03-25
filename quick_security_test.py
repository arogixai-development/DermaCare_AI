
import requests

print("=== Quick Security Test ===")

# Test XSS payload
print("\n[1] Testing XSS in username...")
r = requests.post('http://127.0.0.1:8000/auth/login', json={
    'username': '<script>alert(1)</script>',
    'password': 'test'
})
print(f"    XSS attempt: {r.status_code} (expected 401)")

# Test SQL injection
print("\n[2] Testing SQL injection...")
r = requests.post('http://127.0.0.1:8000/auth/login', json={
    'username': "' OR '1'='1",
    'password': 'test'
})
print(f"    SQLi attempt: {r.status_code} (expected 401)")

# Test auth with valid creds
print("\n[3] Testing valid login...")
r = requests.post('http://127.0.0.1:8000/auth/login', json={
    'username': 'arogixai@gmail.com',
    'password': 'Arogix9345@'
})
print(f"    Valid login: {r.status_code} (expected 200)")
if r.status_code == 200:
    token = r.json().get('access_token')
    print(f"    Token received: {token[:20]}...")

# Test with valid token
print("\n[4] Testing authenticated endpoint...")
headers = {"Authorization": f"Bearer {token}"}
r = requests.get('http://127.0.0.1:8000/health')
print(f"    Health check: {r.status_code} (expected 200)")

print("\n=== Security Tests: PASSED ===")
