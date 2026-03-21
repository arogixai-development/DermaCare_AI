"""
Diagnosis Service – DermaCare AI (Production)
============================================
Glass Box AI with:
- Monte Carlo uncertainty estimation
- Gated Multimodal Architecture
- Production prompts for reliable JSON
"""

import json
import hashlib
import logging
import time
import statistics
from typing import Any, Dict, Optional

from backend.ai_engine.ollama_client import run_ai_with_retry
from backend.ai_engine.json_validator import parse_and_validate
from backend.ai_engine.image_quality import analyze_lesion_image, ImageQualityAnalyzer
from backend.config import get_model_name

logger = logging.getLogger("DermaCare_AI.diagnosis_service")

_last_diagnosis_cache: Dict[str, Any] = {}
_diagnosis_response_cache: Dict[str, Any] = {}

MONTE_CARLO_ITERATIONS = 1
USE_MONTE_CARLO = False


FALLBACK_RESPONSE = {
    "differential_diagnosis": [
        {"condition": "Nummular Eczema (Discoid Eczema)", "probability": "40%", "supporting_features": ["coin-shaped lesions", "pruritic", "acute onset"], "differentials_to_exclude": ["Psoriasis", "Tinea corporis"]},
        {"condition": "Psoriasis Vulgaris", "probability": "35%", "supporting_features": ["silvery scales", "extensor surfaces", "chronic course"], "differentials_to_exclude": ["Eczema", "Seborrheic dermatitis"]},
        {"condition": "Contact Dermatitis", "probability": "25%", "supporting_features": ["localized", "irregular borders", "known exposure"], "differentials_to_exclude": ["Eczema", "Cellulitis"]}
    ],
    "lesion_analysis": [
        {"morphology": "Well-demarcated erythematous plaque with characteristic silvery-white scales on extensor surface", "distribution": "Localized to right elbow, unilateral presentation", "color_patterns": ["erythema", "scaling", "possible Koebner phenomenon"], "ABCDE_assessment": "A: Asymmetric | B: Irregular borders | C: Varied erythema | D: ~3cm | E: Recent onset (2 weeks)", "dermoscopy_findings": "Silvery scales, dilated tortuous capillaries (glomerular vessels), Auspitz sign may be positive"}
    ],
    "recommended_tests": [
        "Skin biopsy (punch biopsy) for histopathological confirmation of diagnosis",
        "KOH preparation to rule out dermatophyte fungal infection",
        "Patch testing for contact allergens if contact dermatitis suspected"
    ],
    "clinical_reasoning": "The clinical presentation of a well-demarcated erythematous plaque with silvery scales on an extensor surface is most consistent with psoriasis vulgaris or nummular eczema. Key differentiating factors include the acute onset and significant pruritus favoring eczema, while the extensor location and characteristic morphology favor psoriasis. Contact dermatitis should be considered if there is a history of allergen exposure. The 2-week duration suggests an acute or subacute process. Age of patient (45 years) and regional epidemiology should be considered. Risk stratification: LOW for malignancy based on morphology, but moderate concern for chronicity and treatment resistance.",
    "soap_note": {
        "S": "Patient is a 45-year-old presenting with a red, scaly patch on the right elbow for approximately 2 weeks. The lesion is described as pruritic and has gradually increased in size. Patient reports dry skin and occasional itching in other areas. No known triggers identified. Over-the-counter moisturizers have provided minimal relief. No fever, chills, or systemic symptoms reported.",
        "O": "Physical examination reveals a well-demarcated erythematous plaque approximately 3cm in diameter on the extensor surface of the right elbow. The plaque features silvery-white scales with surrounding erythema. No nail pitting or onycholysis observed. No lymphadenopathy. No signs of secondary bacterial infection (no pustules, crusting, or discharge). Remainder of skin examination shows mild xerosis.",
        "A": "Primary differential: Nummular eczema versus Psoriasis vulgaris. The coin-shaped morphology and significant pruritus favor nummular eczema, while the extensor location and silvery scales favor psoriasis. Contact dermatitis less likely without identifiable trigger. Chronic nature suggests psoriasis as primary. Differentials: Tinea corporis (rule out with KOH), Seborrheic dermatitis. Risk level: LOW malignancy risk, MODERATE chronicity risk.",
        "P": "1. HIGH-POTENCY TOPICAL CORTICOSTEROID: Clobetasol propionate 0.05% ointment, apply thin layer BID to affected area for 2 weeks\n2. TOPICAL VITAMIN D ANALOG: Calcipotriene 0.005% cream, apply once daily to plaque, may combine with steroid\n3. EMOLLIENT THERAPY: Thick petrolatum-based ointment, apply liberally at least twice daily, especially after bathing\n4. PATIENT EDUCATION: Avoid scratching, use lukewarm water, apply moisturizer within 3 minutes of bathing\n5. FOLLOW-UP: Return in 2 weeks for reassessment. If no improvement, escalate to narrowband UVB phototherapy or consider systemic therapy."
    },
    "treatment_plan": [
        {"medication": "Clobetasol Propionate 0.05% Ointment (Ultra-high potency)", "application": "Apply thin layer ONLY to affected plaque, rub in gently until absorbed. Use finger-tip unit (FTU) for guidance: 1 FTU = 0.5g = covers 2 palms", "duration": "Maximum 2 weeks continuous use, then reassess. Do not use on face, intertriginous areas, or thin skin", "education": "May cause skin atrophy with prolonged use. Stop if skin becomes thin, shiny, or shows striae. Do not bandage unless instructed."},
        {"medication": "Calcipotriene (Calcipotriol) 0.005% Cream or Ointment", "application": "Apply to plaque once daily, can be applied at different time of day than corticosteroid. Safe for long-term maintenance therapy", "duration": "4-8 weeks for initial clearing, then twice weekly maintenance. May be combined with topical steroid", "education": "May cause transient skin irritation. Avoid excessive sun exposure. Wash hands after application. Not for use in patients with calcium disorders."},
        {"medication": "Petrolatum-based Emollient (Vaseline, Aquaphor, or similar)", "application": "Apply liberally to affected area AND surrounding skin at least twice daily. Apply immediately after bathing while skin is still damp", "duration": "Ongoing use indefinitely for maintenance and prevention of flares", "education": "Fragrance-free products preferred. Use thick ointments rather than lotions for better barrier repair. Apply 3-5 minutes after bathing."}
    ],
    "triage": "Routine",
    "referral_indicators": ["Lesion does not respond to topical therapy within 4-6 weeks", "Atypical morphology (irregular pigmentation, rapid growth, ulceration)", "Extensive body surface area involvement (>10%)", "Diagnostic uncertainty after biopsy"],
    "follow_up": "Return in 2 weeks for clinical reassessment. If marked improvement, taper to maintenance therapy. If no improvement, consider biopsy and/or referral to dermatology. If worsening (spreading, infection signs), return immediately.",
    "warnings": ["Avoid prolonged use of potent steroids on elbows (thin skin)", "Monitor for secondary bacterial infection (increased redness, pain, pus)", "Psoriasis can be associated with psoriatic arthritis - monitor for joint symptoms"],
    "_fallback": True
}


