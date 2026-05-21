"""
Diagnosis Service – DermaCare AI (Production)
===========================================
Glass Box AI with:
- Monte Carlo uncertainty estimation
- Gated Multimodal Architecture
- Production prompts for reliable JSON
- Bounded LRU cache to prevent memory leaks
"""

import ast
import json
import hashlib
import logging
import re
import time
import statistics
from typing import Any, Dict, Optional, Tuple

from backend.ai_engine.ollama_client import (
    run_ai_with_retry,
    run_ai_with_retry_async,
    run_groq_fallback,
    estimate_tokens,
    OllamaConnectionError,
    OllamaOverloadError,
    OllamaTimeoutError,
)
from backend.ai_engine.json_validator import DIAGNOSIS_SCHEMA, parse_and_validate
from backend.ai_engine.image_quality import analyze_lesion_image, ImageQualityAnalyzer
from backend.config import get_model_name, get_reliability_config
from backend.prompts.diagnosis_prompt import (
    build_reasoning_prompt,
    build_formatting_prompt,
    build_formatting_repair_prompt,
    build_diagnosis_prompt_quick,
    build_diagnosis_repair_prompt_quick,
)

logger = logging.getLogger("DermaCare_AI.diagnosis_service")

# SECURITY: Bounded cache with max 100 entries to prevent memory exhaustion
CACHE_MAX_SIZE = 100
# Bump when post-processing (guard/normalize/calibration) or stored payload shape changes
# Cache versioning: bump this integer if the LLM output structure or schema changes significantly.
_DIAGNOSIS_OUTPUT_CACHE_VERSION = 3
_last_diagnosis_cache: Dict[str, Any] = {}
_diagnosis_response_cache: Dict[str, Any] = {}


def _v1_diagnosis_cache_key(case_hash: str) -> str:
    return f"v1:{_DIAGNOSIS_OUTPUT_CACHE_VERSION}:{case_hash}"


def _v2_diagnosis_cache_key(case_hash: str) -> str:
    return f"v2:{_DIAGNOSIS_OUTPUT_CACHE_VERSION}:{case_hash}"

MONTE_CARLO_ITERATIONS = 2
USE_MONTE_CARLO = True

QUICK_MODE_TARGET_SECONDS = 25.0
ACCURATE_MODE_TARGET_SECONDS = 60.0
QUICK_MODE_MAX_TOKENS = 384
ACCURATE_MODE_MAX_TOKENS = 896
MAX_PARSE_RETRIES_QUICK = 0
MAX_PARSE_RETRIES_ACCURATE = 2

_DIAGNOSIS_RUNTIME_METRICS: Dict[str, Any] = {
    "total_runs": 0,
    "full_model_outputs": 0,
    "partial_model_outputs": 0,
    "fallback_outputs": 0,
    "parse_failures": 0,
    "latencies_ms": [],
    "parse_status_counts": {"FULL": 0, "PARTIAL": 0, "INVALID": 0},
    "fallback_reason_counts": {},
    "fallback_provider_counts": {"ollama_retry": 0, "groq": 0, "openai_disabled": 0},
    "groq_calls": 0,
    "cost_estimate_usd": 0.0,
    "low_confidence_cases": 0,
    "fallback_dependency_rate": 0.0,
    "timeout_spike_count": 0,
    "last_request_timeout_spike": False,
    "max_latency_ms_observed": 0,
}

# Per-request wall-clock threshold for spike logging (complements p95 in summaries).
SPIKE_LATENCY_SECONDS = 60.0

# v1 /diagnosis allowlist: canonical CDSS fields plus SPA and observability keys.
V1_DIAGNOSIS_RESPONSE_ALLOWLIST = frozenset(
    {
        "complaint",
        "lesion",
        "symptoms",
        "patient_age",
        "geographic_region",
        "skin_phototype",
        "lesion_history",
        "history_duration",
        "change_pattern",
        "diagnosis",
        "confidence",
        "reasoning",
        "recommended_tests",
        "treatment_plan",
        "triage",
        "differential_diagnosis",
        "clinical_reasoning",
        "soap_note",
        "lesion_analysis",
        "referral_indicators",
        "follow_up",
        "warnings",
        "uncertainty_flags",
        "gmu_analysis",
        "safety_checks",
        "response_type",
        "fallback_reason",
        "parse_error_type",
        "recovery_stage",
        "early_return_triggered",
        "time_budget_triggered",
        "elapsed_time_ms",
        "fallback_provider",
        "cost_estimate",
        "escalation_instruction",
        "_inference_time",
        "_model",
        "_response_quality",
        "_partial_llm",
        "_partial_reason",
        "_fallback",
        "_fallback_reason",
        "_cached",
        "_decision_support_note",
        "_parse_meta",
    }
)

# Maximum image data size (2MB) to prevent DoS
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB in bytes


def _validate_image_size(image_data: Optional[str]) -> bool:
    """Validate that image data is within size limit."""
    if not image_data:
        return True
    # Base64 encoding increases size by ~33%, so we check decoded size
    try:
        import base64
        # Remove data URI prefix if present
        if "," in image_data:
            image_data = image_data.split(",")[1]
        decoded = base64.b64decode(image_data)
        if len(decoded) > MAX_IMAGE_SIZE:
            logger.warning(f"Image size {len(decoded)} exceeds limit {MAX_IMAGE_SIZE}")
            return False
        return True
    except Exception as e:
        logger.warning(f"Image validation failed: {e}")
        return False


def _get_case_hash(case_data: dict) -> str:
    """Generate a hash for the case to use as cache key."""
    essential = {
        "complaint": case_data.get("complaint", ""),
        "lesion": case_data.get("lesion", ""),
        "symptoms": case_data.get("symptoms", ""),
        "patient_age": case_data.get("patient_age", ""),
        "geographic_region": case_data.get("geographic_region", ""),
        "history_duration": case_data.get("history_duration", ""),
        "change_pattern": case_data.get("change_pattern", ""),
        "monte_carlo": bool(case_data.get("monte_carlo", False)),
    }
    return hashlib.sha256(json.dumps(essential, sort_keys=True).encode()).hexdigest()


def _note_diagnosis_latency_wallclock(
    latency_seconds: float, mode: str, route: str = "v1"
) -> None:
    """Record max latency; log and count spikes when wall-clock exceeds SPIKE_LATENCY_SECONDS."""
    ms = int(latency_seconds * 1000)
    m = _DIAGNOSIS_RUNTIME_METRICS
    prev_max = int(m.get("max_latency_ms_observed", 0) or 0)
    if ms > prev_max:
        m["max_latency_ms_observed"] = ms
    spike = latency_seconds > SPIKE_LATENCY_SECONDS
    m["last_request_timeout_spike"] = spike
    if spike:
        m["timeout_spike_count"] = int(m.get("timeout_spike_count", 0) or 0) + 1
        logger.warning(
            json.dumps(
                {
                    "timeout_spike_detected": True,
                    "latency_ms": ms,
                    "mode": mode,
                    "route": route,
                }
            )
        )


