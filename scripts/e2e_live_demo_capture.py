"""
Live E2E capture: same /diagnosis contract as frontend (JWT + JSON body).

Usage (backend on 127.0.0.1:8000):
  python scripts/e2e_live_demo_capture.py

Credentials: set E2E_LOGIN_USER / E2E_LOGIN_PASS or defaults to repo bootstrap admin
(see backend/routes/auth_routes.py init_default_admin).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

BASE = os.environ.get("E2E_API_BASE", "http://127.0.0.1:8000")
LOGIN_USER = os.environ.get("E2E_LOGIN_USER", "arogixai@gmail.com")
LOGIN_PASS = os.environ.get("E2E_LOGIN_PASS", "Arogix9345@")


def login(client: httpx.Client) -> str:
    r = client.post(
        f"{BASE}/auth/login",
        json={"username": LOGIN_USER, "password": LOGIN_PASS},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def diagnose(client: httpx.Client, token: str, payload: dict) -> dict:
    r = client.post(
        f"{BASE}/diagnosis",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=120.0,
    )
    r.raise_for_status()
    return r.json()


def soap_to_text(soap) -> str:
    if isinstance(soap, dict):
        parts = []
        for k in ("S", "O", "A", "P"):
            if k in soap:
                parts.append(f"{k}: {soap[k]}")
        return "\n".join(parts)
    return str(soap or "")


def analyze_response(name: str, data: dict, case_meta: dict) -> dict:
    ddx = data.get("differential_diagnosis") or []
    top3 = ddx[:3]
    names = [str(x.get("condition", "")) for x in top3 if isinstance(x, dict)]
    conf = data.get("confidence")
    reasoning = str(data.get("clinical_reasoning") or data.get("reasoning") or "")
    soap = data.get("soap_note")
    soap_text = soap_to_text(soap)
    warnings = data.get("warnings") or []
    fb = data.get("_fallback_reason") or data.get("fallback_reason")
    partial = data.get("_partial_llm")
    words = reasoning.split()
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", reasoning.strip()) if s.strip()]
    lines_r = len(reasoning.splitlines()) if reasoning else 0
    lines_s = len(soap_text.splitlines()) if soap_text else 0

    guard_hint = "Distribution and symmetry strongly support psoriasis" in reasoning
    guard_warn = any(
        "Rank order adjusted for classic psoriatic distribution" in str(w)
        for w in warnings
    )
    guard_applied = guard_hint or guard_warn

    # Expected accuracy rubric (clinical teaching case)
    if name == "case_1_psoriasis":
        top_ok = any("psoriasis" in n.lower() for n in names[:1])
        acc = "YES" if top_ok else "NO"
        acc_note = "Psoriasis should lead for symmetric extensor silvery plaques." if not top_ok else "Top slot aligns with plaque psoriasis pattern."
    elif name == "case_2_fungal":
        top_ok = any(
            "tinea" in n.lower() or "fungal" in n.lower() or "ring" in n.lower()
            for n in names[:1]
        )
        acc = "YES" if top_ok else "NO"
        acc_note = "Tinea/dermatophyte expected for annular central clearing." if not top_ok else "Top slot aligns with ringworm morphology."
    else:
        acc = "N/A"
        acc_note = "Weak input: broad DDx acceptable; no forced single diagnosis."

    feat = bool(reasoning) and len(words) > 15
    diffcmp = bool(
        re.search(
            r"versus|compared|rather than|argues against|differential|however",
            reasoning,
            re.I,
        )
    )
    just = bool(re.search(r"therefore|thus|preferred|leading|ranked|conclusion", reasoning, re.I))

    soap_detail = all(
        len(str((soap or {}).get(k, "") if isinstance(soap, dict) else "")) > 20
        for k in ("S", "O", "A", "P")
    ) if isinstance(soap, dict) else len(soap_text) > 80
    tx_fu = bool(
        re.search(r"follow|review|recheck|KOH|topical|steroid|antifungal", soap_text, re.I)
    )

    return {
        "case": name,
        "case_meta": case_meta,
        "top_3_diagnoses": names,
        "confidence": conf,
        "clinical_reasoning_full": reasoning,
        "soap_note_full": soap_text if isinstance(soap, dict) else soap,
        "fallback_metadata": {
            "_fallback": data.get("_fallback"),
            "_partial_llm": partial,
            "_fallback_reason": fb,
            "response_type": data.get("response_type"),
        },
        "quality": {
            "accuracy_top_correct": acc,
            "accuracy_note": acc_note,
            "reasoning_word_count": len(words),
            "reasoning_sentence_count": len(sentences),
            "has_feature_extraction": feat,
            "has_differential_comparison": diffcmp,
            "has_justification": just,
            "soap_sections_substantive": soap_detail,
            "soap_treatment_or_followup": tx_fu,
            "lines_reasoning": max(lines_r, 1 if reasoning else 0),
            "lines_soap": max(lines_s, 1 if soap_text else 0),
            "guard_applied_signal": guard_applied,
        },
    }


def main() -> None:
    cases = [
        (
            "case_1_psoriasis",
            {
                "context": "",
                "complaint": "Itchy, scaly plaques on elbows for 3 weeks",
                "lesion": "Symmetric plaques, silvery scale, extensor elbows",
                "symptoms": "Pruritus",
                "tests": "None",
                "geographic_region": "Temperate North America",
                "patient_age": 45,
                "monte_carlo": True,
            },
        ),
        (
            "case_2_fungal",
            {
                "context": "",
                "complaint": "Round itchy patch with central clearing",
                "lesion": "Annular lesion, ring-like border",
                "symptoms": "",
                "tests": "None",
                "geographic_region": "North America",
                "patient_age": 32,
                "monte_carlo": False,
            },
        ),
        (
            "case_3_weak",
            {
                "context": "",
                "complaint": "Small itchy patch on forearm",
                "lesion": "",
                "symptoms": "",
                "tests": "None",
                "geographic_region": "Unknown",
                "patient_age": 28,
                "monte_carlo": False,
            },
        ),
    ]

    out_path = ROOT / "scripts" / "e2e_live_demo_results.json"
    report = {}

    with httpx.Client() as client:
        token = login(client)
        for key, payload in cases:
            raw = diagnose(client, token, payload)
            report[key] = analyze_response(key, raw, {"request_payload": payload})

    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
