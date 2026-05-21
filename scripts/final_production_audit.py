"""End-to-end production audit: health, metrics, auth, 5 clinical cases, failure sim."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = os.getenv("DERMACARE_BASE_URL", "http://127.0.0.1:8000")
AUDIT_USER = os.getenv("DERMACARE_AUDIT_USER", "arogixai@gmail.com")
AUDIT_PASSWORD = os.getenv("DERMACARE_AUDIT_PASSWORD", "Arogix9345@")


def p95(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    i = min(len(s) - 1, int((len(s) - 1) * 0.95))
    return round(s[i], 2)


def structured(d: dict[str, Any]) -> bool:
    if not isinstance(d, dict) or "error" in d:
        return False
    has_dx = bool(d.get("differential_diagnosis")) or bool(d.get("diagnosis"))
    triage_ok = bool(str(d.get("triage", "")).strip())
    tests_ok = d.get("recommended_tests") is not None
    treat_ok = d.get("treatment_plan") is not None
    return has_dx and triage_ok and tests_ok and treat_ok


def plausible(d: dict[str, Any]) -> bool:
    b = json.dumps(d).lower()
    if any(x in b for x in ("as an ai", "i cannot", "i'm sorry", "cannot diagnose")):
        return False
    dx = d.get("differential_diagnosis") or []
    if isinstance(dx, list):
        for i in dx[:5]:
            if isinstance(i, dict) and len(str(i.get("condition", "")).strip()) >= 4:
                return True
    for n in d.get("diagnosis") or []:
        if isinstance(n, str) and len(n.strip()) >= 4:
            return True
    return False


def observability_from_response(d: dict[str, Any]) -> dict[str, bool]:
    keys = (
        "response_type",
        "fallback_reason",
        "parse_error_type",
        "early_return_triggered",
        "time_budget_triggered",
        "cost_estimate",
    )
    return {k: k in d for k in keys}


CASES: list[tuple[str, str, dict[str, Any]]] = [
    (
        "case_1_simple",
        "simple",
        {
            "complaint": "mild itching 3 days",
            "lesion": "small red patch forearm",
            "symptoms": "mild itch",
            "patient_age": 28,
            "geographic_region": "Urban",
            "history_duration": "3 days",
            "monte_carlo": False,
        },
    ),
    (
        "case_2_moderate",
        "moderate",
        {
            "complaint": "scaly spreading 2 weeks mild pain",
            "lesion": "scaly plaque shin",
            "symptoms": "itch tenderness",
            "patient_age": 45,
            "geographic_region": "Temperate",
            "history_duration": "2 weeks",
            "monte_carlo": False,
        },
    ),
    (
        "case_3_complex",
        "complex",
        {
            "complaint": "multiple lesions months itch discoloration",
            "lesion": "macules trunk arms",
            "symptoms": "chronic itch",
            "patient_age": 52,
            "geographic_region": "Semi-urban",
            "history_duration": "6 months",
            "monte_carlo": True,
        },
    ),
    (
        "case_4_ambiguous",
        "ambiguous",
        {
            "complaint": "redness dryness irritation",
            "lesion": "dry erythema cheeks hands",
            "symptoms": "burning itch",
            "patient_age": 34,
            "geographic_region": "Urban",
            "monte_carlo": False,
        },
    ),
    (
        "case_5_low_confidence",
        "vague",
        {
            "complaint": "skin issue",
            "lesion": "something on skin",
            "symptoms": "unsure",
            "patient_age": 40,
            "geographic_region": "Unknown",
            "monte_carlo": True,
        },
    ),
]


def main() -> int:
    issues: list[str] = []

    try:
        h = requests.get(f"{BASE}/health", timeout=30)
        health_ok = h.status_code == 200
        health_body = h.json() if health_ok else {}
    except requests.RequestException as e:
        issues.append(f"health_unreachable:{e}")
        health_body = {}
        health_ok = False

    if not health_ok:
        issues.append("health_not_ok")

    groq_configured = bool(os.getenv("GROQ_API_KEY", "").strip())

    try:
        m0 = requests.get(f"{BASE}/metrics", timeout=30)
        metrics_pre = m0.json() if m0.ok else {}
    except requests.RequestException:
        metrics_pre = {}
        issues.append("metrics_unreachable")

    try:
        tok = requests.post(
            f"{BASE}/auth/login",
            json={"username": AUDIT_USER, "password": AUDIT_PASSWORD},
            timeout=60,
        )
    except requests.RequestException as e:
        print(json.dumps({"error": "auth_unreachable", "detail": str(e)}))
        return 1

    if tok.status_code != 200:
        issues.append(f"auth_failed_http_{tok.status_code}")
        print(
            json.dumps(
                {
                    "error": "auth_failed",
                    "status": tok.status_code,
                    "body": tok.text[:500],
                }
            )
        )
        return 1

    token = tok.json().get("access_token")
    if not token:
        issues.append("auth_no_token")
        print(json.dumps({"error": "no_access_token", "body": tok.text[:500]}))
        return 1

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-API-Version": "v1",
    }

    results: list[dict[str, Any]] = []
    lats: list[float] = []
    fb = partial = ok_n = 0
    last_obs: dict[str, bool] = {}

    for cid, lab, payload in CASES:
        t0 = time.perf_counter()
        try:
            r = requests.post(
                f"{BASE}/diagnosis",
                json=payload,
                headers=headers,
                timeout=240,
            )
        except requests.RequestException as e:
            results.append(
                {
                    "id": cid,
                    "label": lab,
                    "latency_ms": None,
                    "http_status": None,
                    "error": str(e),
                    "response_type": None,
                    "fallback_used": None,
                    "confidence": None,
                    "triage": None,
                    "structured_valid": False,
                    "clinical_plausible": False,
                }
            )
            issues.append(f"{cid}_request_failed")
            continue

        ms = (time.perf_counter() - t0) * 1000
        lats.append(ms)
        d: dict[str, Any] = {}
        try:
            if r.headers.get("content-type", "").startswith("application/json"):
                d = r.json()
        except json.JSONDecodeError:
            issues.append(f"{cid}_bad_json")
        ok = r.status_code == 200 and isinstance(d, dict) and "error" not in d
        if ok:
            ok_n += 1
        rt = str(d.get("response_type", "") or "")
        if rt == "fallback":
            fb += 1
        if rt == "partial":
            partial += 1
        last_obs = observability_from_response(d) if ok else {}
        results.append(
            {
                "id": cid,
                "label": lab,
                "latency_ms": round(ms, 1),
                "http_status": r.status_code,
                "response_type": rt or None,
                "fallback_used": rt == "fallback",
                "confidence": d.get("confidence"),
                "triage": d.get("triage"),
                "structured_valid": structured(d) if ok else False,
                "clinical_plausible": plausible(d) if ok else False,
            }
        )
        if not ok:
            issues.append(f"{cid}_fail_status_{r.status_code}")

    n = len(CASES)
    timeout_spikes_client = sum(1 for x in lats if x > 60_000)

    try:
        m1 = requests.get(f"{BASE}/metrics", timeout=30).json()
    except requests.RequestException:
        m1 = metrics_pre or {}
        issues.append("metrics_post_unreachable")

    dr = m1.get("diagnosis_runtime") or {}
    total_runs = int(dr.get("total_runs") or 0)
    full_o = int(dr.get("full_model_outputs") or 0)
    part_o = int(dr.get("partial_model_outputs") or 0)
    recovery_rate = (
        round((full_o + part_o) / total_runs, 3) if total_runs > 0 else 0.0
    )

    summary = {
        "avg_latency": round(sum(lats) / len(lats), 1) if lats else 0.0,
        "p95_latency": p95(lats),
        "max_latency": round(max(lats), 1) if lats else 0.0,
        "timeout_spikes_over_60s": timeout_spikes_client,
        "fallback_rate": round(fb / n, 3),
        "json_success_rate": round(ok_n / n, 3),
        "partial_success_rate": round(partial / n, 3),
        "recovery_rate": recovery_rate,
        "groq_usage_rate": dr.get("groq_usage_rate", 0),
        "gross_margin_pct": dr.get("gross_margin_pct", 0),
        "cost_per_100_requests": dr.get("cost_estimate_usd_per_100_requests", 0),
        "server_timeout_spike_count": dr.get("timeout_spike_count", 0),
        "server_max_latency_ms": dr.get("max_latency_ms_observed", 0),
    }

    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "failure_simulation_tests.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    sim_ok = p.returncode == 0 and "failure_simulation_pass=True" in (p.stdout or "")
    if not sim_ok:
        issues.append("failure_simulation_failed")
        if p.stderr:
            issues.append(f"failure_sim_stderr:{p.stderr[:200]}")

    struct_n = sum(1 for x in results if x.get("structured_valid"))
    plausible_n = sum(1 for x in results if x.get("clinical_plausible"))

    # Scoring (0–10 per dimension)
    latency_score = 10
    if summary["p95_latency"] > 120_000:
        latency_score = 4
    elif summary["p95_latency"] > 60_000:
        latency_score = 7
    elif summary["max_latency"] > 180_000:
        latency_score = 6

    reliability_score = 10
    if summary["json_success_rate"] < 1.0:
        reliability_score = 5
    if summary["json_success_rate"] < 0.8:
        reliability_score = 2

    accuracy_score = round(10 * plausible_n / n, 1)
    cdss_score = round(10 * struct_n / n, 1)

    fallback_score = 10
    if summary["fallback_rate"] > 0.1:
        fallback_score = 6
    if summary["fallback_rate"] > 0.3:
        fallback_score = 3

    cost_score = 8
    gur = float(summary["groq_usage_rate"] or 0)
    gmp = float(summary["gross_margin_pct"] or 0)
    if gur < 0.15 and gmp >= 60:
        cost_score = 10
    elif gur > 0.5 or gmp < 30:
        cost_score = 5

    frontend_score = 7
    frontend_notes: list[str] = []
    for url in (
        "http://127.0.0.1:3000/",
        "http://127.0.0.1:3000/frontend/index.html",
        "http://127.0.0.1:3000/index.html",
    ):
        try:
            fr = requests.get(url, timeout=5)
            if fr.status_code == 200 and len(fr.text) > 200:
                frontend_score = 8
                frontend_notes.append(f"served:{url}")
                break
        except requests.RequestException:
            continue
    else:
        frontend_notes.append("static_server_not_detected_on_3000")

    scores = [
        latency_score,
        reliability_score,
        accuracy_score,
        cdss_score,
        fallback_score,
        cost_score,
        frontend_score,
    ]
    overall = round(sum(scores) / 7, 1)

    verdict = "GO"
    if not health_body.get("ollama_connected", False):
        verdict = "NO-GO"
        issues.append("ollama_not_connected")
    if summary["json_success_rate"] < 1.0 or struct_n < n:
        verdict = "NO-GO"
    if not sim_ok:
        verdict = "NO-GO"
    if not health_ok:
        verdict = "NO-GO"

    obs_required = (
        "response_type",
        "fallback_reason",
        "parse_error_type",
        "early_return_triggered",
        "time_budget_triggered",
        "cost_estimate",
    )
    obs_missing = [k for k in obs_required if not last_obs.get(k)]
    observability_score_detail = {
        "fields_checked_on_last_successful_response": last_obs,
        "missing_keys_if_any": obs_missing,
        "log_fields_note": "Server logs should include timeout_spike_detected JSON when wall-clock spike; verify in uvicorn output.",
    }
    if ok_n > 0 and obs_missing:
        issues.append(f"observability_keys_missing:{obs_missing}")

    report = {
        "latency_score": latency_score,
        "reliability_score": reliability_score,
        "accuracy_score": accuracy_score,
        "cdss_compliance_score": cdss_score,
        "fallback_score": fallback_score,
        "cost_efficiency_score": cost_score,
        "frontend_score": frontend_score,
        "overall_score": overall,
        "metrics": {
            "avg_latency": summary["avg_latency"],
            "p95_latency": summary["p95_latency"],
            "max_latency": summary["max_latency"],
            "fallback_rate": summary["fallback_rate"],
            "json_success_rate": summary["json_success_rate"],
            "partial_success_rate": summary["partial_success_rate"],
            "recovery_rate": summary["recovery_rate"],
            "groq_usage_rate": summary["groq_usage_rate"],
            "gross_margin_pct": summary["gross_margin_pct"],
            "cost_per_100_requests": summary["cost_per_100_requests"],
            "timeout_spikes_over_60s_client": summary["timeout_spikes_over_60s"],
            "timeout_spike_count_server": summary["server_timeout_spike_count"],
        },
        "case_results": results,
        "issues_found": issues,
        "final_verdict": verdict,
        "health_snapshot": {
            "status": health_body.get("status"),
            "ollama_connected": health_body.get("ollama_connected"),
            "model": health_body.get("model"),
        },
        "config_snapshot": {
            "groq_api_key_configured": groq_configured,
            "base_url": BASE,
        },
        "failure_simulation_ok": sim_ok,
        "frontend_probe": frontend_notes,
        "observability": observability_score_detail,
    }
    print(json.dumps(report, indent=2))
    return 0 if verdict == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