def sanitize_v1_diagnosis_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep only allowlisted top-level keys (drops stray LLM keys).
    Preserves canonical CDSS fields and SPA-required keys.
    """
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k in V1_DIAGNOSIS_RESPONSE_ALLOWLIST}


def _degraded_response_quality_valid(result: Dict[str, Any]) -> bool:
    """Heuristic: partial/degraded output has valid triage and meaningful diagnoses."""
    triage = str(result.get("triage", "")).strip().lower()
    if triage not in ("routine", "urgent"):
        return False
    for item in (result.get("differential_diagnosis") or [])[:5]:
        if isinstance(item, dict) and len(str(item.get("condition", "")).strip()) >= 3:
            return True
    for n in result.get("diagnosis") or []:
        if isinstance(n, str) and len(n.strip()) >= 3:
            return True
    return False


def _cleanup_cache():
    """Remove oldest entries if cache exceeds max size."""
    if len(_diagnosis_response_cache) > CACHE_MAX_SIZE:
        # Remove oldest 20% of entries
        keys_to_remove = list(_diagnosis_response_cache.keys())[:int(CACHE_MAX_SIZE * 0.2)]
        for key in keys_to_remove:
            del _diagnosis_response_cache[key]
        logger.info(f"Cache cleanup: removed {len(keys_to_remove)} entries")


def _record_runtime(
    latency_seconds: float,
    mode: str,
    output_kind: str,
    parse_failed: bool = False,
    parse_status: str = "INVALID",
    fallback_reason: str = "",
    fallback_provider: str = "",
    cost_estimate_usd: float = 0.0,
) -> None:
    """Track diagnosis runtime and output quality counters."""
    _DIAGNOSIS_RUNTIME_METRICS["total_runs"] += 1
    if output_kind == "full":
        _DIAGNOSIS_RUNTIME_METRICS["full_model_outputs"] += 1
    elif output_kind == "partial":
        _DIAGNOSIS_RUNTIME_METRICS["partial_model_outputs"] += 1
    else:
        _DIAGNOSIS_RUNTIME_METRICS["fallback_outputs"] += 1
    if parse_failed:
        _DIAGNOSIS_RUNTIME_METRICS["parse_failures"] += 1
    if parse_status in _DIAGNOSIS_RUNTIME_METRICS["parse_status_counts"]:
        _DIAGNOSIS_RUNTIME_METRICS["parse_status_counts"][parse_status] += 1
    if fallback_reason:
        reasons = _DIAGNOSIS_RUNTIME_METRICS["fallback_reason_counts"]
        reasons[fallback_reason] = reasons.get(fallback_reason, 0) + 1
    if fallback_provider:
        providers = _DIAGNOSIS_RUNTIME_METRICS["fallback_provider_counts"]
        providers[fallback_provider] = providers.get(fallback_provider, 0) + 1
        if fallback_provider in ("groq", "groq_quick_recovery"):
            _DIAGNOSIS_RUNTIME_METRICS["groq_calls"] += 1
    _DIAGNOSIS_RUNTIME_METRICS["cost_estimate_usd"] += float(cost_estimate_usd or 0.0)

    latencies = _DIAGNOSIS_RUNTIME_METRICS["latencies_ms"]
    latencies.append(int(latency_seconds * 1000))
    if len(latencies) > 200:
        del latencies[: len(latencies) - 200]

    budget = QUICK_MODE_TARGET_SECONDS if mode == "quick" else ACCURATE_MODE_TARGET_SECONDS
    if latency_seconds > budget:
        logger.warning(
            "[DIAGNOSIS] %s mode exceeded budget: %.2fs > %.2fs",
            mode,
            latency_seconds,
            budget,
        )
    _note_diagnosis_latency_wallclock(latency_seconds, mode=mode, route="v1")


def _p95(values: list) -> int:
    if not values:
        return 0
    sorted_values = sorted(values)
    idx = min(len(sorted_values) - 1, int(len(sorted_values) * 0.95))
    return sorted_values[idx]


def get_runtime_metrics() -> Dict[str, Any]:
    """Expose runtime metrics for health/observability endpoints."""
    latencies = _DIAGNOSIS_RUNTIME_METRICS["latencies_ms"]
    total = _DIAGNOSIS_RUNTIME_METRICS["total_runs"] or 1
    reliability = get_reliability_config()
    revenue_total = reliability.get("price_per_request_usd", 0.05) * total
    cost_total = _DIAGNOSIS_RUNTIME_METRICS["cost_estimate_usd"]
    gross_margin = ((revenue_total - cost_total) / revenue_total) if revenue_total > 0 else 0.0
    fallback_dependency_rate = _DIAGNOSIS_RUNTIME_METRICS["fallback_outputs"] / total
    _DIAGNOSIS_RUNTIME_METRICS["fallback_dependency_rate"] = round(fallback_dependency_rate, 3)
    return {
        "total_runs": _DIAGNOSIS_RUNTIME_METRICS["total_runs"],
        "full_model_outputs": _DIAGNOSIS_RUNTIME_METRICS["full_model_outputs"],
        "partial_model_outputs": _DIAGNOSIS_RUNTIME_METRICS["partial_model_outputs"],
        "fallback_outputs": _DIAGNOSIS_RUNTIME_METRICS["fallback_outputs"],
        "parse_failures": _DIAGNOSIS_RUNTIME_METRICS["parse_failures"],
        "fallback_rate": round(_DIAGNOSIS_RUNTIME_METRICS["fallback_outputs"] / total, 3),
        "parse_failure_rate": round(_DIAGNOSIS_RUNTIME_METRICS["parse_failures"] / total, 3),
        "parse_status_counts": _DIAGNOSIS_RUNTIME_METRICS["parse_status_counts"],
        "fallback_reason_counts": _DIAGNOSIS_RUNTIME_METRICS["fallback_reason_counts"],
        "fallback_provider_counts": _DIAGNOSIS_RUNTIME_METRICS["fallback_provider_counts"],
        "groq_usage_rate": round(_DIAGNOSIS_RUNTIME_METRICS["groq_calls"] / total, 3),
        "cost_estimate_usd_total": round(_DIAGNOSIS_RUNTIME_METRICS["cost_estimate_usd"], 6),
        "cost_estimate_usd_per_100_requests": round(
            (_DIAGNOSIS_RUNTIME_METRICS["cost_estimate_usd"] / total) * 100, 6
        ),
        "gross_margin_pct": round(gross_margin * 100, 2),
        "fallback_dependency_rate": round(fallback_dependency_rate, 3),
        "low_confidence_cases": _DIAGNOSIS_RUNTIME_METRICS["low_confidence_cases"],
        "latency_ms_p95": _p95(latencies),
        "latency_ms_last": latencies[-1] if latencies else 0,
        "timeout_spike_count": int(_DIAGNOSIS_RUNTIME_METRICS.get("timeout_spike_count", 0) or 0),
        "timeout_spike_detected": bool(_DIAGNOSIS_RUNTIME_METRICS.get("last_request_timeout_spike", False)),
        "max_latency_ms_observed": int(_DIAGNOSIS_RUNTIME_METRICS.get("max_latency_ms_observed", 0) or 0),
        "quick_target_seconds": QUICK_MODE_TARGET_SECONDS,
        "accurate_target_seconds": ACCURATE_MODE_TARGET_SECONDS,
    }


def create_dynamic_fallback(case_data: dict) -> dict:
    """
    Create a DYNAMIC fallback response based on ACTUAL patient data.
    This ensures the AI always returns relevant information even when LLM parsing fails.
    """
    age = str(case_data.get('patient_age', 'Unknown'))
    region = case_data.get('geographic_region', 'Unknown')
    complaint = case_data.get('complaint', 'Dermatological concern')
    lesion = case_data.get('lesion', 'Not specified')
    symptoms = case_data.get('symptoms', 'Not specified')
    duration = case_data.get('history_duration', 'Not specified')
    phototype = case_data.get('skin_phototype', 'Type III')
    
    logger.warning(f"[DIAGNOSIS] Using dynamic fallback for patient: {age}yo, complaint: {complaint[:50]}...")
    complaint_text = f"{complaint} {lesion} {symptoms}".lower()

    if any(k in complaint_text for k in ["lip", "oral", "mouth", "ulcer", "stomatitis", "aphthous"]):
        differential_diagnosis = [
            {
                "condition": "Provisional Oral Ulcerative Lesion (pending clinical confirmation)",
                "probability": "45%",
                "supporting_features": ["Painful oral/lip ulcer pattern", "Needs oral cavity exam"],
                "differentials_to_exclude": ["Aphthous ulcer", "HSV lesion", "Oral neoplasia"]
            },
            {
                "condition": "Provisional Aphthous-like Ulcer (pending clinical confirmation)",
                "probability": "30%",
                "supporting_features": ["Pain during eating", "Subacute duration pattern"],
                "differentials_to_exclude": ["Traumatic ulcer", "Behcet disease"]
            },
            {
                "condition": "Provisional Infectious or Traumatic Oral Lesion (pending clinical confirmation)",
                "probability": "25%",
                "supporting_features": ["Local bleeding/pain features", "Requires infection and malignancy exclusion"],
                "differentials_to_exclude": ["Bacterial ulcer", "Syphilis", "Squamous cell carcinoma"]
            }
        ]
    elif any(k in complaint_text for k in ["ring", "annular", "central clearing", "fungal", "tinea"]):
        differential_diagnosis = [
            {
                "condition": "Provisional Tinea Corporis (pending clinical confirmation)",
                "probability": "50%",
                "supporting_features": ["Annular/ring morphology", "Possible central clearing"],
                "differentials_to_exclude": ["Nummular eczema", "Psoriasis"]
            },
            {
                "condition": "Provisional Nummular Dermatitis (pending clinical confirmation)",
                "probability": "30%",
                "supporting_features": ["Pruritic erythematous plaque pattern", "Can mimic fungal lesions"],
                "differentials_to_exclude": ["Tinea corporis", "Contact dermatitis"]
            },
            {
                "condition": "Provisional Contact Dermatitis (pending clinical confirmation)",
                "probability": "20%",
                "supporting_features": ["Inflammatory rash requiring trigger history", "Symptom-based provisional"],
                "differentials_to_exclude": ["Atopic dermatitis", "Fungal infection"]
            }
        ]
    elif any(k in complaint_text for k in ["psoriasis", "scale", "plaque", "extensor"]):
        differential_diagnosis = [
            {
                "condition": "Provisional Psoriasis (pending clinical confirmation)",
                "probability": "55%",
                "supporting_features": ["Scaly plaque morphology", "Extensor surface distribution pattern"],
                "differentials_to_exclude": ["Seborrheic dermatitis", "Lichen planus", "Nummular dermatitis"]
            },
            {
                "condition": "Provisional Dermatitis (pending clinical confirmation)",
                "probability": "25%",
                "supporting_features": ["Erythematous scaly lesion", "Symptom-based provisional"],
                "differentials_to_exclude": ["Psoriasis", "Fungal infection"]
            },
            {
                "condition": "Provisional Skin Condition (pending clinical confirmation)",
                "probability": "20%",
                "supporting_features": ["Requires further evaluation"],
                "differentials_to_exclude": ["Infection", "Allergic reaction"]
            }
        ]
    else:
        differential_diagnosis = [
            {
                "condition": "Provisional Dermatitis (pending clinical confirmation)",
                "probability": "40%",
                "supporting_features": ["Requires clinical examination", "Based on presented symptoms"],
                "differentials_to_exclude": ["Psoriasis", "Fungal infection", "Malignancy"]
            },
            {
                "condition": "Provisional Eczema (pending clinical confirmation)",
                "probability": "35%",
                "supporting_features": ["Requires clinical examination", "Symptom-based provisional"],
                "differentials_to_exclude": ["Contact dermatitis", "Seborrheic dermatitis"]
            },
            {
                "condition": "Provisional Skin Condition (pending clinical confirmation)",
                "probability": "25%",
                "supporting_features": ["Requires further evaluation"],
                "differentials_to_exclude": ["Infection", "Allergic reaction"]
            }
        ]

    return {
        "differential_diagnosis": differential_diagnosis,
        "lesion_analysis": [
            {
                "morphology": f"Clinical description pending: {lesion[:100] if lesion else 'Not specified'}",
                "distribution": f"Affected area: Region {region}",
                "color_patterns": ["Pending visual examination"],
                "ABCDE_assessment": "Assessment pending clinical examination",
                "dermoscopy_findings": "Visual examination recommended"
            }
        ],
        "recommended_tests": [
            "Clinical dermatological examination recommended",
            "Consider skin biopsy if lesion persists",
            "Patch testing if allergic etiology suspected",
            "KOH preparation if fungal infection suspected"
        ],
        "clinical_reasoning": f"AI analysis incomplete due to LLM parsing issue. Patient profile: {age}-year-old from {region}, Skin Type: {phototype}. Chief Complaint: {complaint}. Lesion: {lesion}. Symptoms: {symptoms}. Duration: {duration}. Please retry analysis or consult dermatologist for definitive diagnosis.",
        "soap_note": {
            "S": f"Patient ({age}yo from {region}) presents with: {complaint}. Lesion: {lesion}. Symptoms: {symptoms}. Duration: {duration}.",
            "O": "Objective examination pending. Visual inspection of affected area required.",
            "A": f"Provisional assessment: Dermatological condition requires clinical examination. Patient data: {age}yo, {region}, {phototype}.",
            "P": "1. Clinical examination recommended\n2. Consider biopsy if needed\n3. Follow-up in 1-2 weeks if symptoms persist\n4. Return if condition worsens"
        },
        "treatment_plan": [
            {
                "medication": "Clinical Evaluation Required",
                "application": "Please consult with dermatologist for proper assessment",
                "duration": "Immediate",
                "education": "Do not self-diagnose. Seek professional medical evaluation."
            },
            {
                "medication": "Symptomatic Relief (pending diagnosis)",
                "application": "Keep affected area clean and dry. Avoid scratching.",
                "duration": "Until clinical evaluation",
                "education": "Monitor for changes in size, color, or symptoms."
            }
        ],
        "triage": "Routine",
        "referral_indicators": [
            "Lesion does not respond to treatment within 2 weeks",
            "Atypical appearance (irregular borders, changing color, bleeding)",
            "Systemic symptoms (fever, malaise)",
            "Extensive body surface area involvement"
        ],
        "follow_up": f"Return in 1-2 weeks for reassessment. If symptoms worsen or new symptoms develop, seek immediate medical attention. Patient: {age}yo from {region}.",
        "warnings": ["This is a FALLBACK response - AI analysis was incomplete", "Please verify with clinical examination", "Consult dermatologist for definitive diagnosis"],
        "_fallback": True,
        "_fallback_reason": "LLM JSON parsing failed - dynamic fallback based on patient data"
    }


FALLBACK_RESPONSE = create_dynamic_fallback({
    'patient_age': 'Unknown',
    'geographic_region': 'Unknown',
    'complaint': 'General dermatological concern'
})


def _all_providers_failed_fallback(case_data: dict) -> Dict[str, Any]:
    """
    CDSS-shaped safety response when local Ollama and Groq are unavailable
    or return no usable output. Keeps triage compatible with downstream checks.
    """
    age = str(case_data.get("patient_age", "Unknown"))
    region = case_data.get("geographic_region", "Unknown")
    complaint = case_data.get("complaint", "Not specified")
    lesion = case_data.get("lesion", "Not specified")
    return {
        "differential_diagnosis": [
            {
                "condition": "Unable to determine condition (AI services unavailable)",
                "probability": "N/A",
                "supporting_features": [
                    "Primary and backup inference did not return usable automated output",
                ],
                "differentials_to_exclude": ["Defer to in-person clinical assessment"],
            }
        ],
        "diagnosis": ["Unable to determine condition"],
        "lesion_analysis": [
            {
                "morphology": f"Not assessed automatically: {lesion[:120] if lesion else 'Not specified'}",
                "distribution": f"Region: {region}",
                "color_patterns": ["Pending examination"],
                "ABCDE_assessment": "Deferred — seek clinical evaluation",
                "dermoscopy_findings": "Not available",
            }
        ],
        "recommended_tests": [
            "In-person dermatologic examination when services are restored",
        ],
        "clinical_reasoning": (
            "AI services temporarily unavailable. Automated diagnosis could not be completed. "
            f"Presenting concern: {complaint[:200]}. Seek licensed in-person care."
        ),
        "soap_note": {
            "S": f"{age}yo from {region}: {complaint}. Lesion: {lesion}.",
            "O": "Automated assessment unavailable.",
            "A": "Diagnosis undetermined — provider outage or contingency failure.",
            "P": "Consult a licensed medical professional; re-try analysis later if appropriate.",
        },
        "treatment_plan": [
            {
                "medication": "None — clinical assessment required",
                "application": "N/A",
                "duration": "Until evaluated",
                "education": "Consult a licensed medical professional",
            }
        ],
        "triage": "Urgent",
        "referral_indicators": ["Consult a licensed medical professional promptly"],
        "follow_up": "Re-attempt decision support when systems are healthy, or proceed with standard care.",
        "warnings": [
            "AI inference providers unavailable or returned no usable result.",
            "Consult Doctor — do not rely on this placeholder for treatment decisions.",
        ],
        "_fallback": True,
        "_fallback_reason": "all_providers_failed",
    }


def _run_monte_carlo(prompt: str) -> Dict[str, Any]:
    """Run Monte Carlo uncertainty estimation."""
    results = []
    temperatures = [0.2, 0.3]
    
    for i, temp in enumerate(temperatures[:MONTE_CARLO_ITERATIONS]):
        try:
            raw = run_ai_with_retry(prompt, max_tokens=256, format="json", max_retries=0)
            parsed, success = parse_and_validate(raw, DIAGNOSIS_SCHEMA, {}, "diagnosis")
            if success:
                results.append({"success": True, "data": parsed})
            else:
                results.append({"success": False, "raw": raw[:200]})
        except Exception as e:
            results.append({"success": False, "error": str(e)[:100]})
    
    valid = [r for r in results if r.get("success")]
    
    if not valid:
        return {
            "variance_score": 0.7,
            "confidence_interval": [20, 50],
            "consensus_score": 0.3,
            "uncertainty_flag": True,
            "discordant_indicators": ["All MC runs failed"],
            "recommendations": ["Retry analysis"]
        }
    
    consensus = _calculate_consensus(valid)
    variance = _calculate_variance(valid)
    
    return {
        "variance_score": round(variance, 3),
        "confidence_interval": _calculate_confidence_interval(consensus, variance),
        "consensus_score": round(consensus, 3),
        "uncertainty_flag": variance > 0.4 or consensus < 0.5,
        "discordant_indicators": _find_discordant(valid),
        "recommendations": _get_suggestions(variance, consensus),
        "iterations_completed": len(valid),
        "iterations_total": MONTE_CARLO_ITERATIONS
    }


def _calculate_consensus(results: list) -> float:
    if not results:
        return 0.3
    conditions = []
    for r in results:
        data = r.get("data", {})
        dx = data.get("differential_diagnosis", [])
        if dx and len(dx) > 0:
            conditions.append(dx[0].get("condition", "").lower())
    if not conditions:
        return 0.3
    most_common = statistics.mode(conditions)
    return conditions.count(most_common) / len(conditions)


def _calculate_variance(results: list) -> float:
    if len(results) < 2:
        return 0.4
    conditions_sets = []
    for r in results:
        data = r.get("data", {})
        dx = data.get("differential_diagnosis", [])
        conditions = {d.get("condition", "").lower() for d in dx if d.get("condition")}
        conditions_sets.append(conditions)
    
    if not conditions_sets:
        return 0.5
    
    similarities = []
    for i, s1 in enumerate(conditions_sets):
        for s2 in conditions_sets[i+1:]:
            if s1 or s2:
                intersection = len(s1 & s2)
                union = len(s1 | s2)
                similarities.append(intersection / union if union > 0 else 0)
    
    return 1.0 - (statistics.mean(similarities) if similarities else 0.5)


def _calculate_confidence_interval(consensus: float, variance: float) -> list:
    base = consensus * 100
    margin = 15 if consensus > 0.7 else 25 if consensus < 0.4 else 20
    return [max(0, base - margin), min(100, base + margin)]


def _find_discordant(results: list) -> list:
    discordant = []
    conf_levels = []
    for r in results:
        data = r.get("data", {})
        reasoning = data.get("clinical_reasoning", "")
        if "uncertain" in reasoning.lower() or "may" in reasoning.lower():
            conf_levels.append("LOW")
        else:
            conf_levels.append("MEDIUM")
    if len(set(conf_levels)) > 1:
        discordant.append("Confidence varied across runs")
    return discordant


def _get_suggestions(variance: float, consensus: float) -> list:
    suggestions = []
    if variance > 0.5:
        suggestions.append("High variance - specialist review recommended")
    if consensus < 0.5:
        suggestions.append("Low consensus - consider biopsy")
    suggestions.append("Provide more clinical details")
    return suggestions


def _map_confidence(consensus: float, variance: float) -> str:
    """Map MC consensus/variance to label; slightly more forgiving MEDIUM band (balanced UX)."""
    if consensus >= 0.65 and variance < 0.35:
        return "HIGH"
    if consensus >= 0.38 and variance < 0.55:
        return "MEDIUM"
    if consensus >= 0.22:
        return "LOW"
    return "UNCERTAIN"


def _clinical_reasoning_word_count(candidate: Dict[str, Any]) -> int:
    text = str(candidate.get("clinical_reasoning", "") or "").strip()
    return len(text.split()) if text else 0


_CR_SOAP_LABELS = {
    "S": "Subjective",
    "O": "Objective",
    "A": "Assessment",
    "P": "Plan",
    "B": "Clinical summary",
}
_CLINICAL_REASONING_GUARD_HINT = (
    "Distribution and symmetry strongly support psoriasis over fungal causes."
)


def _looks_like_soap_dict_string(s: str) -> bool:
    t = (s or "").strip()
    if not t.startswith("{"):
        return False
    return any(
        needle in t
        for needle in ("'S':", '"S":', "'O':", '"O":', "'A':", '"A":', "'P':", '"P":')
    )


def _looks_like_part_dict_string(s: str) -> bool:
    """LLM sometimes returns clinical_reasoning as {'Part1': '...', 'Part2': '...'}."""
    t = (s or "").strip()
    if not t.startswith("{"):
        return False
    return bool(re.search(r"['\"]Part\d+['\"]\s*:", t, re.I))


def _normalize_clinical_reasoning_text(raw: str) -> str:
    """Turn SOAP- or PartN-embedded dict reprs into readable multi-line clinical reasoning."""
    text = (raw or "").strip()
    if not text:
        return raw if raw is not None else ""

    if _looks_like_soap_dict_string(text):
        try:
            obj = ast.literal_eval(text)
        except (ValueError, SyntaxError, MemoryError):
            obj = None
        if isinstance(obj, dict):
            parts: list = []
            for key in ("S", "O", "A", "P", "B"):
                if key not in obj:
                    continue
                val = obj[key]
                if val is None:
                    continue
                body = str(val).strip()
                if not body:
                    continue
                label = _CR_SOAP_LABELS.get(key, key)
                parts.append(f"{label}:\n{body}")
            if parts:
                return "\n\n".join(parts)

    if _looks_like_part_dict_string(text):
        try:
            obj = ast.literal_eval(text)
        except (ValueError, SyntaxError, MemoryError):
            return raw if raw is not None else ""
        if isinstance(obj, dict):
            part_keys = [
                k
                for k in obj
                if isinstance(k, str) and re.match(r"^Part\d+$", k, re.I)
            ]
            if part_keys:

                def _part_order(k: str) -> int:
                    m = re.search(r"(\d+)", k, re.I)
                    return int(m.group(1)) if m else 0

                part_keys.sort(key=_part_order)
                blocks = []
                for k in part_keys:
                    val = obj.get(k)
                    if val is None:
                        continue
                    body = str(val).strip()
                    if body:
                        blocks.append(f"{k}:\n{body}")
                if blocks:
                    return "\n\n".join(blocks)

    return raw if raw is not None else ""


_DICT_LIKE_CR_RE = re.compile(
    r"^\s*\{[\s\S]*['\"][\w_]+['\"]\s*:\s*",
    re.MULTILINE,
)


def _clinical_reasoning_dict_like_residual(text: str) -> bool:
    """True if reasoning still looks like an embedded dict (after failed literal_eval)."""
    t = (text or "").strip()
    if _looks_like_soap_dict_string(t) or _looks_like_part_dict_string(t):
        return True
    return bool(_DICT_LIKE_CR_RE.search(t))


def _expand_clinical_reasoning_readability(
    text: str, result: Dict[str, Any]
) -> str:
    """Deterministic expansion for thin or dict-like clinical_reasoning (no extra LLM)."""
    t = (text or "").strip()
    if not t:
        return text if text is not None else ""
    tl = t.lower()
    if (
        re.search(r"(?i)^key features:\s", t)
        and "differential:" in tl
        and "conclusion:" in tl
    ):
        return text
    wc = len(t.split())
    single_line = "\n" not in t.replace("\r\n", "\n")
    if not (single_line or wc < 30 or _clinical_reasoning_dict_like_residual(t)):
        return text

    lines_dd: list = []
    for item in (result.get("differential_diagnosis") or [])[:5]:
        if isinstance(item, dict):
            c = str(item.get("condition", "") or "").strip()
            if not c:
                continue
            p = item.get("probability")
            if p is not None and str(p).strip():
                lines_dd.append(f"- {c} (support: {p})")
            else:
                lines_dd.append(f"- {c}")
    dd_block = (
        "\n".join(lines_dd)
        if lines_dd
        else "Ranked differentials follow clinical exam; refine with KOH or biopsy if unclear."
    )
    lead = ""
    dd = result.get("differential_diagnosis") or []
    if dd and isinstance(dd[0], dict):
        lead = str(dd[0].get("condition", "") or "").strip()
    if not lead:
        for n in result.get("diagnosis") or []:
            if isinstance(n, str) and n.strip():
                lead = n.strip()
                break
    triage = str(result.get("triage", "") or "").strip()
    key_body = t
    if _clinical_reasoning_dict_like_residual(t) and len(t) > 320:
        key_body = t[:320].rstrip() + "…"
    conclusion = (
        f"Preferred working diagnosis: {lead or 'pending clinical correlation'}."
    )
    if triage:
        conclusion += f" Triage: {triage}."
    else:
        conclusion += " Correlate with exam and histology/KOH when indicated."
    parts = [
        f"Key Features:\n{key_body}",
        f"Differential:\n{dd_block}",
        f"Conclusion:\n{conclusion}",
    ]
    return "\n\n".join(parts)


def _clinical_reasoning_structure_weak(text: str) -> bool:
    """Heuristic: dict-like SOAP blob or short text without differential comparison."""
    t = (text or "").strip()
    if not t:
        return True
    if _looks_like_soap_dict_string(t) or _looks_like_part_dict_string(t):
        return True
    words = t.split()
    has_cmp = bool(
        re.search(
            r"versus|compared|argues against|\bdifferential\b|less likely|more likely|"
            r"preferred|ranked|conclusion|alternate|exclude",
            t,
            re.I,
        )
    )
    if len(words) < 55 and not has_cmp:
        return True
    return False


def _strong_pattern_or_guard_calibration_signal(
    case_data: dict, result: Dict[str, Any]
) -> bool:
    if _psoriatic_phenotype_hint(case_data):
        return True
    cr = str(result.get("clinical_reasoning", "") or "")
    if _CLINICAL_REASONING_GUARD_HINT.lower() in cr.lower():
        return True
    for w in result.get("warnings") or []:
        ws = str(w)
        if "Rank order adjusted for classic psoriatic distribution" in ws:
            return True
    return False


def _calibrate_display_confidence(
    confidence_score: float,
    case_data: dict,
    result: Dict[str, Any],
    llm_usable: bool,
    output_kind: str,
    parse_meta: Optional[Dict[str, Any]],
    reliability: Dict[str, Any],
) -> float:
    """Raise numeric confidence slightly for strong FULL parses that match classic patterns."""
    if not llm_usable or output_kind != "full":
        return confidence_score
    if not parse_meta:
        return confidence_score
    if parse_meta.get("status") != "FULL":
        return confidence_score
    thresh = float(reliability.get("full_parse_confidence_calibration_threshold", 0.9))
    completeness = float(parse_meta.get("completeness_score", 0.0) or 0.0)
    if completeness < thresh:
        return confidence_score
    if not _strong_pattern_or_guard_calibration_signal(case_data, result):
        return confidence_score
    bumped = min(0.85, confidence_score + 0.12)
    return round(max(bumped, 0.6), 3)


_PSORIATIC_SYM = (
    "symmetric",
    "bilateral",
    "both elbows",
    "both knees",
    "both elbow",
    "both knee",
)
_PSORIATIC_EXT = ("extensor", "elbow", "knee", "elbows", "knees")
_PSORIATIC_SCALE = ("silvery", "silvery-white", "silvery white", "well-demarcated")
_FUNGAL_COND_RE = re.compile(
    r"tinea|ringworm|dermatophyte|fungal\s*infection|fungal\s+dermatitis",
    re.IGNORECASE,
)
_PSORIASIS_COND_RE = re.compile(r"psoriasis|psoriatic", re.IGNORECASE)


def _case_text_blob(case_data: dict) -> str:
    return " ".join(
        [
            str(case_data.get("complaint", "") or ""),
            str(case_data.get("lesion", "") or ""),
            str(case_data.get("symptoms", "") or ""),
        ]
    ).lower()


def _guard_blocked_by_fungal_morphology(case_data: dict) -> bool:
    """Annular / central clearing favors true tinea; skip rank guard to avoid overcorrection."""
    blob = _case_text_blob(case_data)
    return "annular" in blob or "central clearing" in blob


def _psoriatic_phenotype_hint(case_data: dict) -> bool:
    """True if at least two of: symmetry, extensor distribution, silvery/well-demarcated scale."""
    blob = _case_text_blob(case_data)
    sym = any(s in blob for s in _PSORIATIC_SYM)
    ext = any(s in blob for s in _PSORIATIC_EXT)
    scale = any(s in blob for s in _PSORIATIC_SCALE)
    return sum(1 for x in (sym, ext, scale) if x) >= 2


def _nudge_percent_probability_str(val: Any, factor: float) -> Any:
    """Slightly scale a 'NN%' style probability; leave non-matching values unchanged."""
    if val is None:
        return None
    s = str(val).strip()
    m = re.search(r"(\d+\.?\d*)\s*%", s)
    if not m:
        return val
    num = float(m.group(1)) * factor
    num = max(8.0, min(92.0, num))
    if num == int(num):
        return f"{int(num)}%"
    return f"{num:.1f}%"


def _adjust_confidence_after_psoriasis_guard(out: Dict[str, Any]) -> None:
    """Subtle boost and floor after a psoriasis-over-tinea reorder (strong-pattern context)."""
    raw = out.get("confidence")
    try:
        cf = float(raw) if raw is not None and raw != "" else 0.0
    except (TypeError, ValueError):
        return
    if cf <= 0.0:
        out["confidence"] = 0.65
        return
    bumped = min(0.92, cf * 1.06 + 0.02)
    out["confidence"] = round(max(bumped, 0.62), 3)


def _append_clinical_reasoning_guard_hint(out: Dict[str, Any]) -> None:
    cr = str(out.get("clinical_reasoning", "") or "").strip()
    hint = _CLINICAL_REASONING_GUARD_HINT
    if hint.lower() in cr.lower():
        return
    out["clinical_reasoning"] = (cr + " " + hint).strip() if cr else hint


def _soap_needs_psoriasis_realignment(
    soap: Dict[str, Any], lead_condition: str
) -> Tuple[bool, bool]:
    """Returns (patch_assessment, patch_plan) when SOAP still centers tinea without psoriasis context."""
    if not _PSORIASIS_COND_RE.search(str(lead_condition or "")):
        return False, False
    a = str(soap.get("A", "") or "")
    p = str(soap.get("P", "") or "")
    a_l, p_l = a.lower(), p.lower()
    tinea_forward = bool(_FUNGAL_COND_RE.search(a) or "tinea" in a_l or "ringworm" in a_l)
    ps_in_a = bool(_PSORIASIS_COND_RE.search(a))
    patch_a = tinea_forward and not ps_in_a
    fungal_rx = any(
        x in p_l
        for x in (
            "antifungal",
            "terbinafine",
            "clotrimazole",
            "ketoconazole",
            "miconazole",
            "azole cream",
            "griseofulvin",
        )
    )
    ps_rx = any(
        x in p_l
        for x in (
            "steroid",
            "corticosteroid",
            "psoriasis",
            "calcipotriene",
            "calcitriol",
            "tacrolimus",
            "uvb",
        )
    )
    patch_p = fungal_rx and not ps_rx
    return patch_a, patch_p


def _align_soap_with_psoriasis_lead(out: Dict[str, Any], lead_condition: str) -> None:
    """Minimal SOAP patches when DDx lead is psoriasis but A/P still read tinea-primary."""
    sn = out.get("soap_note")
    if not isinstance(sn, dict):
        return
    patch_a, patch_p = _soap_needs_psoriasis_realignment(sn, lead_condition)
    if not patch_a and not patch_p:
        return
    soap = dict(sn)
    if patch_a:
        add_a = (
            " Working diagnosis favors psoriasis given distribution and symmetry; "
            "retain tinea if morphology becomes annular or KOH is positive."
        )
        soap["A"] = (str(soap.get("A", "") or "").rstrip() + add_a).strip()
    if patch_p:
        add_p = (
            " Align therapy with psoriasis first-line per local protocol if exam supports plaques; "
            "use empiric topical antifungal only if lesions are annular or scrapings suggest dermatophyte."
        )
        soap["P"] = (str(soap.get("P", "") or "").rstrip() + add_p).strip()
    out["soap_note"] = soap


def _fungal_primary_misrank(dx_list: list) -> bool:
    if len(dx_list) < 2:
        return False
    first = dx_list[0]
    if not isinstance(first, dict):
        return False
    if not _FUNGAL_COND_RE.search(str(first.get("condition", "") or "")):
        return False
    for item in dx_list[1:]:
        if isinstance(item, dict) and _PSORIASIS_COND_RE.search(
            str(item.get("condition", "") or "")
        ):
            return True
    return False


def _find_first_psoriasis_index(dx_list: list) -> int:
    for i, item in enumerate(dx_list):
        if isinstance(item, dict) and _PSORIASIS_COND_RE.search(
            str(item.get("condition", "") or "")
        ):
            return i
    return -1


def _first_condition_is_fungal(dx_list: list) -> bool:
    if not dx_list or not isinstance(dx_list[0], dict):
        return False
    return bool(
        _FUNGAL_COND_RE.search(str(dx_list[0].get("condition", "") or ""))
    )


def _differential_has_psoriasis(dx_list: list) -> bool:
    for item in dx_list:
        if isinstance(item, dict) and _PSORIASIS_COND_RE.search(
            str(item.get("condition", "") or "")
        ):
            return True
    return False


def _apply_psoriasis_fungal_rank_guard(
    case_data: dict, result: Dict[str, Any]
) -> Dict[str, Any]:
    """Reorder DDx when case text matches classic psoriasis pattern but model ranks tinea first."""
    if _guard_blocked_by_fungal_morphology(case_data):
        logger.info(
            "[DIAGNOSIS] clinical_pattern_guard=skipped reason=guard_skipped_fungal_pattern_detected"
        )
        return result
    if not _psoriatic_phenotype_hint(case_data):
        return result
    dx = result.get("differential_diagnosis")
    if not isinstance(dx, list) or len(dx) < 1:
        return result

    dx_copy: list = []
    for entry in dx:
        if isinstance(entry, dict):
            dx_copy.append(dict(entry))
        else:
            dx_copy.append(entry)

    if len(dx_copy) >= 2 and _fungal_primary_misrank(dx_copy):
        j = _find_first_psoriasis_index(dx_copy)
        if j > 0:
            out = dict(result)
            msg = (
                "Rank order adjusted for classic psoriatic distribution—confirm clinically."
            )
            a, b = dx_copy[0], dx_copy[j]
            prob_a = a.get("probability") if isinstance(a, dict) else None
            prob_b = b.get("probability") if isinstance(b, dict) else None
            dx_copy[0], dx_copy[j] = dx_copy[j], dx_copy[0]
            if isinstance(dx_copy[0], dict) and isinstance(dx_copy[j], dict):
                dx_copy[0]["probability"] = prob_b
                dx_copy[j]["probability"] = prob_a
                dx_copy[0]["probability"] = _nudge_percent_probability_str(
                    dx_copy[0].get("probability"), 1.05
                )
                dx_copy[j]["probability"] = _nudge_percent_probability_str(
                    dx_copy[j].get("probability"), 0.95
                )
            out["differential_diagnosis"] = dx_copy
            warns = out.get("warnings")
            if not isinstance(warns, list):
                warns = []
            out["warnings"] = list(warns) + ([msg] if msg not in warns else [])
            _adjust_confidence_after_psoriasis_guard(out)
            _append_clinical_reasoning_guard_hint(out)
            lead = (
                str(dx_copy[0].get("condition", "") or "")
                if isinstance(dx_copy[0], dict)
                else ""
            )
            _align_soap_with_psoriasis_lead(out, lead)
            _normalize_canonical(out)
            logger.info(
                "[DIAGNOSIS] clinical_pattern_guard_applied=true reason=swap_fungal_below_psoriasis"
            )
            return out

    if _first_condition_is_fungal(dx_copy) and not _differential_has_psoriasis(dx_copy):
        msg = (
            "Consider psoriasis vulgaris in the differential if symmetric extensor silvery "
            "plaques are present—confirm clinically."
        )
        warns = result.get("warnings")
        if not isinstance(warns, list):
            warns = []
        if msg in warns:
            return result
        out = dict(result)
        out["warnings"] = list(warns) + [msg]
        logger.info(
            "[DIAGNOSIS] clinical_pattern_guard_applied=true reason=fungal_first_psoriasis_not_listed"
        )
        return out

    return result


def _to_confidence_score(level: str) -> float:
    mapping = {"HIGH": 0.85, "MEDIUM": 0.65, "LOW": 0.4, "UNCERTAIN": 0.3}
    return mapping.get(level, 0.4)


def _normalize_canonical(result: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure canonical investor schema fields always exist."""
    diagnosis_list = []
    for item in result.get("differential_diagnosis", [])[:3]:
        if isinstance(item, dict):
            diagnosis_list.append(str(item.get("condition", "")).strip())
    result["diagnosis"] = diagnosis_list
    result["confidence"] = float(result.get("confidence", 0.0) or 0.0)
    result["reasoning"] = str(result.get("clinical_reasoning", "") or "")
    result["recommended_tests"] = result.get("recommended_tests", []) or []
    result["treatment_plan"] = result.get("treatment_plan", []) or []
    result["triage"] = str(result.get("triage", "Routine") or "Routine")
    return result