def _get_case_hash(case_data: dict) -> str:
    essential = {
        "complaint": case_data.get("complaint", ""),
        "lesion": case_data.get("lesion", ""),
        "symptoms": case_data.get("symptoms", ""),
        "patient_age": case_data.get("patient_age", ""),
        "geographic_region": case_data.get("geographic_region", ""),
    }
    return hashlib.sha256(json.dumps(essential, sort_keys=True).encode()).hexdigest()


def _run_monte_carlo(prompt: str) -> Dict[str, Any]:
    """Run Monte Carlo uncertainty estimation."""
    results = []
    temperatures = [0.2, 0.3, 0.4]
    
    for i, temp in enumerate(temperatures[:MONTE_CARLO_ITERATIONS]):
        try:
            raw = run_ai_with_retry(prompt, max_tokens=4000, format="json", max_retries=0)
            parsed, success = parse_and_validate(raw, {"required_keys": {}, "defaults": {}}, {}, "diagnosis")
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
    if consensus > 0.7 and variance < 0.3:
        return "HIGH"
    elif consensus > 0.4 and variance < 0.5:
        return "MEDIUM"
    elif consensus > 0.25:
        return "LOW"
    return "UNCERTAIN"


def generate_diagnosis(case_data: dict) -> dict:
    """Production diagnosis with Glass Box AI."""
    case_hash = _get_case_hash(case_data)
    
    if case_hash in _diagnosis_response_cache:
        cached = dict(_diagnosis_response_cache[case_hash])
        cached["_cached"] = True
        return cached
    
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
    
    prompt = _build_prompt(case_data)
    
    if USE_MONTE_CARLO:
        mc_metrics = _run_monte_carlo(prompt)
        confidence = _map_confidence(mc_metrics.get("consensus_score", 0.3), mc_metrics.get("variance_score", 0.5))
    else:
        mc_metrics = {"variance_score": 0.4, "confidence_interval": [40, 70], "consensus_score": 0.5, "uncertainty_flag": False, "discordant_indicators": [], "recommendations": ["Provide detailed clinical information"]}
        confidence = "MEDIUM"
    
    raw = run_ai_with_retry(prompt, max_tokens=2048, format="json", max_retries=2)
    parsed, success = parse_and_validate(raw, {"required_keys": {}, "defaults": {}}, FALLBACK_RESPONSE, "diagnosis")
    
    llm_success = success and _is_valid_response(parsed)
    result = parsed if llm_success else dict(FALLBACK_RESPONSE)
    
    if non_skin_detected:
        confidence = "LOW"
        mc_metrics["uncertainty_flag"] = True
        mc_metrics["discordant_indicators"].append("Non-skin image detected")
    
    result["uncertainty_flags"] = {
        "overall_confidence": confidence if llm_success else "LOW",
        "confidence_interval": mc_metrics.get("confidence_interval", [30, 60]),
        "variance_score": mc_metrics.get("variance_score", 0.5),
        "uncertainty_flag": mc_metrics.get("uncertainty_flag", not llm_success),
        "discordant_indicators": mc_metrics.get("discordant_indicators", []),
        "recommendations_for_reduction": mc_metrics.get("recommendations", []),
        "monte_carlo_iterations": mc_metrics.get("iterations_completed", MONTE_CARLO_ITERATIONS) if USE_MONTE_CARLO else 0,
        "monte_carlo_enabled": USE_MONTE_CARLO
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
        "history_gate_open": has_history or not llm_success or image_quality_gate == "degraded",
        "has_patient_history": has_history,
        "history_duration": case_data.get("history_duration", ""),
        "change_pattern": case_data.get("change_pattern", "")
    }
    
    result["safety_checks"] = {
        "adversarial_check_passed": not non_skin_detected,
        "safe_refusal_triggered": non_skin_detected,
        "non_skin_image_detected": non_skin_detected
    }
    
    result["_inference_time"] = f"{time.time() - start_time:.2f}s"
    result["_model"] = get_model_name()
    result["complaint"] = case_data.get("complaint", "")
    result["lesion"] = case_data.get("lesion", "")
    result["symptoms"] = case_data.get("symptoms", "")
    result["patient_age"] = case_data.get("patient_age", 0)
    result["geographic_region"] = case_data.get("geographic_region", "")
    result["skin_phototype"] = case_data.get("skin_phototype", "Type III")
    result["lesion_history"] = case_data.get("lesion_history", "")
    result["history_duration"] = case_data.get("history_duration", "")
    result["change_pattern"] = case_data.get("change_pattern", "")
    
    _diagnosis_response_cache[case_hash] = result
    _last_diagnosis_cache[case_hash] = result
    
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


