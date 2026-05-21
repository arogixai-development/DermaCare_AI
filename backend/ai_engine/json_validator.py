"""
JSON Validator for DermaCare AI
===============================
Provides robust JSON parsing, schema validation, retry logic, and
fallback structured responses to ensure the frontend always receives
well-formed JSON from the LLM pipeline.
"""

import json
import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("DermaCare_AI.json_validator")

VALID_STATUS_FULL = "FULL"
VALID_STATUS_PARTIAL = "PARTIAL"
VALID_STATUS_INVALID = "INVALID"

# ──────────────────────────────────────────────────────────────────────────────
# Schema definitions
# Each schema has:
#   required_keys  – {field_name: expected_python_type}
#   defaults       – {field_name: value_to_use_when_missing}
# ──────────────────────────────────────────────────────────────────────────────

DIAGNOSIS_SCHEMA: Dict[str, Any] = {
    # Slightly lower bar for PARTIAL to reduce unnecessary generic fallbacks (still requires core keys).
    "partial_threshold": 0.42,
    "required_keys": {
        "differential_diagnosis": list,
        "clinical_reasoning":     str,
    },
    "defaults": {
        "differential_diagnosis": [
            {"condition": "Unable to determine", "probability": "N/A", "supporting_features": []}
        ],
        "clinical_reasoning":     "Analysis could not be completed. Please retry.",
        "soap_note": {
            "S": "Unable to complete subjective summary.",
            "O": "No objective data available.",
            "A": "Unable to assess reliably.",
            "P": "Retry with additional structured clinical information."
        },
        "treatment_plan":         [
            {"medication": "Clinical evaluation recommended", "application": "N/A", "duration": "N/A", "education": "Consult dermatologist"}
        ],
        "triage":                "Routine",
    },
}

# Legacy field mappings for backward compatibility
LEGACY_FIELD_MAPPING = {
    "diagnoses": "differential_diagnosis",
    "reasoning": "clinical_reasoning",
    "soap": "soap_note",
    "treatment": "treatment_plan",
    "tests": "recommended_tests",
    "referral": "referral_indicators",
}