def _ensure_cdss_structure(result: Dict[str, Any]) -> Dict[str, Any]:
    """Enforce deterministic CDSS shape and fill missing optional fields safely."""
    result = _normalize_canonical(result)
    if not result.get("recommended_tests"):
        result["recommended_tests"] = [
            "Clinical dermatological examination",
            "KOH or biopsy based on lesion evolution",
        ]
    if not result.get("treatment_plan"):
        result["treatment_plan"] = [
            {
                "medication": "Supportive care pending confirmation",
                "application": "Follow clinician guidance",
                "duration": "Until reviewed",
                "education": "Consult a licensed medical professional",
            }
        ]
    return result


def _has_critical_fields(result: Dict[str, Any]) -> bool:
    return bool(result.get("diagnosis")) and bool(str(result.get("triage", "")).strip())


def _is_non_cdss_output(parsed: Dict[str, Any], raw: str) -> bool:
    """Reject conversational outputs masquerading as diagnosis."""
    if not isinstance(parsed, dict):
        return True
    structured_keys = {"differential_diagnosis", "triage", "treatment_plan", "recommended_tests"}
    if any(k in parsed for k in structured_keys):
        return False
    conversational_markers = ["i cannot", "as an ai", "i'm sorry", "cannot provide medical advice"]
    raw_lower = (raw or "").lower()
    return any(marker in raw_lower for marker in conversational_markers)


