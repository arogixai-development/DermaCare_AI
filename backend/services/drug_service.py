from backend.ai_engine.ollama_client import run_ai_with_retry, check_ollama_connection, OllamaConnectionError
from backend.prompts.drug_prompt import build_drug_prompt
import logging

logger = logging.getLogger("DermaCare_AI.drug_service")

def analyze_drug_interactions(drugs: list) -> str:
    """
    Analyzes potential interactions between a list of drugs using the AI engine.
    Uses retry logic for reliability.
    """
    if not drugs:
        return "No medications provided for analysis."
    
    # Check Ollama connection
    status = check_ollama_connection()
    if not status["connected"]:
        logger.error("Drug service: Ollama not available - %s", status["error"])
        raise OllamaConnectionError(status["error"])
    
    prompt = build_drug_prompt(drugs)
    
    try:
        result = run_ai_with_retry(prompt, max_tokens=1024, max_retries=1)
        if not result or not result.strip():
            return "Unable to analyze drug interactions. Please try again."
        return result
    except OllamaConnectionError:
        raise
    except Exception as e:
        logger.error("Drug interaction analysis failed: %s", str(e))
        return f"Error analyzing drug interactions: {str(e)}"