DRUG_INTERACTION_SCHEMA: Dict[str, Any] = {
    "required_keys": {
        "summary":                     str,
        "major_interactions":          list,
        "moderate_minor_interactions": list,
        "clinical_recommendation":     str,
        "patient_education":           str,
    },
    "defaults": {
        "summary":                     "",
        "major_interactions":          [],
        "moderate_minor_interactions": [],
        "clinical_recommendation":     "",
        "patient_education":           "",
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# Fallback responses  (used when ALL retries are exhausted)
# ──────────────────────────────────────────────────────────────────────────────

DIAGNOSIS_FALLBACK: Dict[str, Any] = {
    "differential_diagnosis": [
        {"condition": "Unable to determine diagnosis at this time", "probability": "N/A", "supporting_features": []}
    ],
    "clinical_reasoning": "AI response could not be parsed. Please retry.",
    "soap_note": "S: AI parsing failed\nO: No data\nA: Unable to assess\nP: Please retry the analysis",
    "treatment_plan": [
        {"medication": "Symptomatic management pending proper evaluation", "application": "N/A", "duration": "N/A", "education": "Consult a specialist"}
    ],
    "triage": "Routine",
    "referral_indicators": ["Consult a specialist"],
    "follow_up": "Retry analysis with complete clinical information",
    "_fallback": True,
    "_error":    "JSON parsing / schema validation failed after retry",
}

DRUG_INTERACTION_FALLBACK: Dict[str, Any] = {
    "summary":                     (
        "Drug interaction analysis could not be completed. Please retry."
    ),
    "major_interactions":          [],
    "moderate_minor_interactions": [],
    "clinical_recommendation":     (
        "Please retry or consult a clinical pharmacologist."
    ),
    "patient_education":           "Unable to provide recommendations at this time.",
    "_fallback":        True,
    "_error":           "JSON parsing / schema validation failed after retry",
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_balanced_json(candidate: str) -> str:
    """Extract the first balanced JSON object substring from candidate text."""
    start = candidate.find("{")
    if start == -1:
        return ""

    depth = 0
    in_string = False
    escaped = False
    for i, ch in enumerate(candidate[start:], start):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return candidate[start:i + 1]
    return ""


def _repair_json_chunk(chunk: str) -> str:
    """Apply the same repairs as the main extractor to a single JSON substring."""
    text = chunk.strip()
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    text = re.sub(r",\s*([\]}])", r"\1", text)
    text = re.sub(r'"condition\w+":\s*"(\d+%)"', r'"probability": "\1"', text)
    text = re.sub(r'"condition\w+":', r'"condition":', text)
    text = re.sub(r'"supportingth:|"supporting\w+features:', r'"supporting_features":', text)
    text = re.sub(r"'([^']+)':\s*'", r'"\1": "', text)
    text = re.sub(r":\s*'([^']*)'", r': "\1"', text)
    text = re.sub(r'"([a-zA-Z]{30,})":', lambda m: m.group(0), text)
    text = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)', r'\1"\2"\3', text)
    text = re.sub(r"\[\s*,+", "[", text)
    text = re.sub(r",+\s*\]", "]", text)
    return text


def _score_diagnosis_dict(d: dict) -> int:
    """Prefer root CDSS objects over embedded lesion_analysis fragments."""
    score = min(len(str(d)) // 8, 400)
    if "differential_diagnosis" in d:
        score += 2000
        dd = d.get("differential_diagnosis")
        if isinstance(dd, list):
            score += min(len(dd) * 12, 120)
    else:
        score -= 900
    for k, w in (
        ("clinical_reasoning", 90),
        ("soap_note", 90),
        ("treatment_plan", 45),
        ("triage", 25),
        ("recommended_tests", 25),
    ):
        if k in d:
            score += w
    if "morphology" in d and "differential_diagnosis" not in d:
        score -= 650
    if "color_patterns" in d and "differential_diagnosis" not in d:
        score -= 450
    if "ABCDE_assessment" in d and "differential_diagnosis" not in d:
        score -= 350
    return score


def _collect_scored_json_candidates(source: str) -> List[Tuple[str, int]]:
    """Enumerate balanced objects, repair, parse, score; return (repaired_json_str, score)."""
    out: List[Tuple[str, int]] = []
    i = 0
    while i < len(source):
        if source[i] != "{":
            i += 1
            continue
        chunk = _extract_balanced_json(source[i:])
        if not chunk:
            i += 1
            continue
        repaired = _repair_json_chunk(chunk)
        try:
            parsed = json.loads(repaired)
        except json.JSONDecodeError:
            i += max(1, len(chunk))
            continue
        if isinstance(parsed, dict):
            out.append((repaired, _score_diagnosis_dict(parsed)))
        i += max(1, len(chunk))
    return out


def extract_json_from_text(text: str) -> str:
    """
    Extract and repair JSON from LLM output.
    Handles garbage after JSON and common LLM errors.
    """
    if not text:
        return ""

    text = text.strip()
    # Strip common model "thinking" wrappers that break json.loads
    text = re.sub(
        r"<think>.*?</think>|"
        r"<redacted_reasoning>.*?</redacted_reasoning>|"
        r"<reasoning>.*?</reasoning>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = text.strip()

    first_brace = text.find("{")
    if first_brace > 0:
        text = text[first_brace:]

    # Remove markdown code fences
    if "```" in text:
        parts = [p.strip() for p in text.split("```")]
        json_like_parts = [p for p in parts if "{" in p]
        if json_like_parts:
            text = max(json_like_parts, key=len)

    # Prefer extraction anchored around diagnosis key if present.
    candidate = text
    for needle in ('"differential_diagnosis"', "'differential_diagnosis'"):
        if needle in text:
            anchor = text.find(needle)
            anchor_start = text.rfind("{", 0, anchor)
            if anchor_start != -1:
                candidate = text[anchor_start:]
            break

    scored = _collect_scored_json_candidates(candidate)
    if not scored:
        scored = _collect_scored_json_candidates(text)
    if not scored:
        return "{}"

    text = max(scored, key=lambda x: x[1])[0]

    # Final sanity pass.
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        return "{}"



def validate_schema(data: dict, schema: Dict[str, Any]) -> Tuple[bool, dict]:
    """Validate and coerce required schema fields."""
    required_keys: Dict[str, type] = schema["required_keys"]
    defaults: Dict[str, Any]       = schema["defaults"]

    is_valid = True
    coerced  = dict(data)

    for key, expected_type in required_keys.items():
        value = coerced.get(key)

        if value is None:
            logger.warning(
                "Schema validation: missing key '%s' – using default %r",
                key, defaults.get(key),
            )
            coerced[key] = defaults.get(key, None)
            is_valid = False
            continue

        if not isinstance(value, expected_type):
            try:
                if expected_type is list and isinstance(value, str):
                    coerced[key] = [value]
                elif expected_type is str and isinstance(value, list):
                    coerced[key] = " ".join(str(v) for v in value)
                else:
                    coerced[key] = expected_type(value)
                logger.warning(
                    "Schema validation: coerced key '%s' from %s to %s",
                    key, type(value).__name__, expected_type.__name__,
                )
            except Exception as exc:
                logger.error(
                    "Schema validation: cannot coerce key '%s' (%s) – using default. Reason: %s",
                    key, type(value).__name__, exc,
                )
                coerced[key] = defaults.get(key)
                is_valid = False

    return is_valid, coerced


def _coerce_field(value: Any, expected_type: type, default: Any) -> Tuple[Any, bool]:
    if value is None:
        return default, False
    if isinstance(value, expected_type):
        return value, True
    try:
        if expected_type is list and isinstance(value, str):
            return [value], True
        if expected_type is str and isinstance(value, list):
            return " ".join(str(v) for v in value), True
        return expected_type(value), True
    except Exception:
        return default, False


def validate_with_status(
    data: dict, schema: Dict[str, Any], partial_threshold: float = 0.5
) -> Dict[str, Any]:
    """Field-level validation with FULL/PARTIAL/INVALID status."""
    required_keys: Dict[str, type] = schema["required_keys"]
    defaults: Dict[str, Any] = schema["defaults"]
    result = dict(data) if isinstance(data, dict) else {}
    missing_fields: List[str] = []
    invalid_fields: List[str] = []
    valid_count = 0

    for key, expected_type in required_keys.items():
        value = result.get(key)
        if value is None or value == "":
            missing_fields.append(key)
            result[key] = defaults.get(key)
            continue
        coerced, ok = _coerce_field(value, expected_type, defaults.get(key))
        result[key] = coerced
        if ok and coerced not in (None, "", [], {}):
            valid_count += 1
        elif value in (None, "", [], {}):
            missing_fields.append(key)
        else:
            invalid_fields.append(key)

    required_total = max(1, len(required_keys))
    completeness_score = round(valid_count / required_total, 3)
    if completeness_score >= 0.99 and not missing_fields and not invalid_fields:
        status = VALID_STATUS_FULL
    elif completeness_score >= partial_threshold:
        status = VALID_STATUS_PARTIAL
    else:
        status = VALID_STATUS_INVALID

    return {
        "status": status,
        "data": result,
        "missing_fields": missing_fields,
        "invalid_fields": invalid_fields,
        "completeness_score": completeness_score,
    }


def convert_legacy_to_new(data: dict) -> dict:
    """
    Convert legacy field names to new field names for backward compatibility.
    """
    result = dict(data)
    
    # Map legacy fields to new fields
    for legacy_key, new_key in LEGACY_FIELD_MAPPING.items():
        if legacy_key in result and new_key not in result:
            result[new_key] = result[legacy_key]
    
    # Convert legacy lists to new treatment_plan format
    if "treatment" in data and "treatment_plan" not in result:
        treatments = data.get("treatment", [])
        if isinstance(treatments, list):
            result["treatment_plan"] = [
                {"medication": t if isinstance(t, str) else str(t), 
                 "application": "Per clinical guidelines", 
                 "duration": "As directed", 
                 "education": "Follow prescribing instructions"}
                for t in treatments
            ]
    
    # Convert diagnoses to differential_diagnosis format
    if "diagnoses" in data and "differential_diagnosis" not in result:
        diagnoses = data.get("diagnoses", [])
        if isinstance(diagnoses, list):
            result["differential_diagnosis"] = [
                {"condition": d if isinstance(d, str) else str(d), 
                 "probability": "N/A", 
                 "supporting_features": []}
                for d in diagnoses
            ]
    
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Main public API
# ──────────────────────────────────────────────────────────────────────────────

def parse_and_validate(
    raw_str: str,
    schema: Dict[str, Any],
    fallback: Dict[str, Any],
    context: str = "",
    return_meta: bool = False,
) -> Tuple[Dict[str, Any], bool]:
    """
    Parse *raw_str* as JSON, validate against *schema*, and return a
    guaranteed-structurally-correct dict.
    """
    logger.info(
        f"[{context}] parse_and_validate called with raw_str length: {len(raw_str) if raw_str else 0}"
    )
    partial_threshold = float(schema.get("partial_threshold", 0.5))

    if not raw_str or not raw_str.strip():
        logger.error(f"[{context}] LLM returned an empty or whitespace-only response")
        meta = {
            "parsed": False,
            "schema_valid": False,
            "used_fallback": True,
            "missing_required_keys": list(schema.get("required_keys", {}).keys()),
            "cleaned_length": 0,
            "raw_length": 0,
            "status": VALID_STATUS_INVALID,
            "parse_error_type": "empty_response",
            "invalid_fields": [],
            "completeness_score": 0.0,
        }
        return (dict(fallback), False, meta) if return_meta else (dict(fallback), False)

    cleaned = extract_json_from_text(raw_str)
    logger.info(f"[{context}] Extracted JSON length: {len(cleaned)}")
    logger.info(f"[{context}] Extracted JSON preview: {repr(cleaned[:120])}")

    try:
        parsed = json.loads(cleaned)
        logger.info(f"[{context}] JSON parsed successfully, keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}")
    except json.JSONDecodeError as exc:
        logger.error(f"[{context}] json.loads() FAILED: {exc}")
        logger.error(f"[{context}] Raw response (first 500 chars): {raw_str[:500]}")
        logger.error(f"[{context}] Cleaned response (first 500 chars): {cleaned[:500]}")
        meta = {
            "parsed": False,
            "schema_valid": False,
            "used_fallback": True,
            "missing_required_keys": list(schema.get("required_keys", {}).keys()),
            "cleaned_length": len(cleaned),
            "raw_length": len(raw_str),
            "status": VALID_STATUS_INVALID,
            "parse_error_type": "json_decode_error",
            "invalid_fields": [],
            "completeness_score": 0.0,
        }
        return (dict(fallback), False, meta) if return_meta else (dict(fallback), False)

    if not isinstance(parsed, dict):
        logger.error(f"[{context}] Parsed JSON is not a dict (got {type(parsed).__name__})")
        meta = {
            "parsed": False,
            "schema_valid": False,
            "used_fallback": True,
            "missing_required_keys": list(schema.get("required_keys", {}).keys()),
            "cleaned_length": len(cleaned),
            "raw_length": len(raw_str),
            "status": VALID_STATUS_INVALID,
            "parse_error_type": "non_object_json",
            "invalid_fields": [],
            "completeness_score": 0.0,
        }
        return (dict(fallback), False, meta) if return_meta else (dict(fallback), False)

    parsed = convert_legacy_to_new(parsed)
    status_result = validate_with_status(parsed, schema, partial_threshold=partial_threshold)
    coerced = status_result["data"]
    status = status_result["status"]
    is_valid = status in {VALID_STATUS_FULL, VALID_STATUS_PARTIAL}
    if status == VALID_STATUS_FULL:
        logger.info(f"[{context}] Schema validation FULL")
    elif status == VALID_STATUS_PARTIAL:
        logger.warning(f"[{context}] Schema validation PARTIAL")
    else:
        logger.warning(f"[{context}] Schema validation INVALID")
        coerced = dict(fallback)

    meta = {
        "parsed": True,
        "schema_valid": status == VALID_STATUS_FULL,
        "used_fallback": status == VALID_STATUS_INVALID,
        "missing_required_keys": status_result["missing_fields"],
        "cleaned_length": len(cleaned),
        "raw_length": len(raw_str),
        "status": status,
        "parse_error_type": None if is_valid else "schema_invalid",
        "invalid_fields": status_result["invalid_fields"],
        "completeness_score": status_result["completeness_score"],
    }

    return (coerced, is_valid, meta) if return_meta else (coerced, is_valid)