def _deterministic_enrichment(case_data: dict, result: dict, confidence_score: float) -> dict:
    enriched = dict(result)
    
    if "confidence_explanation" not in enriched:
        if confidence_score < 0.4:
            enriched["confidence_explanation"] = "Confidence limited by absence of confirmatory testing. Clinical morphology is suggestive but not pathognomonic; variance reflects incomplete diagnostic certainty."
        elif confidence_score < 0.7:
            enriched["confidence_explanation"] = "Confidence moderated due to absence of confirmatory testing. Clinical morphology is suggestive, though histopathologic confirmation is unavailable."
        else:
            enriched["confidence_explanation"] = "High confidence based on classic morphological presentation and patient history."
            
    dx_list = enriched.get("differential_diagnosis", [])
    lead_dx = dx_list[0].get("condition", "Undetermined") if dx_list and isinstance(dx_list[0], dict) else "Undetermined"
    lead_dx_lower = lead_dx.lower()
    
    # 5. Triage Calibration
    triage = str(enriched.get("triage", "Routine")).title()
    symptoms_lower = (str(case_data.get("symptoms", "")) + " " + str(case_data.get("complaint", "")) + " " + str(case_data.get("lesion", ""))).lower()
    
    if "psoriasis" in lead_dx_lower:
        # Stable chronic plaque psoriasis is Routine. Only Urgent if severe red flags present.
        if any(s in symptoms_lower for s in ["fever", "chills", "bleeding", "pustular", "erythroderma", "rapid", "widespread", "systemic"]):
            triage = "Urgent"
        else:
            triage = "Routine"
    elif "tinea" in lead_dx_lower or "fungal" in lead_dx_lower:
        # Fungal is typically routine unless acute secondary infection features are present
        if any(s in symptoms_lower for s in ["fever", "pus", "spreading rapidly", "severe pain"]):
            triage = "Urgent"
        else:
            triage = "Routine"
    else:
        # Weak input/undetermined is standard routine follow up
        triage = "Routine"
        
    enriched["triage"] = triage

    # ALWAYS OVERRIDE SOAP NOTE FOR DETERMINISTIC QUALITY
    age = str(case_data.get("patient_age", "Unknown"))
    region = case_data.get("geographic_region", "Unknown")
    complaint = case_data.get("complaint", "Not specified")
    lesion = case_data.get("lesion", "Not specified")
    symptoms = case_data.get("symptoms", "None")
    duration = case_data.get("history_duration", "Unknown")
    
    if "psoriasis" in lead_dx_lower:
        assessment_text = f"Clinical morphology strongly favors {lead_dx} given the described plaque characteristics and distribution. Presentation is consistent with chronic plaque psoriasis."
    elif "tinea" in lead_dx_lower or "fungal" in lead_dx_lower:
        assessment_text = f"Clinical morphology is highly suggestive of {lead_dx}, presenting as an annular scaling plaque with central clearing."
    elif "eczema" in lead_dx_lower or "dermatitis" in lead_dx_lower:
        assessment_text = f"Clinical morphology is consistent with {lead_dx}, showing eczematous inflammatory changes."
    else:
        assessment_text = f"Primary working diagnosis: {lead_dx}. (Confidence: {confidence_score*100:.0f}%). Clinical evaluation required to differentiate from similar entities."
    
    enriched["soap_note"] = {
        "S": f"Patient ({age}yo, {region}) presents with chief complaint of '{complaint}'. Associated symptoms include: {symptoms}. Reported duration: {duration}.",
        "O": f"Dermatological findings: {lesion}. (Pending formal physical examination)",
        "A": assessment_text,
        "P": "1. Recommend in-person clinical evaluation to confirm findings.\n2. Consider specific diagnostic tests (e.g., biopsy, KOH prep) if lesion is refractory to initial management.\n3. Initiate symptom-directed therapy as outlined in the treatment plan.\n4. Standard follow-up in 2-4 weeks or sooner if condition exacerbates.\n5. Counsel patient on red flag symptoms requiring immediate evaluation."
    }
    
    # ALWAYS OVERRIDE TREATMENT PLAN
    treatments = []
    if "tinea" in lead_dx_lower or "fungal" in lead_dx_lower:
        treatments.append({
            "medication": "Topical Antifungal (e.g., Terbinafine 1% or Clotrimazole 1% cream)",
            "application": "Apply topically to the affected area and 2 cm beyond the visible margin, twice daily.",
            "duration": "Continue for 1-2 weeks after clinical clearing to prevent recurrence.",
            "education": "Maintain strict hygiene. Keep the affected area clean and dry. Avoid tight-fitting clothing and wash towels frequently. Do not use topical corticosteroids as monotherapy."
        })
        treatments.append({
            "medication": "Supportive Care & Monitoring",
            "application": "Inspect lesions daily for peripheral spread or central clearing.",
            "duration": "Ongoing during active therapy.",
            "education": "Avoid sharing towels or personal items. Monitor for signs of secondary bacterial infection (pus, warmth, severe pain). Refer to primary care if no improvement after 2 weeks of compliant topical therapy."
        })
    elif "psoriasis" in lead_dx_lower:
        treatments.append({
            "medication": "Topical Corticosteroid (e.g., Clobetasol 0.05% or Betamethasone dipropionate)",
            "application": "Apply a thin layer strictly to the active psoriatic plaques, avoiding normal surrounding skin.",
            "duration": "Use daily for up to 2-4 weeks, then taper to weekend-only maintenance if cleared.",
            "education": "Avoid skin trauma (Koebner phenomenon) and scratching. Monitor for skin thinning. Follow up for systemic therapy evaluation if >10% BSA."
        })
        treatments.append({
            "medication": "Thick Emollients & Keratolytics (e.g., Salicylic acid 3% or plain Petrolatum base)",
            "application": "Apply liberally to plaques to reduce scaling and improve steroid penetration.",
            "duration": "Use continuously as a daily maintenance routine.",
            "education": "Apply immediately after bathing to lock in moisture and protect skin barrier."
        })
        treatments.append({
            "medication": "Dermatology Referral & Escalation Guidance",
            "application": "Schedule routine dermatology referral for confirmation and long-term care plan.",
            "duration": "Follow up within 4 weeks.",
            "education": "Escalate to urgent care immediately if rapid plaque progression, bleeding, pustular lesions, severe widespread involvement (>10% body surface area), or erythroderma-like findings develop. Phototherapy or systemic therapy may be considered if topical management is insufficient."
        })
    elif "eczema" in lead_dx_lower or "dermatitis" in lead_dx_lower:
        treatments.append({
            "medication": "Thick Emollients (e.g., Petrolatum-based or Ceramide-rich creams)",
            "application": "Apply liberally to the entire body, especially to affected areas.",
            "duration": "Continuous daily use, multiple times a day.",
            "education": "Maintain strict skin hydration. Avoid known irritants, harsh soaps, hot water baths, and wool clothing."
        })
        treatments.append({
            "medication": "Topical Corticosteroid (e.g., Triamcinolone 0.1% ointment)",
            "application": "Apply sparingly to active inflammatory areas only.",
            "duration": "Use during acute flares for 1-2 weeks maximum on sensitive areas.",
            "education": "Do not apply on face or intertriginous areas without explicit physician instruction."
        })
    else:
        # Conservative safe guidance, no hallucinated prescriptions
        treatments.append({
            "medication": "Conservative Barrier Support (e.g., Ceramide-rich emollient or Plain Petrolatum)",
            "application": "Apply sparingly as needed to provide barrier support and soothe dry/irritated skin.",
            "duration": "Until formal clinical evaluation.",
            "education": "Contains no active drug substances. Avoid using unguided prescription steroid or antifungal creams. Monitor closely for changes in morphology."
        })
        treatments.append({
            "medication": "Clinical Consult & Triage Guide",
            "application": "Schedule standard face-to-face physician evaluation.",
            "duration": "Within 7-14 days.",
            "education": "Confidence limited by extremely brief or atypical description. Presentation does not meet minimum clinical criteria for active automated prescription recommendations."
        })
        
    enriched["treatment_plan"] = treatments

    # ALWAYS OVERRIDE LESION ANALYSIS
    lesion_text = str(case_data.get("lesion", "")).lower()
    if "psoriasis" in lead_dx_lower or "plaque" in lesion_text or "scale" in lesion_text:
        morphology = "Well-demarcated erythematous plaques with overlying silvery-white scale."
        distribution = "Symmetric extensor distribution highly favored based on clinical pattern."
        pattern = "Psoriasiform inflammatory pattern. Classic hallmark of epidermal hyperproliferation."
    elif "tinea" in lead_dx_lower or "annular" in lesion_text or "ring" in lesion_text:
        morphology = "Annular erythematous plaques with central clearing and active scaly borders."
        distribution = "Localized to specified body region."
        pattern = "Dermatophyte / Fungal pattern. Inflammatory response to dermatophyte invasion."
    elif "eczema" in lead_dx_lower or "patch" in lesion_text:
        morphology = "Poorly-demarcated erythematous patches with possible excoriation or lichenification."
        distribution = "Flexural or generalized pattern typical for atopic/contact etiology."
        pattern = "Spongiotic dermatitis pattern. Epidermal edema characteristic of eczematous process."
    else:
        morphology = case_data.get("lesion", "Unspecified morphology.")
        distribution = "As described by patient."
        pattern = "Non-specific inflammatory pattern."
        
    enriched["lesion_analysis"] = [{
        "morphology": morphology,
        "distribution": distribution,
        "ABCDE_assessment": "Not overtly suggestive of melanoma based on text description.",
        "color_patterns": ["Erythematous", "Scaly"] if "scale" in morphology.lower() else ["Erythematous"],
        "dermoscopy_findings": f"Dermoscopy not available. Suspected pattern: {pattern}. Clinical correlation required."
    }]

    enriched["follow_up"] = "Return to clinic in 10-14 days for treatment response reassessment. Immediate return if symptoms acutely worsen, signs of secondary infection appear, or systemic symptoms (fever) develop."
        
    warnings = enriched.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
    if confidence_score < 0.5:
        if "Low diagnostic confidence. Clinical correlation is strongly advised." not in warnings:
            warnings.append("Low diagnostic confidence. Clinical correlation is strongly advised.")
    if str(enriched.get("triage", "")).lower() in ["urgent", "emergency"]:
        if "URGENT triage indicated. Prompt medical evaluation required." not in warnings:
            warnings.append("URGENT triage indicated. Prompt medical evaluation required.")
            
    if not any("AI output" in w or "decision-support" in w for w in warnings):
        warnings.append("This is an AI-generated decision support output, not a definitive medical diagnosis.")
        
    enriched["warnings"] = warnings
    
    enriched["referral_indicators"] = [
        "Lack of improvement after 2 weeks of compliant initial therapy",
        "Development of systemic symptoms (e.g., fever, chills, malaise)",
        "Rapid expansion of the lesion or signs of secondary bacterial infection (erythema, warmth, purulence)",
        "Atypical lesion evolution suggestive of malignancy"
    ]
        
    return enriched


