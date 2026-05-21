"""
Cold-start scenario: optionally restart Ollama, then measure first /diagnosis latency.

Logs cold_start_latency_ms and whether the response has expected structured fields.

Usage (from repo root):
  python scripts/cold_start_test.py
  python scripts/cold_start_test.py --restart-ollama
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = os.getenv("DERMACARE_BASE_URL", "http://127.0.0.1:8000")
USER = os.getenv("DERMACARE_TEST_USER", "arogixai@gmail.com")
PASSWORD = os.getenv("DERMACARE_TEST_PASSWORD", "Arogix9345@")


def restart_ollama_windows() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "ollama.exe"], check=False)
    time.sleep(2)
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    time.sleep(3)


def main() -> int:
    parser = argparse.ArgumentParser(description="DermaCare cold-start diagnosis latency test")
    parser.add_argument(
        "--restart-ollama",
        action="store_true",
        help="Kill ollama.exe and start `ollama serve` (Windows). Use with care.",
    )
    args = parser.parse_args()

    if args.restart_ollama:
        restart_ollama_windows()

    tok = requests.post(
        f"{BASE}/auth/login",
        json={"username": USER, "password": PASSWORD},
        timeout=30,
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}
    body = {
        "complaint": "Cold start itch patch",
        "lesion": "erythematous scaly patch",
        "symptoms": "mild pruritus",
        "patient_age": 30,
        "geographic_region": "Urban",
        "monte_carlo": False,
    }
    t0 = time.perf_counter()
    r = requests.post(f"{BASE}/diagnosis", json=body, headers=headers, timeout=180)
    cold_ms = int((time.perf_counter() - t0) * 1000)
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    ok = r.status_code == 200 and isinstance(data, dict)
    structured = ok and all(
        k in data for k in ("differential_diagnosis", "triage", "treatment_plan")
    )
    out = {
        "cold_start_latency_ms": cold_ms,
        "http_status": r.status_code,
        "structured_ok": structured,
    }
    print(json.dumps(out, indent=2))
    return 0 if structured else 1


if __name__ == "__main__":
    raise SystemExit(main())
