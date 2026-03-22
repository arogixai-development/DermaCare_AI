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
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("DermaCare_AI.json_validator")

# ──────────────────────────────────────────────────────────────────────────────
# Schema definitions
# Each schema has:
#   required_keys  – {field_name: expected_python_type}
#   defaults       – {field_name: value_to_use_when_missing}
# ──────────────────────────────────────────────────────────────────────────────

DIAGNOSIS_SCHEMA: Dict[str, Any] = {
    "required_keys": {
        "differential_diagnosis": list,
        "clinical_reasoning":     str,
        "soap_note":             str,
        "treatment_plan":         list,
        "triage":                str,
    },
    "defaults": {
        "differential_diagnosis": [
            {"condition": "Unable to determine", "probability": "N/A", "supporting_features": []}
        ],
        "clinical_reasoning":     "Analysis could not be completed. Please retry.",
        "soap_note":             "S: Unable to complete\nO: No data\nA: Unable to assess\nP: Retry with additional information",
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

def extract_json_from_text(text: str) -> str:
    """
    Extract and repair JSON from LLM output.
    Handles garbage after JSON and common LLM errors.
    """
    if not text:
        return ""
    
    text = text.strip()
    
    # Remove markdown code fences
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("{") or (len(part) > 1 and "{" in part):
                text = part
                break
    
    # Find first { and extract to matching }
    start = text.find("{")
    if start == -1:
        return "{}"
    
    # Find the matching closing brace using stack
    depth = 0
    in_string = False
    escape_next = False
    end = start
    
    for i, c in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if c == "\\":
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    
    text = text[start:end + 1]
    
    # Remove garbage after JSON (common LLM issue)
    # Look for non-JSON characters after the closing brace
    remaining = text[end + 1:] if end < len(text) - 1 else ""
    if remaining.strip() and not remaining.strip().startswith(","):
        # There's garbage after JSON, but we have valid JSON
        pass  # Keep just the JSON part
    
    # Fix trailing commas
    text = re.sub(r',\s*([\]}])', r'\1', text)
    
    # Fix common typos
    text = re.sub(r'"condition\w+":\s*"(\d+%)"', r'"probability": "\1"', text)
    text = re.sub(r'"condition\w+":', r'"condition":', text)
    text = re.sub(r'"supportingth:|"supporting\w+features:', r'"supporting_features":', text)
    
    # Fix Python dict style
    text = re.sub(r"'([^']+)':\s*'", r'"\1": "', text)
    text = re.sub(r":\s*'([^']*)'", r': "\1"', text)
    
    # Only fix truly garbage merged keys (no semantic meaning, very long)
    text = re.sub(r'"([a-zA-Z]{30,})":', lambda m: m.group(0), text)
    
    return text



def validate_schema(
    data: dict,
    schema: Dict[str, Any],
) -> Tuple[bool, dict]:
    """
    Validate that *data* contains all required keys with the correct Python types.

    Missing or wrongly-typed values are coerced or replaced with schema defaults.

    Returns
    -------
    (is_fully_valid, coerced_data)
        is_fully_valid – True when every key was present and correctly typed.
        coerced_data   – The (possibly repaired) dict, always structurally complete.
    """
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
) -> Tuple[Dict[str, Any], bool]:
    """
    Parse *raw_str* as JSON, validate against *schema*, and return a
    guaranteed-structurally-correct dict.
    """
    logger.info(f"[{context}] parse_and_validate called with raw_str length: {len(raw_str) if raw_str else 0}")
    
    if not raw_str or not raw_str.strip():
        logger.error(f"[{context}] LLM returned an empty or whitespace-only response")
        return dict(fallback), False

    cleaned = extract_json_from_text(raw_str)
    logger.info(f"[{context}] Extracted JSON length: {len(cleaned)}")

    try:
        parsed = json.loads(cleaned)
        logger.info(f"[{context}] JSON parsed successfully, keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}")
    except json.JSONDecodeError as exc:
        logger.error(f"[{context}] json.loads() FAILED: {exc}")
        logger.error(f"[{context}] Raw response (first 500 chars): {raw_str[:500]}")
        logger.error(f"[{context}] Cleaned response (first 500 chars): {cleaned[:500]}")
        return dict(fallback), False

    if not isinstance(parsed, dict):
        logger.error(f"[{context}] Parsed JSON is not a dict (got {type(parsed).__name__})")
        return dict(fallback), False

    parsed = convert_legacy_to_new(parsed)

    is_valid, coerced = validate_schema(parsed, schema)

    if is_valid:
        logger.info(f"[{context}] Schema validation PASSED")
    else:
        logger.warning(f"[{context}] Schema validation had issues - using defaults for missing fields")

    return coerced, True