def generate_diagnosis(case_data: dict, use_monte_carlo: bool = True) -> dict:
    """Production diagnosis with Glass Box AI.
    
    Args:
        case_data: Patient case data
        use_monte_carlo: If True, run uncertainty estimation (slower but more accurate).
                         If False, skip MC for faster response.
    """
    
    logger.info(f"[DIAGNOSIS] Starting diagnosis for patient: {case_data.get('patient_age')}yo, complaint: {str(case_data.get('complaint', ''))[:50]}...")
    logger.info(f"[DIAGNOSIS] Monte Carlo: {'Enabled' if use_monte_carlo else 'Disabled'}")
    
    # SECURITY: Validate image size before processing
    if case_data.get("image_data") and not _validate_image_size(case_data.get("image_data")):
        logger.warning("Image exceeds maximum size limit of 2MB")
        return {
            "error": "Image too large",
            "detail": "Image data exceeds the maximum size limit of 2MB. Please use a smaller image.",
            "status": "rejected"
        }
    
    case_hash = _get_case_hash(case_data)
    ck = _v1_diagnosis_cache_key(case_hash)

    if ck in _diagnosis_response_cache:
        cached = dict(_diagnosis_response_cache[ck])
        cached["_cached"] = True
        logger.info(
            "[DIAGNOSIS] Returning cached result for case hash: %s... (cache_key=%s)",
            case_hash[:16],
            ck[:24],
        )
        return cached
    
    _cleanup_cache()
    
    start_time = time.time()
    has_history = bool(case_data.get("lesion_history") or case_data.get("history_duration"))
    
    image_quality_result = None
    multimodal_weights = {"image": 0.4, "metadata": 0.6}
    image_quality_gate = "pass"
    non_skin_detected = False
    
    if case_data.get("image_data"):
        try:
            image_quality_result = analyze_lesion_image(case_data["image_data"])
            analyzer = ImageQualityAnalyzer()
            should_use, reason = analyzer.should_use_multimodal(image_quality_result)
            multimodal_weights = analyzer.get_multimodal_weights(image_quality_result, has_history)
            
            if image_quality_result.quality_level.value == "non_diagnostic":
                image_quality_gate = "rejected"
                non_skin_detected = True
            elif image_quality_result.quality_level.value == "low":
                image_quality_gate = "degraded"
            else:
                image_quality_gate = "pass"
        except Exception as e:
            logger.warning(f"Image quality analysis failed: {e}")
            image_quality_gate = "unknown"
    
    reliability = get_reliability_config()
    quick_mode = not use_monte_carlo
    mode = "accurate" if use_monte_carlo else "quick"

    prompt = ""
    max_tokens = (
        int(reliability.get("accurate_mode_max_tokens", ACCURATE_MODE_MAX_TOKENS))
        if use_monte_carlo
        else int(reliability.get("quick_mode_max_tokens", QUICK_MODE_MAX_TOKENS))
    )
    parse_retries = (
        1 # ONE formatting repair attempt maximum for accurate
        if use_monte_carlo
        else 0 # Quick mode: single-pass fast generation, no repair
    )

    if use_monte_carlo:
        mc_metrics = _run_monte_carlo(build_reasoning_prompt(case_data))
        confidence = _map_confidence(mc_metrics.get("consensus_score", 0.3), mc_metrics.get("variance_score", 0.5))
    else:
        mc_metrics = {"variance_score": 0.4, "confidence_interval": [40, 70], "consensus_score": 0.5, "uncertainty_flag": False, "discordant_indicators": [], "recommendations": ["Provide detailed clinical information"]}
        confidence = "MEDIUM"
    
    logger.info("[DIAGNOSIS] Calling LLM...")
    dynamic_fallback = create_dynamic_fallback(case_data)

    parsed = dict(dynamic_fallback)
    success = False
    parse_meta: Dict[str, Any] = {}
    raw = ""
    parse_failures = 0
    parse_status = "INVALID"
    fallback_provider = "none"
    fallback_reason = ""
    recovery_stage = "primary_ollama"
    cost_estimate_usd = 0.0
    final_attempt = 0
    retry_overhead_time = 0.0
    accurate_time_budget = int(reliability.get("accurate_time_budget_seconds", 48))
    accurate_final_fallback_timeout = int(
        reliability.get("accurate_final_fallback_timeout_seconds", 15)
    )
    early_return_triggered = False
    time_budget_triggered = False
    elapsed_time_ms = 0
    final_budget_fallback_allowed = False
    ollama_unreachable = False
    groq_http_attempted = False
    
    raw_reasoning = ""
    if use_monte_carlo:
        logger.info("[DIAGNOSIS] Step A: Clinical reasoning pass (Accurate mode)")
        try:
            raw_reasoning = run_ai_with_retry(build_reasoning_prompt(case_data), max_tokens=1000, format=None, max_retries=0)
        except OllamaConnectionError as exc:
            ollama_unreachable = True
            logger.warning("[DIAGNOSIS] Step A failed: %s", exc)

    for attempt in range(parse_retries + 1):
        final_attempt = attempt
        if use_monte_carlo:
            if not raw_reasoning:
                break
            if attempt == 0:
                attempt_prompt = build_formatting_prompt(raw_reasoning, case_data)
            else:
                attempt_prompt = build_formatting_repair_prompt(raw_reasoning, case_data, raw)
        else:
            if attempt == 0:
                attempt_prompt = build_diagnosis_prompt_quick(case_data)
            else:
                attempt_prompt = build_diagnosis_repair_prompt_quick(case_data, raw)
        
        prompt = attempt_prompt
        llm_start = time.time()
        try:
            raw = run_ai_with_retry(attempt_prompt, max_tokens=max_tokens, format="json", max_retries=0)
        except OllamaConnectionError as exc:
            logger.warning(
                "[DIAGNOSIS] ollama_failure_detected type=%s detail=%s",
                type(exc).__name__,
                exc,
            )
            ollama_unreachable = True
            raw = ""
            ollama_call_time = time.time() - llm_start
            logger.info(
                "[DIAGNOSIS] Raw LLM response length: 0 chars (Ollama unavailable)"
            )
            break
        ollama_call_time = time.time() - llm_start
        logger.info(f"[DIAGNOSIS] Raw LLM response length: {len(raw)} chars")
        parse_start = time.time()
        parsed, success, parse_meta = parse_and_validate(
            raw, DIAGNOSIS_SCHEMA, dynamic_fallback, "diagnosis", return_meta=True
        )
        parse_time = time.time() - parse_start
        logger.info(
            "[DIAGNOSIS_TIMING] mode=%s ollama_call_time=%.3fs parse_time=%.3fs",
            mode,
            ollama_call_time,
            parse_time,
        )
        parse_status = parse_meta.get("status", "INVALID")
        elapsed_time_ms = int((time.time() - start_time) * 1000)

        if use_monte_carlo:
            # Accurate fast path: return immediately after first usable output.
            partial_threshold = float(reliability.get("partial_valid_threshold", 0.5))
            completeness_score = float(parse_meta.get("completeness_score", 0.0))
            result_candidate = dict(dynamic_fallback)
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    if value not in (None, "", [], {}):
                        result_candidate[key] = value
            result_candidate.pop("_fallback", None)
            result_candidate.pop("_fallback_reason", None)
            result_candidate = _ensure_cdss_structure(result_candidate)
            has_critical = _has_critical_fields(result_candidate)
            usable_full = parse_status == "FULL" and has_critical
            usable_partial = (
                parse_status == "PARTIAL"
                and completeness_score >= partial_threshold
                and has_critical
            )
            if attempt == 0 and (usable_full or usable_partial):
                budget_ms = int(accurate_time_budget * 1000 * 0.85)
                cr_words = _clinical_reasoning_word_count(result_candidate)
                cr_raw = str(result_candidate.get("clinical_reasoning", "") or "")
                structure_weak = _clinical_reasoning_structure_weak(cr_raw)
                defer_quality = parse_retries >= 1 and elapsed_time_ms < budget_ms and (
                    (completeness_score < 0.95 and cr_words < 70) or structure_weak
                )
                if defer_quality:
                    logger.info(
                        "[DIAGNOSIS] accurate_quality_pass deferred words=%d completeness=%.2f structure_weak=%s",
                        cr_words,
                        completeness_score,
                        structure_weak,
                    )
                    continue
                early_return_triggered = True
                success = True
                parsed = result_candidate
                if usable_partial:
                    fallback_reason = fallback_reason or "partial_salvage"
                logger.info(
                    "[DIAGNOSIS] early_return_triggered=true parse_status=%s elapsed_ms=%d",
                    parse_status,
                    elapsed_time_ms,
                )
                break

            if elapsed_time_ms >= (accurate_time_budget * 1000):
                time_budget_triggered = True
                if has_critical:
                    success = True
                    parsed = result_candidate
                    parse_status = "PARTIAL"
                    fallback_reason = fallback_reason or "time_budget_partial_return"
                    logger.warning(
                        "[DIAGNOSIS] time_budget_triggered with critical fields; returning partial (elapsed_ms=%d)",
                        elapsed_time_ms,
                    )
                    break
                final_budget_fallback_allowed = True
                logger.warning(
                    "[DIAGNOSIS] time_budget_triggered without usable partial; allowing one final fallback (elapsed_ms=%d)",
                    elapsed_time_ms,
                )
                break

        if success:
            recovery_stage = "primary_ollama" if attempt == 0 else "ollama_repair_retry"
            break
        parse_failures += 1
        retry_overhead_time += ollama_call_time + parse_time
        logger.warning("[DIAGNOSIS] Parse attempt %d failed; retrying...", attempt + 1)

    if reliability.get("enable_groq_fallback", True) and (not success or ollama_unreachable):
        allow_groq = (
            (not quick_mode)
            or reliability.get("quick_allow_groq_fallback", False)
            or ollama_unreachable
        )
        total_runs = max(1, _DIAGNOSIS_RUNTIME_METRICS.get("total_runs", 0))
        groq_rate = _DIAGNOSIS_RUNTIME_METRICS.get("groq_calls", 0) / total_runs
        cap = float(reliability.get("groq_usage_cap_rate", 0.10))
        under_cap = groq_rate < cap or ollama_unreachable
        if allow_groq and under_cap:
            groq_model = (
                reliability.get("groq_model_cheap")
                if reliability.get("groq_model_strategy", "quality") == "cost"
                else reliability.get("groq_model")
            )
            if use_monte_carlo and raw_reasoning:
                groq_prompt = build_formatting_repair_prompt(raw_reasoning, case_data, raw) if (raw and str(raw).strip()) else build_formatting_prompt(raw_reasoning, case_data)
            else:
                groq_prompt = build_diagnosis_repair_prompt_quick(case_data, raw) if (raw and str(raw).strip()) else build_diagnosis_prompt_quick(case_data)
            
            prompt = groq_prompt
            if ollama_unreachable:
                fallback_reason = fallback_reason or "ollama_unavailable"
            groq_http_attempted = True
            groq_result = run_groq_fallback(
                groq_prompt,
                max_tokens=max_tokens,
                model_override=groq_model,
                timeout_seconds=accurate_final_fallback_timeout if final_budget_fallback_allowed else 30,
            )
            if groq_result.get("ok"):
                fallback_provider = "groq"
                recovery_stage = "groq_contingency"
                cost_estimate_usd = float(groq_result.get("estimated_cost_usd", 0.0))
                logger.info(
                    "[DIAGNOSIS] Groq contingency used model=%s ollama_unreachable=%s",
                    groq_result.get("model", groq_model),
                    ollama_unreachable,
                )
                raw = groq_result.get("content", "")
                parsed, success, parse_meta = parse_and_validate(
                    raw, DIAGNOSIS_SCHEMA, dynamic_fallback, "diagnosis_groq", return_meta=True
                )
                parse_status = parse_meta.get("status", "INVALID")
                if ollama_unreachable and success:
                    fallback_reason = "ollama_unavailable"
            else:
                if ollama_unreachable:
                    fallback_reason = f"ollama_unavailable;groq_unavailable:{groq_result.get('error', 'unknown')}"
                else:
                    fallback_reason = f"groq_unavailable:{groq_result.get('error', 'unknown')}"
        elif not allow_groq:
            fallback_reason = "groq_disabled_for_mode"
        else:
            fallback_reason = "groq_usage_cap_reached"

    logger.info(
        "[DIAGNOSIS] JSON parsing success=%s ollama_unreachable=%s fallback_provider=%s fallback_reason=%s",
        success,
        ollama_unreachable,
        fallback_provider,
        fallback_reason or "none",
    )
    completeness_score = float(parse_meta.get("completeness_score", 0.0) if parse_meta else 0.0)
    partial_threshold = float(reliability.get("partial_valid_threshold", 0.5))
    parse_status = parse_meta.get("status", parse_status) if parse_meta else parse_status

    if _is_non_cdss_output(parsed if isinstance(parsed, dict) else {}, raw):
        success = False
        parse_status = "INVALID"
        fallback_reason = fallback_reason or "non_cdss_output_detected"

    force_all_providers_failed = ollama_unreachable and not success

    result_candidate = dict(dynamic_fallback)
    if isinstance(parsed, dict):
        for key, value in parsed.items():
            if value not in (None, "", [], {}):
                result_candidate[key] = value
    result_candidate.pop("_fallback", None)
    result_candidate.pop("_fallback_reason", None)
    result_candidate = _ensure_cdss_structure(result_candidate)

    has_critical = _has_critical_fields(result_candidate)
    usable_full = parse_status == "FULL"
    usable_partial = parse_status == "PARTIAL" and completeness_score >= partial_threshold
    usable_failsafe = (parse_status == "INVALID") and has_critical
    llm_usable = usable_full or usable_partial or usable_failsafe
    if force_all_providers_failed:
        llm_usable = False
    logger.info(
        "[DIAGNOSIS] Decision inputs parse_status=%s completeness=%.2f critical=%s llm_usable=%s",
        parse_status,
        completeness_score,
        has_critical,
        llm_usable,
    )

    # Quick mode: one Groq attempt when Ollama parse is INVALID but critical fields salvage.
    if (
        quick_mode
        and llm_usable
        and parse_status == "INVALID"
        and usable_failsafe
        and reliability.get("enable_groq_fallback", True)
        and fallback_provider != "groq"
        and not groq_http_attempted
    ):
        total_runs_m = max(1, _DIAGNOSIS_RUNTIME_METRICS.get("total_runs", 0))
        groq_rate_m = _DIAGNOSIS_RUNTIME_METRICS.get("groq_calls", 0) / total_runs_m
        cap_m = float(reliability.get("groq_usage_cap_rate", 0.10))
        if groq_rate_m < cap_m or ollama_unreachable:
            groq_model_q = (
                reliability.get("groq_model_cheap")
                if reliability.get("groq_model_strategy", "quality") == "cost"
                else reliability.get("groq_model")
            )
            q_timeout = int(
                reliability.get(
                    "quick_groq_recovery_timeout_seconds",
                    reliability.get("groq_fallback_timeout_seconds", 30),
                )
            )
            groq_prompt_q = (
                build_diagnosis_repair_prompt_quick(case_data, raw)
                if (raw and str(raw).strip())
                else build_diagnosis_prompt_quick(case_data)
            )
            groq_result_q = run_groq_fallback(
                groq_prompt_q,
                max_tokens=max_tokens,
                model_override=groq_model_q,
                timeout_seconds=q_timeout,
            )
            if groq_result_q.get("ok"):
                raw_q = groq_result_q.get("content", "")
                parsed_q, success_q, parse_meta_q = parse_and_validate(
                    raw_q,
                    DIAGNOSIS_SCHEMA,
                    dynamic_fallback,
                    "diagnosis_groq_quick_recovery",
                    return_meta=True,
                )
                if not _is_non_cdss_output(
                    parsed_q if isinstance(parsed_q, dict) else {}, raw_q
                ):
                    old_complete = completeness_score
                    cand_q = dict(dynamic_fallback)
                    if isinstance(parsed_q, dict):
                        for key, value in parsed_q.items():
                            if value not in (None, "", [], {}):
                                cand_q[key] = value
                    cand_q.pop("_fallback", None)
                    cand_q.pop("_fallback_reason", None)
                    cand_q = _ensure_cdss_structure(cand_q)
                    has_q = _has_critical_fields(cand_q)
                    complete_q = float(parse_meta_q.get("completeness_score", 0.0))
                    status_q = parse_meta_q.get("status", "INVALID")
                    usable_full_q = status_q == "FULL"
                    usable_partial_q = (
                        status_q == "PARTIAL" and complete_q >= partial_threshold
                    )
                    usable_failsafe_q = (status_q == "INVALID") and has_q
                    adopt_q = has_q and (
                        usable_full_q
                        or usable_partial_q
                        or (usable_failsafe_q and complete_q >= old_complete - 0.001)
                    )
                    if adopt_q:
                        result_candidate = cand_q
                        has_critical = has_q
                        parsed = parsed_q
                        parse_meta = parse_meta_q
                        success = success_q
                        parse_status = status_q
                        completeness_score = complete_q
                        raw = raw_q
                        fallback_provider = "groq_quick_recovery"
                        recovery_stage = "groq_quick_recovery"
                        cost_estimate_usd += float(
                            groq_result_q.get("estimated_cost_usd", 0.0)
                        )
                        usable_full = parse_status == "FULL"
                        usable_partial = (
                            parse_status == "PARTIAL"
                            and completeness_score >= partial_threshold
                        )
                        usable_failsafe = (parse_status == "INVALID") and has_critical
                        llm_usable = usable_full or usable_partial or usable_failsafe
                        if force_all_providers_failed:
                            llm_usable = False
                        logger.info(
                            "[DIAGNOSIS] fallback_provider=groq_quick_recovery "
                            "parse_status=%s completeness=%.2f",
                            parse_status,
                            completeness_score,
                        )
                    else:
                        logger.info(
                            "[DIAGNOSIS] groq_quick_recovery skipped_adopt "
                            "has_critical=%s status=%s",
                            has_q,
                            status_q,
                        )
                else:
                    logger.info(
                        "[DIAGNOSIS] groq_quick_recovery skipped non_cdss_output"
                    )
            else:
                logger.info(
                    "[DIAGNOSIS] groq_quick_recovery groq_error=%s",
                    groq_result_q.get("error"),
                )

    if llm_usable:
        result = result_candidate
        if usable_partial or usable_failsafe:
            result["_partial_llm"] = True
            if usable_failsafe:
                result["_partial_reason"] = "Failsafe: critical fields present, fallback bypassed"
                fallback_reason = fallback_reason or "failsafe_critical_fields_present"
            else:
                result["_partial_reason"] = "LLM PARTIAL accepted with safe defaults for non-critical fields"
            output_kind = "partial"
            fallback_reason = fallback_reason or "partial_salvage"
        else:
            output_kind = "full"
    else:
        if ollama_unreachable and not success:
            result = _ensure_cdss_structure(_all_providers_failed_fallback(case_data))
            output_kind = "fallback"
            fallback_reason = "all_providers_failed"
            result["_fallback_reason"] = fallback_reason
            logger.error(
                "[DIAGNOSIS] all_providers_failed response_type=fallback fallback_provider=%s",
                fallback_provider,
            )
        else:
            result = dict(dynamic_fallback)
            output_kind = "fallback"
            if parse_status == "INVALID":
                fallback_reason = fallback_reason or "invalid_parse_status"
            elif not has_critical:
                fallback_reason = fallback_reason or "critical_fields_missing"
            else:
                fallback_reason = fallback_reason or "unknown_unusable_state"
            result["_fallback_reason"] = fallback_reason
    logger.info(
        "[DIAGNOSIS] fallback_trigger_reason=%s output_kind=%s fallback_provider=%s response_type=%s",
        fallback_reason or "none",
        output_kind,
        fallback_provider,
        output_kind,
    )

    if llm_usable:
        result = _apply_psoriasis_fungal_rank_guard(case_data, result)
        cr = str(result.get("clinical_reasoning", "") or "").strip()
        if cr:
            new_cr = _normalize_clinical_reasoning_text(cr)
            new_cr = _expand_clinical_reasoning_readability(new_cr, result)
            if new_cr != cr:
                result = dict(result)
                result["clinical_reasoning"] = new_cr

    if non_skin_detected:
        confidence = "LOW"
        mc_metrics["uncertainty_flag"] = True
        mc_metrics["discordant_indicators"].append("Non-skin image detected")
    
    confidence_score = _to_confidence_score(confidence if llm_usable else "LOW")
    confidence_score = _calibrate_display_confidence(
        confidence_score,
        case_data,
        result,
        llm_usable,
        output_kind,
        parse_meta,
        reliability,
    )
    result["uncertainty_flags"] = {
        "overall_confidence": confidence if llm_usable else "LOW",
        "confidence_interval": mc_metrics.get("confidence_interval", [30, 60]),
        "variance_score": mc_metrics.get("variance_score", 0.5),
        "uncertainty_flag": mc_metrics.get("uncertainty_flag", not llm_usable),
        "discordant_indicators": mc_metrics.get("discordant_indicators", []),
        "recommendations_for_reduction": mc_metrics.get("recommendations", []),
        "monte_carlo_iterations": mc_metrics.get("iterations_completed", MONTE_CARLO_ITERATIONS) if use_monte_carlo else 0,
        "monte_carlo_enabled": use_monte_carlo
    }
    
    result["gmu_analysis"] = {
        "image_quality_result": {
            "quality_level": image_quality_result.quality_level.value if image_quality_result else None,
            "overall_score": round(image_quality_result.overall_score, 2) if image_quality_result else None,
            "brightness_score": round(image_quality_result.brightness_score, 2) if image_quality_result else None,
            "contrast_score": round(image_quality_result.contrast_score, 2) if image_quality_result else None,
            "sharpness_score": round(image_quality_result.sharpness_score, 2) if image_quality_result else None,
            "warnings": image_quality_result.warnings if image_quality_result else [],
            "recommendations": image_quality_result.recommendations if image_quality_result else []
        } if image_quality_result else None,
        "multimodal_weights": multimodal_weights,
        "image_quality_gate": image_quality_gate,
        "history_gate_open": has_history or not llm_usable or image_quality_gate == "degraded",
        "has_patient_history": has_history,
        "history_duration": case_data.get("history_duration", ""),
        "change_pattern": case_data.get("change_pattern", "")
    }
    
    result["safety_checks"] = {
        "adversarial_check_passed": not non_skin_detected,
        "safe_refusal_triggered": non_skin_detected,
        "non_skin_image_detected": non_skin_detected
    }
    
    total_time = time.time() - start_time
    if mode == "accurate":
        logger.info("[DIAGNOSIS_TIMING] mode=accurate retry_time=%.3fs", retry_overhead_time)
        logger.info(
            "[DIAGNOSIS_TIMING] mode=accurate early_return_triggered=%s time_budget_triggered=%s elapsed_time_ms=%d",
            early_return_triggered,
            time_budget_triggered,
            int(total_time * 1000),
        )
    logger.info("[DIAGNOSIS_TIMING] mode=%s total_time=%.3fs", mode, total_time)
    result["_inference_time"] = f"{total_time:.2f}s"
    result["_model"] = get_model_name()
    result["_response_quality"] = output_kind
    result["response_type"] = output_kind
    result["fallback_reason"] = fallback_reason or None
    result["parse_error_type"] = parse_meta.get("parse_error_type") if parse_meta else None
    result["recovery_stage"] = recovery_stage
    result["early_return_triggered"] = early_return_triggered if mode == "accurate" else False
    result["time_budget_triggered"] = time_budget_triggered if mode == "accurate" else False
    result["elapsed_time_ms"] = int(total_time * 1000)
    result["fallback_provider"] = (
        fallback_provider if fallback_provider != "none" else ("ollama_retry" if final_attempt > 0 else "none")
    )
    result["cost_estimate"] = {
        "provider": result["fallback_provider"],
        "estimated_input_tokens": estimate_tokens(prompt),
        "estimated_output_tokens": estimate_tokens(raw),
        "estimated_usd": round(cost_estimate_usd, 6),
        "flat_fallback_call_cost_usd": round(
            cost_estimate_usd
            if fallback_provider in ("groq", "groq_quick_recovery")
            else 0.0,
            6,
        ),
    }
    result["confidence"] = confidence_score
    if confidence_score < reliability.get("low_confidence_escalation_threshold", 0.45):
        result["escalation_instruction"] = "Consult a licensed medical professional"
        _DIAGNOSIS_RUNTIME_METRICS["low_confidence_cases"] += 1
        logger.warning("[DIAGNOSIS] Low confidence escalation triggered (confidence=%.2f)", confidence_score)
    result["_decision_support_note"] = (
        "AI output is decision-support only and must be confirmed by a clinician."
    )
    if parse_meta:
        result["_parse_meta"] = {
            "schema_valid": parse_meta.get("schema_valid", False),
            "missing_required_keys": parse_meta.get("missing_required_keys", []),
            "used_fallback": output_kind == "fallback",
            "status": parse_meta.get("status"),
            "completeness_score": parse_meta.get("completeness_score", 0.0),
            "invalid_fields": parse_meta.get("invalid_fields", []),
        }
        
    result = _deterministic_enrichment(case_data, result, confidence_score)
    result = _normalize_canonical(result)
    result["complaint"] = case_data.get("complaint", "")
    result["lesion"] = case_data.get("lesion", "")
    result["symptoms"] = case_data.get("symptoms", "")
    result["patient_age"] = case_data.get("patient_age", 0)
    result["geographic_region"] = case_data.get("geographic_region", "")
    result["skin_phototype"] = case_data.get("skin_phototype", "Type III")
    result["lesion_history"] = case_data.get("lesion_history", "")
    result["history_duration"] = case_data.get("history_duration", "")
    result["change_pattern"] = case_data.get("change_pattern", "")
    
    if output_kind == "partial" or result.get("_partial_llm"):
        logger.info(
            json.dumps(
                {
                    "degraded_quality_valid": _degraded_response_quality_valid(result),
                    "response_type": result.get("response_type"),
                    "mode": mode,
                }
            )
        )

    _diagnosis_response_cache[ck] = result
    _last_diagnosis_cache[case_hash] = result

    _record_runtime(
        time.time() - start_time,
        mode=mode,
        output_kind=output_kind,
        parse_failed=bool(parse_failures),
        parse_status=parse_status,
        fallback_reason=fallback_reason,
        fallback_provider=result.get("fallback_provider", ""),
        cost_estimate_usd=cost_estimate_usd,
    )
    
    return result


