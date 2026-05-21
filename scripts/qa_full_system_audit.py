"""
Full E2E QA audit against live backend (same contract as UI).
Run from repo root with backend on E2E_API_BASE (default http://127.0.0.1:8000).

  python scripts/qa_full_system_audit.py

Outputs: scripts/qa_audit_report.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

BASE = os.environ.get("E2E_API_BASE", "http://127.0.0.1:8000")
LOGIN_USER = os.environ.get("E2E_LOGIN_USER", "arogixai@gmail.com")
LOGIN_PASS = os.environ.get("E2E_LOGIN_PASS", "Arogix9345@")

REQUIRED_TOP_KEYS = {
    "differential_diagnosis",
    "clinical_reasoning",
    "soap_note",
    "confidence",
    "triage",
}


def login(client: httpx.Client) -> str:
    r = client.post(
        f"{BASE}/auth/login",
        json={"username": LOGIN_USER, "password": LOGIN_PASS},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def fetch_health(client: httpx.Client) -> dict:
    r = client.get(f"{BASE}/health", timeout=15.0)
    r.raise_for_status()
    return r.json()


def diagnose_timed(
    client: httpx.Client, token: str, payload: dict
) -> Tuple[dict, float, int]:
    t0 = time.perf_counter()
    r = client.post(
        f"{BASE}/diagnosis",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=180.0,
    )
    elapsed = time.perf_counter() - t0
    if r.status_code == 200:
        return r.json(), elapsed, r.status_code
    try:
        body = r.json()
    except Exception:
        body = {"_detail": r.text[:2000]}
    return {"_http_error": r.status_code, **(body if isinstance(body, dict) else {})}, elapsed, r.status_code


def soap_to_text(soap: Any) -> str:
    if isinstance(soap, dict):
        return "\n".join(f"{k}: {soap.get(k, '')}" for k in ("S", "O", "A", "P") if k in soap)
    return str(soap or "")


def reasoning_quality_score(
    reasoning: str, expect_comparison: bool
) -> Tuple[str, Dict[str, Any]]:
    r = (reasoning or "").strip()
    words = r.split()
    wc = len(words)
    lines = len(r.splitlines())
    has_feat = wc >= 20
    has_cmp = bool(
        re.search(
            r"versus|compared|less likely|more likely|differential|argues against|alternate|exclude|however",
            r,
            re.I,
        )
    )
    has_just = bool(
        re.search(r"therefore|thus|preferred|leading|conclusion|ranked|most consistent", r, re.I)
    )
    dict_blob = r.startswith("{") and ("'S':" in r or '"S":' in r)

    if dict_blob or wc < 15:
        label = "Poor"
    elif expect_comparison and not (has_cmp or has_just):
        label = "Average"
    elif wc >= 80 and has_cmp and has_just and lines >= 3:
        label = "Excellent"
    elif wc >= 40 and (has_cmp or has_just):
        label = "Good"
    else:
        label = "Average"

    return label, {
        "word_count": wc,
        "line_count": lines,
        "multi_line": lines >= 2,
        "feature_extraction_signal": has_feat,
        "differential_comparison_signal": has_cmp,
        "justification_signal": has_just,
        "dict_like_blob": dict_blob,
    }


def soap_quality_score(soap: Any) -> Tuple[str, Dict[str, Any]]:
    if not isinstance(soap, dict):
        return "Poor", {"detail": "not_a_dict"}
    keys = [k for k in ("S", "O", "A", "P") if str(soap.get(k, "")).strip()]
    st = soap_to_text(soap).lower()
    has_tx = bool(re.search(r"topical|antifungal|steroid|treatment|therapy|medication", st))
    has_fu = bool(re.search(r"follow|review|recheck|return|weeks|escalat", st))
    min_len = min(len(str(soap.get(k, ""))) for k in ("S", "O", "A", "P") if k in soap) if keys else 0

    if len(keys) < 4:
        label = "Poor"
    elif min_len < 25 and not has_tx:
        label = "Average"
    elif has_tx and has_fu and min_len >= 30:
        label = "Excellent" if min_len >= 50 else "Good"
    else:
        label = "Average"

    return label, {
        "sections_present": keys,
        "treatment_signal": has_tx,
        "followup_signal": has_fu,
    }


def run_case(
    name: str,
    payload: dict,
    expect: Dict[str, Any],
    client: httpx.Client,
    token: str,
) -> Dict[str, Any]:
    data, elapsed, status = diagnose_timed(client, token, payload)
    if data.get("_http_error"):
        return {
            "case": name,
            "http_status": status,
            "latency_sec": round(elapsed, 3),
            "error": data,
        }
    ddx = data.get("differential_diagnosis") or []
    top = str(ddx[0].get("condition", "")).lower() if ddx and isinstance(ddx[0], dict) else ""
    reasoning = str(data.get("clinical_reasoning") or "")
    conf = data.get("confidence")
    soap = data.get("soap_note")
    soap_txt = soap_to_text(soap)
    schema_ok = REQUIRED_TOP_KEYS.issubset(set(data.keys()) if isinstance(data, dict) else set())
    partial = bool(data.get("_partial_llm"))
    esc = data.get("escalation_instruction")

    acc_exp = expect.get("top_contains", [])
    acc_ok = any(x in top for x in acc_exp) if acc_exp else None

    rq_label, rq_detail = reasoning_quality_score(reasoning, expect.get("expect_comparison", False))
    sq_label, sq_detail = soap_quality_score(soap)

    guard_warn = any(
        "Rank order adjusted" in str(w) for w in (data.get("warnings") or [])
    )
    guard_skip_fungal = expect.get("expect_guard_skip_fungal")

    findings = {
        "case": name,
        "http_status": status,
        "latency_sec": round(elapsed, 3),
        "schema_keys_ok": schema_ok,
        "top_diagnosis": ddx[0] if ddx else None,
        "top3_conditions": [
            str(x.get("condition", "")) for x in ddx[:3] if isinstance(x, dict)
        ],
        "confidence_numeric": conf,
        "response_type": data.get("response_type"),
        "fallback_reason": data.get("fallback_reason"),
        "_partial_llm": partial,
        "escalation_instruction": esc,
        "accuracy_expected_met": acc_ok,
        "reasoning_quality": rq_label,
        "reasoning_detail": rq_detail,
        "soap_quality": sq_label,
        "soap_detail": sq_detail,
        "guard_rank_adjust_warning": guard_warn,
        "clinical_reasoning_excerpt": reasoning[:600] + ("…" if len(reasoning) > 600 else ""),
        "soap_excerpt": soap_txt[:500] + ("…" if len(soap_txt) > 500 else ""),
    }

    if guard_skip_fungal is True:
        findings["guard_expect_skip_for_fungal_morphology"] = True

    return findings


def main() -> None:
    cases: List[Tuple[str, dict, dict]] = [
        (
            "case_1_psoriasis_accurate",
            {
                "context": "",
                "complaint": "Itchy scaly plaques on elbows for one month",
                "lesion": "Symmetric well-demarcated plaques, silvery-white scale, extensor elbows",
                "symptoms": "Pruritus",
                "tests": "None",
                "geographic_region": "North America",
                "patient_age": 42,
                "monte_carlo": True,
            },
            {
                "top_contains": ["psoriasis"],
                "expect_comparison": True,
            },
        ),
        (
            "case_2_fungal_quick",
            {
                "context": "",
                "complaint": "Round itchy patch with central clearing",
                "lesion": "Annular lesion with ring-like scaly border",
                "symptoms": "",
                "tests": "None",
                "geographic_region": "North America",
                "patient_age": 35,
                "monte_carlo": False,
            },
            {
                "top_contains": ["tinea", "fungal", "ring", "dermatophyte"],
                "expect_comparison": False,
                "expect_guard_skip_fungal": True,
            },
        ),
        (
            "case_3_weak_quick",
            {
                "context": "",
                "complaint": "Small itchy spot",
                "lesion": "",
                "symptoms": "",
                "tests": "None",
                "geographic_region": "Unknown",
                "patient_age": 22,
                "monte_carlo": False,
            },
            {
                "top_contains": [],
                "expect_comparison": False,
            },
        ),
        (
            "case_4_ambiguous_quick",
            {
                "context": "",
                "complaint": "Red itchy scaly rash on trunk for 2 weeks",
                "lesion": "Ill-defined erythematous scaly patches, unclear if annular",
                "symptoms": "Itch, no fever",
                "tests": "None",
                "geographic_region": "Europe",
                "patient_age": 50,
                "monte_carlo": False,
            },
            {
                "top_contains": [],
                "expect_comparison": True,
            },
        ),
        (
            "case_5_low_signal_quick",
            {
                "context": "",
                "complaint": "rash",
                "lesion": "",
                "symptoms": "",
                "tests": "",
                "geographic_region": "",
                "patient_age": 30,
                "monte_carlo": False,
            },
            {
                "top_contains": [],
                "expect_comparison": False,
            },
        ),
    ]

    report: Dict[str, Any] = {
        "api_base": BASE,
        "health_before": None,
        "health_after": None,
        "cases": [],
    }

    with httpx.Client() as client:
        report["health_before"] = fetch_health(client)
        token = login(client)
        for name, payload, expect in cases:
            report["cases"].append(run_case(name, payload, expect, client, token))
        report["health_after"] = fetch_health(client)

    rt = report["health_after"].get("diagnosis_runtime", {})
    p95 = rt.get("latency_ms_p95", 0)

    # Aggregate scoring (0-10) — strict, from observed behavior only
    c1 = next(x for x in report["cases"] if x["case"] == "case_1_psoriasis_accurate")
    c2 = next(x for x in report["cases"] if x["case"] == "case_2_fungal_quick")

    def q_to_num(label: str) -> float:
        return {"Poor": 3, "Average": 5.5, "Good": 7.5, "Excellent": 9.5}.get(label, 5)

    acc_pts = 0.0
    if c1.get("accuracy_expected_met"):
        acc_pts += 4
    else:
        acc_pts += 1
    if c2.get("accuracy_expected_met"):
        acc_pts += 3
    else:
        acc_pts += 1
    # weak/ambiguous/low: no single "correct" top — credit safe provisional wording
    for c in report["cases"][2:]:
        top3 = c.get("top3_conditions") or []
        prov = sum(1 for t in top3 if "provisional" in (t or "").lower() or "unable" in (t or "").lower())
        if len(top3) >= 2 or prov:
            acc_pts += 1.0
        else:
            acc_pts += 0.5
    accuracy_score = min(10.0, acc_pts)

    reasoning_scores = [q_to_num(c["reasoning_quality"]) for c in report["cases"]]
    reasoning_score = round(sum(reasoning_scores) / len(reasoning_scores), 2)

    soap_scores = [q_to_num(c["soap_quality"]) for c in report["cases"]]
    soap_score = round(sum(soap_scores) / len(soap_scores), 2)

    # Confidence alignment: case1 should be >= 0.6 if polish deployed; penalize mismatch
    conf_num = c1.get("confidence_numeric")
    if isinstance(conf_num, (int, float)) and c1.get("response_type") == "full":
        if conf_num >= 0.6:
            conf_align = 8.5
        elif conf_num >= 0.45:
            conf_align = 6.0
        else:
            conf_align = 4.0
    else:
        conf_align = 5.5

    partial_rate = sum(1 for c in report["cases"] if c.get("_partial_llm")) / len(report["cases"])
    stability_score = max(2.0, 10.0 - partial_rate * 12.0 - (0.5 if not c1["schema_keys_ok"] else 0))

    latencies = [c["latency_sec"] for c in report["cases"]]
    max_lat = max(latencies)
    perf = 8.0 if max_lat < 35 and p95 < 50000 else (5.5 if max_lat < 90 else 4.0)
    performance_score = round(perf, 2)

    ux_score = round(
        (
            q_to_num(c1["reasoning_quality"])
            + (8 if c1["reasoning_detail"].get("multi_line") else 5)
            + q_to_num(c1["soap_quality"])
        )
        / 3,
        2,
    )

    issues: List[str] = []
    critical: List[str] = []

    if not c1.get("accuracy_expected_met"):
        critical.append("CASE1: Psoriasis not ranked first — major CDSS failure for classic plaque presentation.")
    if c1["reasoning_detail"].get("dict_like_blob"):
        issues.append("CASE1: clinical_reasoning still dict-like blob (polish may not be deployed on this server).")
    if isinstance(conf_num, (int, float)) and conf_num < 0.6 and c1.get("response_type") == "full":
        issues.append(
            f"CASE1: Numeric confidence {conf_num} below 0.6 for strong teaching case (calibration or stale build)."
        )
    if partial_rate >= 0.4:
        issues.append(f"High partial/failsafe rate in sample: {partial_rate:.0%} (phi3 parse / Quick mode).")
    if not c2.get("accuracy_expected_met"):
        issues.append("CASE2: Fungal morphology did not yield tinea-class lead diagnosis in API response.")

    recs = [
        "Restart backend from current main branch so output-polish (reasoning normalizer, confidence calibration, JSON scoring) is active.",
        "Point frontend API_BASE to the same backend instance used for validation.",
        "Consider enabling Groq fallback for Quick mode in reliability config if parse failure rate remains high (policy decision).",
        "Add Playwright smoke tests for login + one diagnosis flow to catch UI regressions.",
    ]

    overall = round(
        (
            accuracy_score
            + reasoning_score
            + soap_score
            + conf_align
            + stability_score
            + performance_score
            + ux_score
        )
        / 7,
        2,
    )

    final_status = "GO" if overall >= 7.0 and len(critical) == 0 else "NO-GO"

    out = {
        "accuracy_score": round(accuracy_score, 2),
        "reasoning_score": reasoning_score,
        "soap_score": soap_score,
        "confidence_score": round(conf_align, 2),
        "stability_score": round(stability_score, 2),
        "performance_score": performance_score,
        "ux_score": ux_score,
        "overall_score": overall,
        "issues_found": issues,
        "critical_bugs": critical,
        "recommendations": recs,
        "final_status": final_status,
        "diagnosis_runtime_after": rt,
        "per_case": report["cases"],
    }

    out_path = ROOT / "scripts" / "qa_audit_report.json"
    out_path.write_text(json.dumps({"full_report": report, "summary": out}, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
