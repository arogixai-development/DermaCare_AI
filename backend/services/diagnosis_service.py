from backend.ai_engine.ollama_client import run_ai
from backend.prompts.diagnosis_prompt import build_diagnosis_prompt

def generate_diagnosis(case_data: dict) -> str:
    """
    Orchestrates the AI diagnosis generation by building the prompt and calling the AI engine.
    """
    prompt = build_diagnosis_prompt(case_data)
    return run_ai(prompt)