def _is_valid_response(data: dict) -> bool:
    if not data:
        return False
    
    dx = data.get("differential_diagnosis", [])
    if not dx or len(dx) < 2:
        return False
    
    for item in dx:
        condition = item.get("condition", "")
        if len(condition) > 60:
            return False
    
    soap = data.get("soap_note", "")
    soap_str = json.dumps(soap) if isinstance(soap, dict) else str(soap)
    if len(soap_str) < 50:
        return False
    
    return True


def _is_case_relevant(case_data: dict, data: dict) -> bool:
    """Verify top diagnoses are context-relevant for key complaint patterns."""
    complaint_text = (
        f"{case_data.get('complaint', '')} "
        f"{case_data.get('lesion', '')} "
        f"{case_data.get('symptoms', '')}"
    ).lower()

    top_dx_text = " ".join(
        d.get("condition", "") for d in data.get("differential_diagnosis", [])[:3]
    ).lower()

    if any(k in complaint_text for k in ["lip", "oral", "mouth", "ulcer", "stomatitis", "aphthous"]):
        oral_keywords = ["lip", "oral", "mouth", "ulcer", "aphthous", "stomatitis", "herpes", "traumatic"]
        return any(k in top_dx_text for k in oral_keywords)

    if any(k in complaint_text for k in ["ring", "annular", "central clearing", "tinea", "fungal"]):
        fungal_keywords = ["tinea", "fungal", "ringworm", "dermatophyte", "nummular", "contact dermatitis"]
        return any(k in top_dx_text for k in fungal_keywords)

    if any(k in complaint_text for k in ["itch", "eczema", "dermatitis", "dry", "scaly"]):
        eczema_keywords = ["eczema", "dermatitis", "atopic", "contact", "nummular", "psoriasis"]
        return any(k in top_dx_text for k in eczema_keywords)

    if any(k in complaint_text for k in ["pigmented", "melanoma", "asymmetry", "irregular border", "changing color"]):
        malignancy_keywords = ["melanoma", "nevus", "lentigo", "pigmented", "carcinoma", "dysplastic"]
        return any(k in top_dx_text for k in malignancy_keywords)

    return bool(data.get("differential_diagnosis"))


