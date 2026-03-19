def build_diagnosis_prompt_optimized(data: dict) -> str:
    """
    Clinical Diagnosis Prompt for DermaCare AI.
    Produces strict JSON output for reliable parsing.
    """
    age       = str(data.get('patient_age', 'Unknown'))
    region    = data.get('geographic_region', 'Unknown')
    complaint = data.get('complaint', 'None')
    lesion    = data.get('lesion', 'None')
    symptoms  = data.get('symptoms', 'None')
    tests     = data.get('tests', 'None')
    phototype = data.get('skin_phototype', 'Type III')

    prompt = f"""Dermatology case analysis. Return ONLY valid JSON:

Patient: {age}yo, {region}, Skin: {phototype}
Complaint: {complaint}
Lesion: {lesion}
Symptoms: {symptoms}
Tests: {tests}

CRITICAL: soap_note must be plain text with | separator, NOT Python dict:
GOOD: "soap_note": "S: Patient reports pain | O: Red lesion found | A: Likely infection | P: Prescribe antibiotic"
BAD: "soap_note": "{{'S': 'Patient reports pain', 'O': 'Red lesion'}}"

JSON template:
{{
  "differential_diagnosis": [
    {{"condition": "Name", "probability": "X%", "supporting_features": ["f1", "f2"]}}
  ],
  "clinical_reasoning": "Reasoning text here",
  "soap_note": "S: subjective text | O: objective text | A: assessment text | P: plan text",
  "treatment_plan": [
    {{"medication": "Drug name", "application": "Apply twice daily", "duration": "7 days", "education": "Advice"}}
  ],
  "triage": "Routine",
  "referral_indicators": ["Warning sign 1"],
  "follow_up": "2 weeks"
}}

Rules: 
- 3 differential diagnoses required
- soap_note MUST use | separator between sections, NOT curly braces
- 2+ treatment items required
- Return valid JSON only, no explanation"""
    return prompt


def build_diagnosis_prompt(data: dict) -> str:
    """Legacy function - now uses optimized version"""
    return build_diagnosis_prompt_optimized(data)
