"""Unit checks for output polish (no HTTP). Run: python scripts/validate_output_polish.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.ai_engine.json_validator import extract_json_from_text  # noqa: E402
from backend.services.diagnosis_service import (  # noqa: E402
    _calibrate_display_confidence,
    _clinical_reasoning_structure_weak,
    _expand_clinical_reasoning_readability,
    _normalize_clinical_reasoning_text,
    _strong_pattern_or_guard_calibration_signal,
)


def test_normalize_dict_like_reasoning():
    s = (
        "{'S': 'Itchy plaques.', 'O': 'Extensor scale.', "
        "'A': 'Psoriasis likely.', 'B': 'KOH if needed.'}"
    )
    out = _normalize_clinical_reasoning_text(s)
    assert "Subjective:" in out and "Itchy plaques." in out
    assert "Objective:" in out and "Assessment:" in out
    assert "\n\n" in out
    assert not out.strip().startswith("{")


def test_normalize_part_dict_reasoning():
    s = (
        "{'Part1': 'Key features: symmetric plaques.', "
        "'Part2': 'Psoriasis fits; tinea less likely.', "
        "'Part3': 'No central clearing.'}"
    )
    out = _normalize_clinical_reasoning_text(s)
    assert "Part1:" in out and "Part2:" in out
    assert "\n\n" in out
    assert not out.strip().startswith("{")


def test_structure_weak():
    assert _clinical_reasoning_structure_weak("") is True
    assert _clinical_reasoning_structure_weak("{'S': 'x'}") is True
    long_cmp = (
        "Features include plaques. Psoriasis fits distribution; tinea is less likely "
        "without annular morphology. Therefore psoriasis is preferred."
    )
    assert _clinical_reasoning_structure_weak(long_cmp) is False


def test_json_extract_prefers_root():
    junk = (
        'Here is output: {"morphology": "annular", "distribution": "arm"} '
        'and then {"differential_diagnosis": [{"condition": "Tinea", '
        '"probability": "70%", "supporting_features": []}], '
        '"clinical_reasoning": "ring lesion", '
        '"soap_note": {"S":"s","O":"o","A":"a","P":"p"}, '
        '"treatment_plan": [], "triage": "Routine"}'
    )
    extracted = extract_json_from_text(junk)
    data = json.loads(extracted)
    assert "differential_diagnosis" in data
    assert data["differential_diagnosis"][0]["condition"] == "Tinea"


def test_confidence_calibration():
    case = {
        "complaint": "scaly",
        "lesion": "Symmetric silvery plaques extensor elbows",
        "symptoms": "",
    }
    result = {
        "clinical_reasoning": "Psoriasis over tinea.",
        "warnings": [],
    }
    assert _strong_pattern_or_guard_calibration_signal(case, result) is True
    meta = {"status": "FULL", "completeness_score": 0.99}
    rel = {"full_parse_confidence_calibration_threshold": 0.9}
    out = _calibrate_display_confidence(0.4, case, result, True, "full", meta, rel)
    assert out >= 0.6
    assert out <= 0.85


def test_expand_readability():
    res = {
        "differential_diagnosis": [
            {"condition": "Psoriasis vulgaris", "probability": "55%"},
            {"condition": "Tinea corporis", "probability": "25%"},
        ],
        "diagnosis": ["Psoriasis vulgaris"],
        "triage": "Routine",
    }
    short = "Symmetric silvery plaques favor psoriasis."
    out = _expand_clinical_reasoning_readability(short, res)
    assert "Key Features:" in out
    assert "Differential:" in out and "Psoriasis vulgaris" in out
    assert "Conclusion:" in out and "Routine" in out
    blob = "{'bad': 'still dict shaped'}"
    out2 = _expand_clinical_reasoning_readability(blob, res)
    assert "Key Features:" in out2 and "Differential:" in out2


def main():
    test_normalize_dict_like_reasoning()
    test_normalize_part_dict_reasoning()
    test_structure_weak()
    test_json_extract_prefers_root()
    test_confidence_calibration()
    test_expand_readability()
    print("validate_output_polish: all checks passed")


if __name__ == "__main__":
    main()
