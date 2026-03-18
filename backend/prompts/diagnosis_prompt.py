def build_diagnosis_prompt_optimized(data: dict) -> str:
    """
    State-of-the-art Clinical Prompt for Llama 3 (8B).
    Demands exhaustive pathophysiological depth, detailed morphological analysis,
    and a comprehensive, professional clinical record.
    """
    age       = data.get('patient_age', 'Unknown')
    region    = data.get('geographic_region', 'Unknown')
    complaint = data.get('complaint', 'None')
    lesion    = data.get('lesion', 'None specified')
    symptoms  = data.get('symptoms', 'None reported')
    tests     = data.get('tests', 'None provided')

    prompt = f"""You are a Senior Dermatologist and Clinical Diagnostician at a world-class institution. 
Analyze this clinical case with exhaustive precision and professional depth.

### PATIENT PRESENTATION:
- Age: {age}
- Region: {region}
- Chief Complaint: {complaint}
- Physical Morphology: {lesion}
- Associated Symptoms: {symptoms}
- Relevant History/Tests: {tests}

### MANDATORY CLINICAL REQUIREMENTS:
1. **Possible Diagnoses**: Provide a clear list of differential diagnoses.
2. **Pathophysiological Reasoning**: Write a detailed, technical paragraph explaining the clinical morphology. 
   - Discuss why the specific findings (e.g., scale type, distribution, Auspitz sign, capillary tortuosity) lead to the diagnosis.
   - Mention relevant pathophysiological mechanisms (e.g., epidermal turnover, inflammatory pathways).
3. **Professional SOAP Note**: Provide a exhaustive, continuous string.
   - SUBJECTIVE: Comprehensive patient history, onset, and aggravating/relieving factors.
   - OBJECTIVE: Descriptive dermatological morphology using professional standard terminology.
   - ASSESSMENT: Synthesize findings into a definitive clinical working diagnosis.
   - PLAN: Provide a tiered management strategy including topical therapies, systemic options if indicated, specific diagnostic follow-up, and detailed patient counseling.
4. **Patient-Facing Management**: Provide clear, step-by-step instructions for the patient to follow (e.g., application frequency, skin care behavior).

### OUTPUT FORMAT:
You MUST respond with ONLY a valid JSON object. No explanations, markdown tags, or prose outside the JSON.
{{
  "diagnoses": ["Most likely Dx", "Differential 1", "Differential 2"],
  "reasoning": "A highly detailed, MULTI-PARAGRAPH technical explanation of the clinical findings, morphological analysis, and diagnostic logic.",
  "soap": "SUBJECTIVE: ...\\nOBJECTIVE: ...\\nASSESSMENT: ...\\nPLAN: ...",
  "triage": "Urgent/Moderate/Routine",
  "tests": ["Detailed follow-up test 1", "Diagnostic step 2"],
  "referral": ["Specific specialist guidance"],
  "treatment": ["Medication 1: dosage/frequency", "Step 2: Skin care regimen", "Step 3: Patient education point"]
}}"""
    return prompt


def build_diagnosis_prompt(data: dict) -> str:
    """Legacy function - now uses optimized version"""
    return build_diagnosis_prompt_optimized(data)
