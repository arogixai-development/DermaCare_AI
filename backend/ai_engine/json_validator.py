"""
JSON Validator for DermaCare AI
================================
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
        "diagnoses":  list,
        "reasoning":  str,
        "soap":       str,
        "triage":     str,
        "tests":      list,
        "referral":   list,
        "treatment":  list,
    },
    "defaults": {
        "diagnoses":  [],
        "reasoning":  "",
        "soap":       "",
        "triage":     "Routine",
        "tests":      [],
        "referral":   [],
        "treatment":  [],
    },
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
    "diagnoses": ["Unable to determine diagnosis at this time"],
    "reasoning": "AI response could not be parsed. Please retry.",
    "soap":      "S: AI parsing failed\nO: No data\nA: Error\nP: Retry",
    "triage":    "Routine",
    "tests":     ["Clinical evaluation recommended"],
    "referral":  ["Consult a specialist"],
    "treatment": ["Symptomatic management pending proper evaluation"],
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
    Attempt to extract a raw JSON object from a string that may contain
    surrounding prose or markdown code fences.

    Strategy (applied in order):
      1. Strip leading/trailing whitespace.
      2. Remove markdown code fences (```json ... ``` or ``` ... ```).
      3. Locate the outermost { … } block.
    """
    text = text.strip()

    # Remove markdown code fences
    if "```" in text:
        # Strip opening fence line and closing fence line
        text = re.sub(r"```(?:json)?\s*", "", text).strip()

    # Find outermost JSON object
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text  # Return as-is; json.loads will surface the error


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
    coerced  = dict(data)  # Shallow copy so we don't mutate the caller's dict

    for key, expected_type in required_keys.items():
        value = coerced.get(key)

        # ── Missing or None ────────────────────────────────────────────────
        if value is None:
            logger.warning(
                "Schema validation: missing key '%s' – using default %r",
                key, defaults[key],
            )
            coerced[key] = defaults[key]
            is_valid = False
            continue

        # ── Wrong type – attempt coercion ──────────────────────────────────
        if not isinstance(value, expected_type):
            try:
                if expected_type is list and isinstance(value, str):
                    # Wrap a bare string in a list
                    coerced[key] = [value]
                elif expected_type is str and isinstance(value, list):
                    # Join a list of strings into one string
                    coerced[key] = " ".join(str(v) for v in value)
                elif expected_type is str and isinstance(value, dict):
                    # Recursively format dictionary as a clean SOAP string
                    def format_dict(d, indent=0):
                        lines = []
                        for k, v in d.items():
                            header = str(k).upper()
                            # Handle common SOAP abbreviations
                            if header == 'S': header = 'SUBJECTIVE'
                            elif header == 'O': header = 'OBJECTIVE'
                            elif header == 'A': header = 'ASSESSMENT'
                            elif header == 'P': header = 'PLAN'
                            
                            if isinstance(v, dict):
                                lines.append(f"{'  ' * indent}{header}:\n{format_dict(v, indent + 1)}")
                            elif isinstance(v, list):
                                lines.append(f"{'  ' * indent}{header}: {' '.join(str(i) for i in v)}")
                            else:
                                lines.append(f"{'  ' * indent}{header}: {v}")
                        return "\n".join(lines)
                    
                    coerced[key] = format_dict(value)
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
                coerced[key] = defaults[key]
                is_valid = False

    return is_valid, coerced


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

    Pipeline
    --------
    1. Guard against empty / None input.
    2. ``extract_json_from_text`` – strip prose / markdown fences.
    3. ``json.loads()``           – decode JSON.
    4. ``validate_schema()``      – type-check and coerce missing fields.

    Parameters
    ----------
    raw_str  : Raw text returned by the LLM.
    schema   : Schema dict (``required_keys`` + ``defaults``).
    fallback : Returned as-is when parsing fails completely.
    context  : Label used in log messages (e.g. ``"diagnosis"``).

    Returns
    -------
    (result_dict, success)
        success is False only when ``json.loads`` raises an exception,
        meaning the LLM produced completely unparseable output.
    """
    if not raw_str or not raw_str.strip():
        logger.error("[%s] LLM returned an empty response", context)
        return dict(fallback), False

    # Step 1 – Extract JSON from potential surrounding text
    cleaned = extract_json_from_text(raw_str)

    # Step 2 – Parse with json.loads()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(
            "[%s] json.loads() failed: %s | Cleaned snippet: %.300s",
            context, exc, cleaned,
        )
        return dict(fallback), False

    if not isinstance(parsed, dict):
        logger.error(
            "[%s] Parsed JSON is not a dict (got %s)",
            context, type(parsed).__name__,
        )
        return dict(fallback), False

    # Step 3 – Schema validation + coercion
    is_valid, coerced = validate_schema(parsed, schema)

    if not is_valid:
        logger.warning(
            "[%s] Schema had issues; coercion applied – result is still usable",
            context,
        )

    return coerced, True
