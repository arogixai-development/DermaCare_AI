from backend.ai_engine.ollama_client import run_ai
from backend.prompts.drug_prompt import build_drug_prompt

def analyze_drug_interactions(drugs: list) -> str:
    """
    Analyzes potential interactions between a list of drugs using the AI engine.
    """
    if not drugs:
        return "No medications provided for analysis."
    
    prompt = build_drug_prompt(drugs)
    return run_ai(prompt)
