"""
Deterministic checks for psoriasis vs tinea rank guard (no LLM).

Run from repo root:
  python scripts/validate_psoriasis_guard_quality.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.diagnosis_service import (  # noqa: E402
    _apply_psoriasis_fungal_rank_guard,
    _guard_blocked_by_fungal_morphology,
    _psoriatic_phenotype_hint,
)


def _base_result(*, tinea_first: bool = True):
    if tinea_first:
        ddx = [
            {"condition": "Tinea corporis", "probability": "70%"},
            {"condition": "Psoriasis vulgaris", "probability": "25%"},
        ]
        soap = {
            "S": "Itchy rash",
            "O": "Scaly plaques",
            "A": "Likely tinea corporis.",
            "P": "Topical antifungal twice daily for 2 weeks.",
        }
    else:
        ddx = [
            {"condition": "Psoriasis vulgaris", "probability": "70%"},
            {"condition": "Tinea corporis", "probability": "25%"},
        ]
        soap = {
            "S": "Chronic plaques",
            "O": "Extensor silvery scale",
            "A": "Psoriasis vulgaris preferred.",
            "P": "Topical corticosteroid per protocol.",
        }
    return {
        "differential_diagnosis": ddx,
        "clinical_reasoning": "Initial model reasoning.",
        "confidence": 0.55,
        "soap_note": soap,
        "warnings": [],
    }


def test_psoriasis_case_swap_and_alignment():
    case = {
        "complaint": "Rash",
        "lesion": "Symmetric extensor plaques with silvery scale on elbows",
        "symptoms": "mild itch",
    }
    assert _psoriatic_phenotype_hint(case)
    assert not _guard_blocked_by_fungal_morphology(case)
    r = _base_result(tinea_first=True)
    out = _apply_psoriasis_fungal_rank_guard(case, r)
    lead = out["differential_diagnosis"][0]["condition"]
    assert "psoriasis" in lead.lower(), f"expected psoriasis lead, got {lead}"
    cr = out["clinical_reasoning"]
    assert "Distribution and symmetry strongly support psoriasis" in cr
    assert out["confidence"] >= 0.62
    a = out["soap_note"]["A"]
    assert "psoriasis" in a.lower() or "Psoriasis" in a
    p = out["soap_note"]["P"]
    assert "psoriasis" in p.lower() or "protocol" in p.lower()


def test_fungal_case_guard_skipped():
    case = {
        "complaint": "Itchy annular rash",
        "lesion": "Annular plaque with central clearing on arm",
        "symptoms": "",
    }
    assert _guard_blocked_by_fungal_morphology(case)
    r = _base_result(tinea_first=True)
    out = _apply_psoriasis_fungal_rank_guard(case, r)
    assert out["differential_diagnosis"][0]["condition"].lower().startswith("tinea")


def test_weak_ambiguous_no_forced_swap():
    case = {
        "complaint": "Rash",
        "lesion": "patch on elbow",
        "symptoms": "itchy",
    }
    assert not _psoriatic_phenotype_hint(case)
    r = _base_result(tinea_first=True)
    out = _apply_psoriasis_fungal_rank_guard(case, r)
    assert out["differential_diagnosis"][0]["condition"].lower().startswith("tinea")


def main() -> None:
    test_psoriasis_case_swap_and_alignment()
    test_fungal_case_guard_skipped()
    test_weak_ambiguous_no_forced_swap()
    print("validate_psoriasis_guard_quality: all checks passed")


if __name__ == "__main__":
    main()