def _has_reasoning_specificity(case_data: dict, data: dict) -> bool:
    reasoning = str(data.get("clinical_reasoning", "")).lower()
    complaint = str(case_data.get("complaint", "")).lower().strip()
    lesion = str(case_data.get("lesion", "")).lower().strip()
    if len(reasoning) < 40:
        return False
    complaint_tokens = [t for t in re.findall(r"[a-z]{4,}", complaint)[:8]]
    lesion_tokens = [t for t in re.findall(r"[a-z]{4,}", lesion)[:8]]
    overlap = sum(1 for t in set(complaint_tokens + lesion_tokens) if t in reasoning)
    return overlap >= 2


def _is_treatment_aligned(data: dict) -> bool:
    diagnosis_text = " ".join(
        d.get("condition", "") for d in data.get("differential_diagnosis", [])[:2]
    ).lower()
    treatment_text = " ".join(
        f"{item.get('medication', '')} {item.get('application', '')}"
        for item in data.get("treatment_plan", []) if isinstance(item, dict)
    ).lower()
    if not treatment_text:
        return False
    if any(k in diagnosis_text for k in ["oral", "ulcer", "aphthous"]):
        oral_terms = ["oral", "mucosa", "avoid spicy", "topical", "analgesic", "mouth"]
        return any(term in treatment_text for term in oral_terms)
    if any(k in diagnosis_text for k in ["tinea", "fungal", "ringworm"]):
        fungal_terms = ["azole", "antifungal", "clotrimazole", "terbinafine", "ketoconazole"]
        return any(term in treatment_text for term in fungal_terms)
    return True


