def build_soap_prompt(case: str) -> str:
    prompt = f"""
You are a medical AI assistant for dermatology in low-resource environments.
Your task is to convert the following clinical case description into a structured medical SOAP note.

Case Description:
{case}

Format your response strictly using this structure:

Subjective:
(Detail the patient's chief complaint, history of present illness, symptoms, and relevant history reported by the patient)

Objective:
(Detail observable, measurable data such as lesion appearance, size, physical exam findings, and any test results available)

Assessment:
(Provide the professional medical diagnosis or differential diagnoses based on the subjective and objective data)

Plan:
(Outline the recommended treatment, further tests, patient education, and follow-up or referral advice)

Ensure the language is concise, professional, and clinical.
"""
    return prompt
