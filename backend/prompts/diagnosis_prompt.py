"""
Diagnosis Prompt Module - DermaCare AI
==================================================
Implements Step A (Reasoning) and Step B (Formatting) to ensure stable JSON generation.
"""

def build_reasoning_prompt(data: dict) -> str:
    """
    Step A: Clinical reasoning pass (Free-text only).
    """
    age = str(data.get('patient_age', 'Unknown'))
    region = data.get('geographic_region', 'Unknown')
    complaint = data.get('complaint', 'None provided')
    lesion = data.get('lesion', 'None provided')
    symptoms = data.get('symptoms', 'None')
    phototype = data.get('skin_phototype', 'Type III')
    lesion_history = data.get('lesion_history', '')
    history_duration = data.get('history_duration', '')
    change_pattern = data.get('change_pattern', '')
    tests = data.get('tests', '')

    return f"""You are a clinical decision support dermatologist assistant.
Perform a clinical reasoning pass. Do NOT return JSON. Write in free-text.

PATIENT: {age}yo from {region}, Skin Type: {phototype}
CHIEF COMPLAINT: {complaint}
LESION: {lesion}
SYMPTOMS: {symptoms}
TESTS: {tests if tests else 'None available'}
HISTORY: {history_duration} - {change_pattern}
ADDITIONAL: {lesion_history if lesion_history else 'None'}

Please provide:
1. Differential Analysis: Top 3 conditions with probabilities and supporting features.
2. Clinical Reasoning: Why the lead diagnosis is preferred over the alternatives. Note any missing or contradictory features.
3. Confidence Rationale: Your level of certainty and why.
4. Treatment Rationale: High-level recommendations for management.
5. Triage: Routine or Urgent.

Keep your reasoning clear and concise.
"""

def build_formatting_prompt(reasoning: str, data: dict) -> str:
    """
    Step B: Structured formatting pass.
    """
    return f"""You are a data extraction assistant.
Convert the following clinical reasoning into strict JSON format.
Return ONLY valid JSON. No markdown or text outside the JSON object.

CLINICAL REASONING:
{reasoning}

Required JSON shape:
{{
  "differential_diagnosis": [
    {{"condition": "...", "probability": "...", "supporting_features": ["..."], "differentials_to_exclude": ["..."]}}
  ],
  "lesion_analysis": [
    {{"morphology": "...", "distribution": "..."}}
  ],
  "clinical_reasoning": "A 2-3 sentence summary of the clinical reasoning provided above.",
  "recommended_tests": ["..."],
  "triage": "Routine|Urgent"
}}
"""

def build_formatting_repair_prompt(reasoning: str, data: dict, previous_output: str) -> str:
    """Repair prompt for Step B formatting."""
    base = build_formatting_prompt(reasoning, data)
    return (
        base
        + "\n\nCRITICAL: Your previous output failed JSON validation. Fix formatting issues and return strict JSON only."
        + f"\nPrevious invalid output (truncated):\n{previous_output[:700]}"
    )

def build_diagnosis_prompt_quick(data: dict) -> str:
    """Quick-mode: single-pass JSON generation (lightweight schema)."""
    age = str(data.get("patient_age", "Unknown"))
    region = data.get("geographic_region", "Unknown")
    complaint = data.get("complaint", "None provided")
    lesion = data.get("lesion", "None provided")
    symptoms = data.get("symptoms", "None")

    return f"""You are a dermatology clinical decision support assistant.
Return ONLY valid JSON. No markdown or prose outside the JSON object.

Patient: Age {age}, Region {region}
Complaint: {complaint}
Lesion: {lesion}
Symptoms: {symptoms}

Required JSON shape:
{{
  "differential_diagnosis": [
    {{"condition":"Provisional ...", "probability":"..%", "supporting_features":["..."], "differentials_to_exclude":["..."]}}
  ],
  "lesion_analysis": [
    {{"morphology":"...", "distribution":"..."}}
  ],
  "clinical_reasoning": "1-2 sentences only: lead diagnosis vs key alternative.",
  "recommended_tests": ["..."],
  "triage": "Routine|Urgent"
}}
"""

def build_diagnosis_repair_prompt_quick(data: dict, previous_output: str) -> str:
    base = build_diagnosis_prompt_quick(data)
    prev = (previous_output or "")[:700]
    return (
        base
        + "\n\nCRITICAL: Your previous output was invalid JSON. Return ONE valid JSON object only."
        + f"\nPrevious broken output (truncated):\n{prev}"
    )

def build_diagnosis_prompt_optimized(data: dict) -> str:
    """Legacy alias if needed by fallback."""
    return build_diagnosis_prompt_quick(data)

def build_diagnosis_repair_prompt(data: dict, previous_output: str) -> str:
    """Legacy alias if needed by fallback."""
    return build_diagnosis_repair_prompt_quick(data, previous_output)

def build_metadata_weighted_prompt(case_data: dict, image_quality_score: float = 0.5) -> str:
    """Legacy alias."""
    return build_diagnosis_prompt_quick(case_data)

def build_diagnosis_prompt_accurate(data: dict) -> str:
    return build_reasoning_prompt(data)

def build_diagnosis_prompt_v2_strict(data: dict) -> str:
    return build_diagnosis_prompt_quick(data)