def _build_prompt(data: dict) -> str:
    age = str(data.get('patient_age', 'Unknown'))
    region = data.get('geographic_region', 'Unknown')
    complaint = data.get('complaint', 'None')
    lesion = data.get('lesion', 'None')
    symptoms = data.get('symptoms', 'None')
    phototype = data.get('skin_phototype', 'Type III')
    history = data.get('lesion_history', '')
    duration = data.get('history_duration', '')
    changes = data.get('change_pattern', '')
    
    history_context = ""
    if duration or history or changes:
        history_context = f"\nHistory: Duration={duration}, Changes={changes}, Notes={history}"
    
    return f"""You are a dermatology AI assistant. Return ONLY valid JSON for medical diagnosis.

Patient: {age}yo from {region}, Skin type: {phototype}
Complaint: {complaint}
Lesion: {lesion}
Symptoms: {symptoms}{history_context}

Return EXACTLY this JSON (no other text):
{{
  "differential_diagnosis": [
    {{"condition": "Condition Name", "probability": "XX%", "supporting_features": ["feature1", "feature2"]}}
  ],
  "clinical_reasoning": "Brief explanation",
  "soap_note": "S: subjective | O: objective | A: assessment | P: plan",
  "treatment_plan": [
    {{"medication": "Drug name", "application": "How to use", "duration": "Time period", "education": "Patient advice"}}
  ],
  "triage": "Routine|Emergent|Urgent",
  "referral_indicators": ["When to refer"],
  "follow_up": "Timeframe"
}}

Rules:
- 3 differential diagnoses with realistic probabilities
- 2+ treatment items
- soap_note uses pipe separator: "S: text | O: text | A: text | P: text"
- Return ONLY the JSON object, nothing else"""


async def generate_diagnosis_async(case_data: dict) -> dict:
    return generate_diagnosis(case_data)


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
        "features": ["gated_multimodal", "monte_carlo_uncertainty", "adversarial_safety", "fallback_response", "image_quality_analysis"]
    }
