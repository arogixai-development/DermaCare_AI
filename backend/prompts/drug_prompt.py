def build_drug_prompt(drugs: list) -> str:
    drugs_str = ", ".join(drugs)
    prompt = f"""
You are a senior clinical pharmacologist. Analyze the potential drug-drug interactions for the following list of medications, specifically focusing on dermatology-related treatments where applicable.

Medications: {drugs_str}

Please provide the analysis in the following structured format:

#### Summary
A brief overview of the interaction profile.

#### Major Interactions
List high-severity interactions that require immediate clinical attention or contraindication.

#### Moderate/Minor Interactions
List interactions that may require dosage adjustment or monitoring.

#### Clinical Recommendation
Suggested actions for the healthcare provider (e.g., alternative medications, timing adjustments).

#### Patient Education
Key points to communicate to the patient regarding these medications.

Use clear, professional medical language. If no significant interactions are found, explicitly state that the combination appears safe but should still be monitored.
"""
    return prompt.strip()
