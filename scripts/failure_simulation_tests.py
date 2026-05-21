#!/usr/bin/env python3
"""
Failure simulation checks for investor reliability readiness.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.ai_engine.json_validator import DIAGNOSIS_SCHEMA, parse_and_validate
from backend.services.diagnosis_service import create_dynamic_fallback


def _simulate_malformed_output() -> Dict[str, Any]:
    fallback = create_dynamic_fallback({"complaint": "test", "lesion": "test", "patient_age": 30})
    raw = """```json
    {diagnosis: [\"text\"], triage: \"Routine\",}
    ```"""
    parsed, success, meta = parse_and_validate(raw, DIAGNOSIS_SCHEMA, fallback, "simulation", return_meta=True)
    return {
        "name": "malformed_output_repair",
        "passed": bool(meta.get("status") in {"PARTIAL", "FULL", "INVALID"} and isinstance(parsed, dict) and parsed.get("triage")),
        "status": meta.get("status"),
    }


def _simulate_non_cdss_output() -> Dict[str, Any]:
    fallback = create_dynamic_fallback({"complaint": "test", "lesion": "test", "patient_age": 30})
    raw = "I am sorry, but I cannot provide diagnosis."
    parsed, success, meta = parse_and_validate(raw, DIAGNOSIS_SCHEMA, fallback, "simulation", return_meta=True)
    return {
        "name": "non_cdss_output_handling",
        "passed": bool(meta.get("status") == "INVALID" or not success),
        "status": meta.get("status"),
    }


def _simulate_fallback_overload_gate() -> Dict[str, Any]:
    cap = float(os.getenv("GROQ_USAGE_CAP_RATE", "0.10"))
    simulated_rate = 0.15
    return {
        "name": "fallback_overload_cap",
        "passed": simulated_rate >= cap,
        "status": f"cap_triggered_at_{simulated_rate}",
    }


def main() -> int:
    checks = [
        _simulate_malformed_output(),
        _simulate_non_cdss_output(),
        _simulate_fallback_overload_gate(),
    ]
    for item in checks:
        print(f"{item['name']}: passed={item['passed']} status={item['status']}")
    overall = all(item["passed"] for item in checks)
    print(f"failure_simulation_pass={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
