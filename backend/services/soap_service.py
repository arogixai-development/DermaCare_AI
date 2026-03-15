from backend.ai_engine.ollama_client import run_ai

def generate_soap(case):
    prompt = f"""
Convert the following clinical case into a concise, professional SOAP note. 
Focus on high-yield clinical information. Use bullet points for clarity.

Case Summary & AI Analysis:
{case}

Format the output strictly as follows:
Subjective: (Concise summary of patient history and symptoms)
Objective: (Concise physical exam and test findings)
Assessment: (Concise clinical impression/differential)
Plan: (Concise management and next steps)

Keep the total length under 300 words for rapid processing.
"""
    return run_ai(prompt)
