#!/usr/bin/env python3
"""
Validate a deployed DermaCare API (e.g. Render) after Cloudflare Tunnel setup.

Usage (Windows PowerShell):
  $env:RENDER_BASE_URL="https://dermacare-api.onrender.com"
  $env:TEST_USER="you@example.com"
  $env:TEST_PASSWORD="yourpassword"
  python scripts/validate_remote_demo.py

Or one-shot:
  python scripts/validate_remote_demo.py https://dermacare-api.onrender.com
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)


def main() -> int:
    base = (
        (sys.argv[1] if len(sys.argv) > 1 else "")
        or os.getenv("RENDER_BASE_URL", "")
    ).rstrip("/")
    if not base:
        print("Set RENDER_BASE_URL or pass URL: python scripts/validate_remote_demo.py <url>")
        return 1

    user = os.getenv("TEST_USER", "")
    password = os.getenv("TEST_PASSWORD", "")

    print(f"Target: {base}\n")

    # Health (public)
    try:
        r = requests.get(f"{base}/health", timeout=60)
        print(f"[1] GET /health -> {r.status_code}")
        if r.ok:
            data = r.json()
            print(f"    ollama_connected: {data.get('ollama_connected')}")
            print(f"    model: {data.get('model')}")
            print(f"    status: {data.get('status')}")
        else:
            print(f"    body: {r.text[:500]}")
    except requests.RequestException as e:
        print(f"[1] GET /health FAILED: {e}")
        return 1

    if not user or not password:
        print("\n[2] Skipping authenticated checks (set TEST_USER and TEST_PASSWORD).")
        print("    Done.")
        return 0

    # Login
    try:
        r = requests.post(
            f"{base}/auth/login",
            json={"username": user, "password": password},
            timeout=60,
        )
        print(f"\n[2] POST /auth/login -> {r.status_code}")
        if not r.ok:
            print(f"    body: {r.text[:500]}")
            return 1
        token = r.json().get("access_token")
        if not token:
            print("    No access_token in response")
            return 1
    except requests.RequestException as e:
        print(f"[2] POST /auth/login FAILED: {e}")
        return 1

    headers = {"Authorization": f"Bearer {token}"}

    # Diagnosis (minimal payload)
    payload: Dict[str, Any] = {
        "complaint": "Itchy patch on forearm 1 week",
        "lesion": "Erythematous scaly plaque",
        "symptoms": "Mild itch",
        "patient_age": 40,
        "geographic_region": "Urban",
    }
    try:
        r = requests.post(
            f"{base}/diagnosis",
            json=payload,
            headers=headers,
            timeout=180,
        )
        print(f"\n[3] POST /diagnosis -> {r.status_code}")
        if r.ok:
            body = r.json()
            dx = body.get("differential_diagnosis") or []
            top = dx[0].get("condition", "") if dx else ""
            print(f"    top_diagnosis: {top[:80]}...")
        else:
            print(f"    body: {r.text[:500]}")
    except requests.RequestException as e:
        print(f"[3] POST /diagnosis FAILED: {e}")
        return 1

    try:
        r = requests.post(
            f"{base}/soap",
            json={
                "case_id": "remote_demo",
                "complaint": payload["complaint"],
                "lesion": payload["lesion"],
                "symptoms": payload["symptoms"],
                "region": payload["geographic_region"],
                "patient_age": payload["patient_age"],
                "diagnoses": ["Eczema", "Contact dermatitis"],
                "treatment": ["Emollient"],
                "tests": ["Clinical exam"],
            },
            headers=headers,
            timeout=120,
        )
        print(f"\n[4] POST /soap -> {r.status_code}")
        if not r.ok:
            print(f"    body: {r.text[:400]}")
    except requests.RequestException as e:
        print(f"\n[4] POST /soap FAILED: {e}")

    try:
        r = requests.post(
            f"{base}/check-interactions",
            json={"drugs": ["Ibuprofen", "Aspirin"]},
            headers=headers,
            timeout=120,
        )
        print(f"\n[5] POST /check-interactions -> {r.status_code}")
        if not r.ok:
            print(f"    body: {r.text[:400]}")
    except requests.RequestException as e:
        print(f"\n[5] POST /check-interactions FAILED: {e}")

    print("\nAll remote checks completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
