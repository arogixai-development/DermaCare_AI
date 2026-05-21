"""One-off QA: login, metrics, diagnosis (Groq trigger attempt), Ollama-down behavior."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BASE = os.getenv("DERMACARE_BASE_URL", "http://127.0.0.1:8000")
USER = os.getenv("DERMACARE_AUDIT_USER", "arogixai@gmail.com")
PWD = os.getenv("DERMACARE_AUDIT_PASSWORD", "Arogix9345@")


def login() -> str:
    r = requests.post(f"{BASE}/auth/login", json={"username": USER, "password": PWD}, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


def metrics() -> dict:
    r = requests.get(f"{BASE}/metrics", timeout=30)
    r.raise_for_status()
    return r.json().get("diagnosis_runtime") or {}


def diagnose(token: str, payload: dict) -> tuple[int, dict]:
    r = requests.post(
        f"{BASE}/diagnosis",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-API-Version": "v1",
        },
        timeout=240,
    )
    try:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    except json.JSONDecodeError:
        body = {"_raw": r.text[:500]}
    return r.status_code, body


def diagnose_async(token: str, payload: dict) -> tuple[int, dict]:
    r = requests.post(
        f"{BASE}/diagnosis/async",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-API-Version": "v1",
        },
        timeout=240,
    )
    try:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    except json.JSONDecodeError:
        body = {"_raw": r.text[:500]}
    return r.status_code, body


def structured(d: dict) -> bool:
    if "error" in d or "detail" in d and "diagnosis" not in d:
        return False
    return bool(
        (d.get("differential_diagnosis") or d.get("diagnosis"))
        and str(d.get("triage", "")).strip()
        and d.get("recommended_tests") is not None
        and d.get("treatment_plan") is not None
    )


def main() -> int:
    out: dict = {"steps": []}

    tok = login()
    m0 = metrics()
    out["steps"].append({"metrics_before": {"groq_calls_guess": m0.get("parse_status_counts"), "total_runs": m0.get("total_runs"), "groq_usage_rate": m0.get("groq_usage_rate")}})

    # Accurate mode: maximize chance Groq runs if Ollama output unusable
    payload_groq = {
        "complaint": "chronic pruritic plaques elbows knees",
        "lesion": "thick silvery scale extensor surfaces",
        "symptoms": "itch",
        "patient_age": 41,
        "geographic_region": "Temperate",
        "history_duration": "2 years",
        "monte_carlo": True,
    }
    code, body = diagnose(tok, payload_groq)
    out["steps"].append(
        {
            "accurate_diagnosis": {
                "http": code,
                "response_type": body.get("response_type"),
                "fallback_provider": body.get("fallback_provider"),
                "fallback_reason": body.get("fallback_reason"),
                "structured": structured(body) if code == 200 else False,
            }
        }
    )

    m1 = metrics()
    out["steps"].append({"metrics_after": {"total_runs": m1.get("total_runs"), "groq_usage_rate": m1.get("groq_usage_rate"), "fallback_provider_counts": m1.get("fallback_provider_counts")}})

    # Ollama stop (Windows)
    out["ollama_stop"] = {}
    try:
        # Kill main server; app may respawn — still try
        subprocess.run(
            ["taskkill", "/IM", "ollama.exe", "/F"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        subprocess.run(
            ["taskkill", "/IM", "ollama app.exe", "/F"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        time.sleep(2)
        out["ollama_stop"]["taskkill_ran"] = True
    except Exception as e:
        out["ollama_stop"]["error"] = str(e)

    code_off, off_body = diagnose(tok, payload_groq)
    out["steps"].append({"diagnosis_ollama_down_sync": {"http": code_off, "body": off_body}})

    code_a, async_body = diagnose_async(tok, payload_groq)
    out["steps"].append({"diagnosis_ollama_down_async": {"http": code_a, "body": async_body}})

    # Restart Ollama
    out["ollama_restart"] = {}
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        time.sleep(4)
        out["ollama_restart"]["popen_ollama_serve"] = True
    except Exception as e:
        out["ollama_restart"]["error"] = str(e)

    # Wait for health
    for _ in range(15):
        try:
            h = requests.get(f"{BASE}/health", timeout=5).json()
            if h.get("ollama_connected"):
                out["health_after_restart"] = h
                break
        except requests.RequestException:
            pass
        time.sleep(2)
    else:
        out["health_after_restart"] = {"error": "ollama_not_ready_in_time"}

    code_rec, rec_body = diagnose(tok, payload_groq)
    out["steps"].append(
        {
            "diagnosis_after_recovery": {
                "http": code_rec,
                "response_type": rec_body.get("response_type"),
                "fallback_provider": rec_body.get("fallback_provider"),
                "structured": structured(rec_body) if code_rec == 200 else False,
            }
        }
    )

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