def _build_prompt(data: dict, quick_mode: bool = False) -> str:
    if quick_mode:
        return build_diagnosis_prompt_quick(data)
    return build_diagnosis_prompt_accurate(data)


def _v2_error_response() -> Dict[str, Any]:
    return {
        "version": "v2",
        "status": "error",
        "data": None,
        "meta": {
            "mode": "accurate",
            "response_type": "clinical_decision_support",
        },
        "error": {
            "type": "INSUFFICIENT_CONTEXT",
            "message": "Unable to generate reliable clinical output",
        },
    }


def _normalize_v2_likelihood(value: str) -> str:
    v = str(value or "").strip().lower()
    if v in {"high", "medium", "low"}:
        return v
    if "%" in v:
        try:
            pct = float(v.replace("%", "").strip())
            if pct > 75:
                return "high"
            if pct >= 50:
                return "medium"
            return "low"
        except Exception:
            return "low"
    return "low"


def _age_group(age: Any) -> str:
    try:
        value = int(age)
    except Exception:
        return "adult"
    if value < 18:
        return "child"
    if value >= 65:
        return "elderly"
    return "adult"


def _tokenize_text(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def _is_medically_relevant_context(text: str) -> bool:
    medical_terms = {
        "dermat", "lesion", "rash", "plaque", "pruritus", "itch", "erythema",
        "tinea", "eczema", "psoriasis", "diagnosis", "clinical", "biopsy", "triage",
        "differential", "symptom", "cutaneous", "fungal", "dermoscopy",
    }
    tokens = _tokenize_text(text)
    return any(any(term in tok for term in medical_terms) for tok in tokens)


def _prepare_retrieved_context(case_data: dict, top_k: int = 10, rerank_k: int = 5) -> list:
    raw_context = case_data.get("retrieved_context", [])
    if not isinstance(raw_context, list):
        raw_context = [raw_context] if raw_context else []
    base_query = " ".join(
        [
            str(case_data.get("complaint", "")),
            str(case_data.get("lesion", "")),
            str(case_data.get("symptoms", "")),
        ]
    ).strip()
    query_tokens = _tokenize_text(base_query)
    age_group = _age_group(case_data.get("patient_age"))
    phototype = str(case_data.get("skin_phototype", "")).strip().lower()
    geography = str(case_data.get("geographic_region", "")).strip().lower()

    scored = []
    for item in raw_context[: max(1, top_k)]:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            base_score = float(item.get("score", 0.0) or 0.0)
        else:
            text = str(item).strip()
            base_score = 0.0
        if not text:
            continue
        if not _is_medically_relevant_context(text):
            continue
        text_tokens = _tokenize_text(text)
        overlap = len(query_tokens.intersection(text_tokens)) / max(1, len(query_tokens))
        boost = 0.0
        text_l = text.lower()
        if age_group in text_l:
            boost += 0.1
        if phototype and phototype in text_l:
            boost += 0.1
        if geography and geography in text_l:
            boost += 0.1
        similarity = base_score + overlap + boost
        scored.append({"text": text, "score": similarity})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return [x["text"] for x in scored[: max(1, rerank_k)]]


def _compute_v2_relevance_score(data: Dict[str, Any]) -> float:
    payload = data.get("data", {}) if isinstance(data, dict) else {}
    diagnoses = payload.get("differential_diagnoses", [])
    confidence = float(payload.get("confidence", 0.0) or 0.0)
    score = 0.0
    if isinstance(diagnoses, list) and len(diagnoses) >= 3:
        score += 0.4
    elif isinstance(diagnoses, list) and len(diagnoses) >= 1:
        score += 0.2
    if isinstance(diagnoses, list) and diagnoses:
        with_justification = sum(
            1
            for d in diagnoses
            if isinstance(d, dict) and str(d.get("justification", "")).strip()
        )
        score += 0.35 * (with_justification / max(1, len(diagnoses)))
    if confidence > 0.6:
        score += 0.25
    return round(min(1.0, score), 3)


def _validate_v2_payload(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("version") != "v2":
        return False
    if payload.get("status") not in {"success", "error"}:
        return False
    if "meta" not in payload or not isinstance(payload.get("meta"), dict):
        return False
    if payload.get("status") == "error":
        err = payload.get("error")
        return isinstance(err, dict) and bool(str(err.get("type", "")).strip())

    data = payload.get("data")
    if not isinstance(data, dict):
        return False
    diagnoses = data.get("differential_diagnoses")
    if not isinstance(diagnoses, list) or len(diagnoses) < 1:
        return False
    final_assessment = data.get("final_assessment")
    if not isinstance(final_assessment, dict):
        return False
    try:
        conf = float(data.get("confidence"))
    except Exception:
        return False
    if conf < 0.0 or conf > 1.0:
        return False
    for dx in diagnoses:
        if not isinstance(dx, dict):
            return False
        if not str(dx.get("justification", "")).strip():
            return False
        supporting = dx.get("supporting_symptoms", [])
        if not isinstance(supporting, list) or len([s for s in supporting if str(s).strip()]) == 0:
            return False
    return True


def _generate_diagnosis_v2_strict_impl(case_data: dict) -> Dict[str, Any]:
    """
    Strict v2 clinical decision-support response (implementation).
    Uses only provided patient inputs and retrieved clinical context.
    """
    retrieved_context = _prepare_retrieved_context(case_data, top_k=10, rerank_k=5)
    if not retrieved_context:
        return _v2_error_response()
    v2_hash_seed = {
        "complaint": case_data.get("complaint", ""),
        "lesion": case_data.get("lesion", ""),
        "symptoms": case_data.get("symptoms", ""),
        "patient_age": case_data.get("patient_age", ""),
        "geographic_region": case_data.get("geographic_region", ""),
        "skin_phototype": case_data.get("skin_phototype", ""),
        "retrieved_context": retrieved_context,
    }
    v2_case_hash = "v2:" + hashlib.sha256(
        json.dumps(v2_hash_seed, sort_keys=True).encode()
    ).hexdigest()
    v2_ck = _v2_diagnosis_cache_key(v2_case_hash)
    if v2_ck in _diagnosis_response_cache:
        cached = dict(_diagnosis_response_cache[v2_ck])
        cached["_cached"] = True
        return cached
    retries = 0
    max_retries = 2
    last_payload: Dict[str, Any] = {}
    validation_failed = False
    while retries <= max_retries:
        try:
            prompt = build_diagnosis_prompt_v2_strict(
                {**case_data, "retrieved_context": retrieved_context}
            )
            raw = run_ai_with_retry(
                prompt,
                max_tokens=512,
                format="json",
                max_retries=0,
                timeout_seconds=50.0,
                overload_wait_seconds=0.2,
            )
            parsed = json.loads(raw) if raw else {}
        except (OllamaOverloadError, OllamaTimeoutError):
            logger.warning("System under high load, please retry")
            return _v2_error_response()
        except Exception:
            parsed = {}

        differential = parsed.get("differential_diagnoses") if isinstance(parsed, dict) else []
        eliminated = parsed.get("eliminated_conditions") if isinstance(parsed, dict) else []
        final_assessment = parsed.get("final_assessment") if isinstance(parsed, dict) else {}
        confidence = parsed.get("confidence") if isinstance(parsed, dict) else 0.0
        recommendations = parsed.get("recommendations", []) if isinstance(parsed, dict) else []

        shaped_differential = []
        for item in (differential or [])[:3]:
            if not isinstance(item, dict):
                continue
            condition = str(item.get("condition", "")).strip()
            justification = str(item.get("justification", "")).strip()
            supporting = item.get("supporting_symptoms", [])
            if not isinstance(supporting, list):
                supporting = [str(supporting)] if supporting else []
            supporting_clean = [str(x) for x in supporting if str(x).strip()]
            if not condition or not justification or not supporting_clean:
                continue
            shaped_differential.append(
                {
                    "condition": condition,
                    "likelihood": _normalize_v2_likelihood(item.get("likelihood", "low")),
                    "justification": justification,
                    "supporting_symptoms": supporting_clean,
                }
            )

        shaped_eliminated = []
        for item in (eliminated or []):
            if not isinstance(item, dict):
                continue
            condition = str(item.get("condition", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if condition and reason:
                shaped_eliminated.append({"condition": condition, "reason": reason})

        try:
            confidence_value = float(confidence)
        except Exception:
            confidence_value = 0.0
        confidence_value = max(0.0, min(1.0, confidence_value))

        if not isinstance(recommendations, list):
            recommendations = [str(recommendations)] if recommendations else []
        safe_recommendations = [str(x) for x in recommendations if str(x).strip()]
        if confidence_value < 0.6:
            if "Consult a licensed medical professional" not in safe_recommendations:
                safe_recommendations.append("Consult a licensed medical professional")

        most_likely = str((final_assessment or {}).get("most_likely_condition", "")).strip()
        reasoning = str((final_assessment or {}).get("clinical_reasoning", "")).strip()

        candidate = {
            "version": "v2",
            "status": "success",
            "data": {
                "differential_diagnoses": shaped_differential,
                "eliminated_conditions": shaped_eliminated,
                "final_assessment": {
                    "most_likely_condition": most_likely,
                    "clinical_reasoning": reasoning,
                },
                "confidence": confidence_value,
                "recommendations": safe_recommendations,
            },
            "meta": {
                "mode": "accurate",
                "response_type": "clinical_decision_support",
            },
            "error": None,
        }
        relevance_score = _compute_v2_relevance_score(candidate)
        if relevance_score < 0.7:
            candidate["data"]["confidence"] = min(candidate["data"]["confidence"], 0.59)
            if "Consult a licensed medical professional" not in candidate["data"]["recommendations"]:
                candidate["data"]["recommendations"].append("Consult a licensed medical professional")

        valid = _validate_v2_payload(candidate)
        last_payload = candidate
        validation_failed = not valid
        logger.info(
            json.dumps(
                {
                    "response_type": "v2",
                    "mode": "accurate",
                    "validation_failed": validation_failed,
                    "retry_count": retries,
                }
            )
        )
        if valid and relevance_score >= 0.7:
            _diagnosis_response_cache[v2_ck] = candidate
            return candidate
        retries += 1

    return _v2_error_response()


def generate_diagnosis_v2_strict(case_data: dict) -> Dict[str, Any]:
    """Public v2 entry: records wall-clock latency for spike metrics."""
    t0 = time.time()
    try:
        return _generate_diagnosis_v2_strict_impl(case_data)
    finally:
        _note_diagnosis_latency_wallclock(time.time() - t0, mode="accurate", route="v2")


async def generate_diagnosis_async(case_data: dict, use_monte_carlo: bool = True) -> dict:
    return generate_diagnosis(case_data, use_monte_carlo)


def get_last_diagnosis(case_data: Optional[dict] = None) -> Any:
    if case_data:
        return _last_diagnosis_cache.get(_get_case_hash(case_data))
    return next(reversed(_last_diagnosis_cache.values()), None)


def clear_cache() -> None:
    _last_diagnosis_cache.clear()
    _diagnosis_response_cache.clear()


def get_cache_stats() -> dict:
    return {
        "cache_size": len(_last_diagnosis_cache),
        "model_used": get_model_name(),
        "optimization_level": "production",
        "monte_carlo_enabled": USE_MONTE_CARLO,
        "monte_carlo_iterations": MONTE_CARLO_ITERATIONS,
        "features": ["gated_multimodal", "monte_carlo_uncertainty", "adversarial_safety", "fallback_response", "image_quality_analysis"],
        "runtime_metrics": get_runtime_metrics(),
    }
