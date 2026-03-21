"""
Diagnosis Prompt Module - DermaCare AI (Simplified for Reliability)
==================================================
Simplified prompt for reliable JSON generation.
"""

def build_diagnosis_prompt_optimized(data: dict) -> str:
    """
    Simplified clinical diagnosis prompt that generates reliable JSON.
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

    prompt = f"""You are a dermatologist. Analyze this case and provide detailed clinical output in JSON format.

PATIENT: {age}yo from {region}, Skin Type: {phototype}
CHIEF COMPLAINT: {complaint}
LESION: {lesion}
SYMPTOMS: {symptoms}
TESTS: {tests if tests else 'None available'}
HISTORY: {history_duration} - {change_pattern}
ADDITIONAL: {lesion_history if lesion_history else 'None'}

Generate a detailed clinical response in this JSON format:
{{
  "differential_diagnosis": [
    {{"condition": "Eczema", "probability": "45%", "supporting_features": ["pruritic", "dry skin", "flexural distribution"], "differentials_to_exclude": ["psoriasis", "tinea"]}},
    {{"condition": "Psoriasis", "probability": "30%", "supporting_features": ["silvery scales", "extensor surfaces", "nail changes"], "differentials_to_exclude": ["eczema", "seborrheic dermatitis"]}},
    {{"condition": "Contact Dermatitis", "probability": "25%", "supporting_features": ["localized", "irregular pattern", "allergen exposure"], "differentials_to_exclude": ["eczema", "cellulitis"]}}
  ],
  "lesion_analysis": [
    {{"morphology": "Well-demarcated erythematous plaque with silvery-white scales on extensor surface", "distribution": "Localized to right elbow, unilateral", "color_patterns": ["erythema", "scaling"], "ABCDE_assessment": "A: Symmetric | B: Regular borders | C: Single color | D: <6mm | E: No evolution", "dermoscopy_findings": "Silvery scales, dilated capillaries"}}
  ],
  "recommended_tests": [
    "Skin biopsy for histopathological confirmation",
    "Patch testing for contact allergens",
    "KOH preparation to rule out fungal infection"
  ],
  "clinical_reasoning": "The clinical presentation of a well-demarcated erythematous plaque with silvery scales on an extensor surface is most consistent with psoriasis or eczema. The chronic nature and characteristic morphology suggest psoriasis as the primary differential. However, the presence of itching and the location make eczema a strong consideration. Contact dermatitis should be ruled out based on exposure history.",
  "soap_note": {{
    "S": "Patient reports a red, scaly patch on the right elbow that has been present for approximately 2 weeks. The lesion is pruritic and has gradually worsened. No known triggers identified. Patient reports dry skin and occasional itching in other areas.",
    "O": "Physical examination reveals a well-demarcated erythematous plaque approximately 3cm in diameter located on the extensor surface of the right elbow. The plaque has silvery-white scales and surrounding erythema. No nail changes observed. No lymphadenopathy.",
    "A": "Primary diagnosis: Psoriasis vulgaris versus nummular eczema. The characteristic morphology and distribution favor psoriasis, though the significant pruritus is more typical of eczema. Chronic course suggests psoriasis. Moderate severity. Differentials: Contact dermatitis, fungal infection.",
    "P": "1. Topical corticosteroid (clobetasol 0.05% ointment) apply thin layer twice daily for 2 weeks\n2. Calcipotriene cream apply once daily to affected area\n3. Emollient apply liberally at least twice daily\n4. Follow-up in 2 weeks; if no improvement, consider biopsy\n5. Patient education: avoid scratching, keep area moisturized"
  }},
  "treatment_plan": [
    {{"medication": "Clobetasol Propionate 0.05% Ointment", "application": "Apply thin layer to affected area twice daily, rub in gently until absorbed", "duration": "2 weeks, then reassess", "education": "Do not use for more than 2 weeks continuously; avoid face and intertriginous areas"}},
    {{"medication": "Calcipotriene (Calcipotriol) 0.005% Cream", "application": "Apply to plaque once daily, may be used with topical steroid", "duration": "4-6 weeks", "education": "May cause local irritation initially; avoid excessive sun exposure"}},
    {{"medication": "Petrolatum-based Emollient", "application": "Apply liberally to affected area and surrounding skin at least twice daily", "duration": "Ongoing", "education": "Use after bathing for best results; fragrance-free products preferred"}}
  ],
  "triage": "Routine",
  "referral_indicators": ["Lesion does not respond to topical therapy within 4 weeks", "Atypical morphology suggesting malignancy"],
  "follow_up": "Return in 2 weeks for reassessment. If no improvement, escalate to narrowband UVB therapy or consider biopsy.",
  "warnings": ["Avoid prolonged use of potent steroids on elbows", "Monitor for signs of secondary bacterial infection"]
}}

Return ONLY valid JSON starting with {{ and ending with }}. No explanations before or after."""
    return prompt


def build_metadata_weighted_prompt(case_data: dict, image_quality_score: float = 0.5) -> str:
    """Prompt for cases relying on metadata."""
    return build_diagnosis_prompt_optimized(case_data)
