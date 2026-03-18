def build_drug_prompt(drugs: list) -> str:
    """
    Builds a strict JSON-only prompt for drug interaction analysis.
    Forces the LLM to return a parseable JSON object every time.
    """
    drugs_str = ", ".join(drugs)

    prompt = f"""You are a senior clinical pharmacologist. You MUST respond with ONLY a valid JSON object.
STRICT RULES:
- Output ONLY the JSON object, nothing else.
- Do NOT include markdown, code fences, explanations, or any text outside the JSON.
- All JSON keys and string values must use double quotes.
- Every required key must be present.

Medications to analyse: {drugs_str}

Output this EXACT JSON structure (replace placeholder values with real clinical content):
{{
  "summary": "Brief overview of the overall interaction profile for these medications.",
  "major_interactions": ["High-severity interaction requiring immediate attention or contraindication, or 'None identified'"],
  "moderate_minor_interactions": ["Moderate/minor interaction requiring monitoring or dose adjustment, or 'None identified'"],
  "clinical_recommendation": "Specific actions for the healthcare provider regarding this combination.",
  "patient_education": "Key points the patient must know about taking these medications together."
}}"""
    return prompt.strip()
