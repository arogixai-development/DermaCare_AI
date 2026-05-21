#!/usr/bin/env python3
"""
Investor demo validation harness for DermaCare diagnosis quality.

Checks:
- JSON success, partial success, fallback and recovery rates
- Relevance (complaint-class keyword alignment)
- Latency budgets for quick/accurate modes
- Groq usage/cost efficiency guardrails
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Dict, List

import requests


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TEST_USER = os.getenv("TEST_USER", "arogixai@gmail.com")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "Arogix9345@")
PRICE_PER_REQUEST_USD = float(os.getenv("PRICE_PER_REQUEST_USD", "0.05"))

QUICK_TARGET_SECONDS = 25.0
ACCURATE_TARGET_SECONDS = 60.0


CASES: List[Dict[str, Any]] = [
    {
        "name": "oral_ulcer_case",
        "payload": {
            "complaint": "Painful ulcer on lower lip for 10 days",
            "lesion": "single shallow ulcer with erythematous border on lower lip mucosa",
            "symptoms": "pain while eating, mild bleeding",
            "patient_age": 32,
            "geographic_region": "Urban Chennai",
        },
        "expected_keywords": ["oral", "ulcer", "aphthous", "stomatitis", "traumatic"],
    },
    {
        "name": "annular_fungal_case",
        "payload": {
            "complaint": "Itchy annular rash with central clearing",
            "lesion": "ring shaped erythematous scaly plaque on forearm",
            "symptoms": "itching for 2 weeks",
            "patient_age": 28,
            "geographic_region": "Tropical",
        },
        "expected_keywords": ["tinea", "fungal", "ringworm", "dermatophyte", "eczema"],
    },
    {
        "name": "eczematous_case",
        "payload": {
            "complaint": "Dry itchy patches on both hands for 3 weeks",
            "lesion": "ill defined erythematous dry plaques over dorsal hands",
            "symptoms": "pruritus and dryness",
            "patient_age": 34,
            "geographic_region": "Urban",
        },
        "expected_keywords": ["eczema", "dermatitis", "contact", "atopic", "psoriasis"],
    },
]

ANONYMIZED_CASES: List[Dict[str, Any]] = [
    {
        "name": "anon_psoriasiform_case",
        "payload": {
            "complaint": "Chronic scaly plaques on elbows with intermittent itching",
            "lesion": "well demarcated erythematous plaques with silvery scale",
            "symptoms": "itching and mild fissuring",
            "patient_age": 41,
            "geographic_region": "Semi-urban South India",
        },
        "expected_keywords": ["psoriasis", "eczema", "dermatitis", "contact"],
    },
    {
        "name": "anon_pigmented_case",
        "payload": {
            "complaint": "Pigmented lesion with recent color change",
            "lesion": "asymmetric hyperpigmented patch with irregular border",
            "symptoms": "no pain, gradual darkening",
            "patient_age": 47,
            "geographic_region": "Urban",
        },
        "expected_keywords": ["melanoma", "nevus", "lentigo", "pigmented"],
    },
]


def _login_token() -> str:
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": TEST_USER, "password": TEST_PASSWORD},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but access_token missing")
    return token


def _is_relevant(dx: List[Dict[str, Any]], expected_keywords: List[str]) -> bool:
    text = " ".join(str(d.get("condition", "")).lower() for d in dx[:3])
    return any(k in text for k in expected_keywords)


def _reasoning_specific(payload: Dict[str, Any], reasoning: str) -> bool:
    if not reasoning:
        return False
    r = reasoning.lower()
    complaint_tokens = [t for t in payload.get("complaint", "").lower().split() if len(t) > 4][:6]
    overlap = sum(1 for t in set(complaint_tokens) if t in r)
    return overlap >= 1 and len(r) > 80


def run_mode(token: str, monte_carlo: bool) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "X-API-Version": "v1"}
    mode_name = "accurate" if monte_carlo else "quick"
    requests.delete(f"{BASE_URL}/diagnosis/cache", headers=headers, timeout=30)

    results: List[Dict[str, Any]] = []
    hybrid_cases = CASES + ANONYMIZED_CASES
    for case in hybrid_cases:
        payload = dict(case["payload"])
        payload["monte_carlo"] = monte_carlo
        payload["context"] = f"benchmark_{mode_name}_{case['name']}_{int(time.time() * 1000)}"

        start = time.time()
        r = requests.post(f"{BASE_URL}/diagnosis", json=payload, headers=headers, timeout=180)
        latency = time.time() - start

        item: Dict[str, Any] = {
            "case": case["name"],
            "status_code": r.status_code,
            "latency_s": round(latency, 2),
            "relevant": False,
            "fallback": True,
            "partial": False,
            "reasoning_specific": False,
            "json_success": False,
            "recovered": False,
            "groq_used": False,
            "estimated_cost_usd": 0.0,
        }

        if r.ok:
            data = r.json()
            dx = data.get("differential_diagnosis") or []
            item["relevant"] = _is_relevant(dx, case["expected_keywords"])
            item["fallback"] = bool(data.get("_fallback", False) or data.get("_response_quality") == "fallback")
            item["partial"] = bool(data.get("_partial_llm", False) or data.get("_response_quality") == "partial")
            item["reasoning_specific"] = _reasoning_specific(payload, str(data.get("clinical_reasoning", "")))
            parse_meta = data.get("_parse_meta", {})
            item["json_success"] = parse_meta.get("status") in {"FULL", "PARTIAL"} or bool(dx)
            item["recovered"] = data.get("recovery_stage") in {"ollama_repair_retry", "groq_contingency"}
            item["groq_used"] = data.get("fallback_provider") == "groq"
            item["estimated_cost_usd"] = float((data.get("cost_estimate") or {}).get("estimated_usd", 0.0))
        else:
            item["error"] = r.text[:300]

        results.append(item)

    latencies = [x["latency_s"] for x in results]
    p95 = sorted(latencies)[min(len(latencies) - 1, int(len(latencies) * 0.95))]
    relevant_rate = sum(1 for x in results if x["relevant"]) / len(results)
    fallback_rate = sum(1 for x in results if x["fallback"]) / len(results)
    partial_rate = sum(1 for x in results if x["partial"]) / len(results)
    json_success_rate = sum(1 for x in results if x["json_success"]) / len(results)
    recovery_rate = sum(1 for x in results if x["recovered"]) / len(results)
    groq_usage_rate = sum(1 for x in results if x["groq_used"]) / len(results)
    estimated_cost_per_100 = (sum(x["estimated_cost_usd"] for x in results) / len(results)) * 100
    fallback_dependency_rate = fallback_rate
    reliability_score = min(1.0, json_success_rate + partial_rate)
    revenue_per_100 = PRICE_PER_REQUEST_USD * 100
    gross_margin_pct = ((revenue_per_100 - estimated_cost_per_100) / revenue_per_100) * 100 if revenue_per_100 else 0.0
    reasoning_rate = sum(1 for x in results if x["reasoning_specific"]) / len(results)

    target = ACCURATE_TARGET_SECONDS if monte_carlo else QUICK_TARGET_SECONDS
    return {
        "mode": mode_name,
        "target_seconds": target,
        "latency_p95_s": round(p95, 2),
        "relevant_rate": round(relevant_rate, 3),
        "json_success_rate": round(json_success_rate, 3),
        "fallback_rate": round(fallback_rate, 3),
        "partial_success_rate": round(partial_rate, 3),
        "recovery_rate": round(recovery_rate, 3),
        "groq_usage_rate": round(groq_usage_rate, 3),
        "estimated_cost_per_100_requests": round(estimated_cost_per_100, 4),
        "fallback_dependency_rate": round(fallback_dependency_rate, 3),
        "reliability_score": round(reliability_score, 3),
        "gross_margin_pct": round(gross_margin_pct, 2),
        "reasoning_specific_rate": round(reasoning_rate, 3),
        "target_met": p95 <= target,
        "results": results,
    }


def print_report(report: Dict[str, Any]) -> None:
    print(f"\n=== {report['mode'].upper()} MODE ===")
    print(f"p95 latency: {report['latency_p95_s']}s (target <= {report['target_seconds']}s) -> {report['target_met']}")
    print(f"json_success_rate: {report['json_success_rate']}")
    print(f"relevant_rate: {report['relevant_rate']}")
    print(f"fallback_rate: {report['fallback_rate']}")
    print(f"partial_success_rate: {report['partial_success_rate']}")
    print(f"recovery_rate: {report['recovery_rate']}")
    print(f"groq_usage_rate: {report['groq_usage_rate']}")
    print(f"estimated_cost_per_100_requests: {report['estimated_cost_per_100_requests']}")
    print(f"fallback_dependency_rate: {report['fallback_dependency_rate']}")
    print(f"reliability_score: {report['reliability_score']}")
    print(f"gross_margin_pct: {report['gross_margin_pct']}")
    print(f"reasoning_specific_rate: {report['reasoning_specific_rate']}")
    for row in report["results"]:
        print(
            f" - {row['case']}: status={row['status_code']} latency={row['latency_s']}s "
            f"relevant={row['relevant']} fallback={row['fallback']} partial={row['partial']}"
        )


def main() -> int:
    token = _login_token()
    quick = run_mode(token, monte_carlo=False)
    accurate = run_mode(token, monte_carlo=True)

    print_report(quick)
    print_report(accurate)

    summary = {
        "quick": {
            "json_success_rate": quick["json_success_rate"],
            "partial_success_rate": quick["partial_success_rate"],
            "fallback_rate": quick["fallback_rate"],
            "recovery_rate": quick["recovery_rate"],
            "latency_p95": quick["latency_p95_s"],
            "reliability_score": quick["reliability_score"],
            "fallback_dependency_rate": quick["fallback_dependency_rate"],
            "cost_per_100_requests": quick["estimated_cost_per_100_requests"],
            "gross_margin_pct": quick["gross_margin_pct"],
        },
        "accurate": {
            "json_success_rate": accurate["json_success_rate"],
            "partial_success_rate": accurate["partial_success_rate"],
            "fallback_rate": accurate["fallback_rate"],
            "recovery_rate": accurate["recovery_rate"],
            "latency_p95": accurate["latency_p95_s"],
            "reliability_score": accurate["reliability_score"],
            "fallback_dependency_rate": accurate["fallback_dependency_rate"],
            "cost_per_100_requests": accurate["estimated_cost_per_100_requests"],
            "gross_margin_pct": accurate["gross_margin_pct"],
        },
    }
    print("\nStructured summary:", summary)
    sim = subprocess.run(
        ["python", "scripts/failure_simulation_tests.py"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    print("\nFailure simulation output:\n", sim.stdout.strip() or sim.stderr.strip())

    overall_ok = (
        quick["target_met"]
        and accurate["target_met"]
        and quick["relevant_rate"] >= 0.85
        and accurate["relevant_rate"] >= 0.85
        and quick["fallback_rate"] <= 0.20
        and accurate["fallback_rate"] <= 0.10
        and accurate["groq_usage_rate"] < 0.10
        and quick["gross_margin_pct"] >= 70.0
        and accurate["gross_margin_pct"] >= 70.0
        and sim.returncode == 0
    )
    print("\nGO/NO-GO:", "GO" if overall_ok else "NO-GO")
    print("Investor gate pass:", overall_ok)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
