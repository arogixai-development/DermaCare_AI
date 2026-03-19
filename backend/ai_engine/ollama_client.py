import ollama
import asyncio
import hashlib
import json
import logging
from typing import Optional, Dict, Any
from functools import lru_cache
from backend.config import get_model_name

logger = logging.getLogger("DermaCare_AI.ollama_client")

class OllamaConnectionError(Exception):
    """Raised when Ollama is not available or not running."""
    pass

def check_ollama_connection() -> Dict[str, Any]:
    """
    Check if Ollama is running and accessible.
    Returns status info with connection details.
    """
    try:
        models = ollama.list()
        return {
            "connected": True,
            "models": [m.get("name") for m in models.get("models", [])],
            "error": None
        }
    except Exception as e:
        error_msg = str(e)
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            return {
                "connected": False,
                "models": [],
                "error": "Ollama is not running. Please start Ollama: `ollama serve`"
            }
        return {
            "connected": False,
            "models": [],
            "error": f"Ollama error: {error_msg}"
        }

# Cache for AI responses to avoid redundant calls
@lru_cache(maxsize=128)
def _get_prompt_hash(prompt: str) -> str:
    """Generate a hash for the prompt to use as cache key"""
    return hashlib.sha256(prompt.encode()).hexdigest()

def run_ai_optimized(prompt: str, max_tokens: int = 1536, format: str = None) -> str:
    """
    Run AI inference with optimized parameters for maximum performance.
    Uses quantized model and aggressive optimization settings.
    """
    # Check Ollama connection first
    status = check_ollama_connection()
    if not status["connected"]:
        raise OllamaConnectionError(status["error"])
    
    prompt_hash = _get_prompt_hash(prompt)
    
    # Try to get from cache first
    # Note: In production, use Redis or similar for persistent caching
    try:
        # Placeholder for actual cache implementation
        pass
    except:
        pass
    
    # Build options dict - optimized for speed
    options = {
        "num_predict": min(max_tokens, 1500),  # Allow larger responses
        "temperature": 0.3,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "num_gpu": -1,  # Use GPU if available
        "num_thread": 8,
        "num_ctx": 4096,  # Larger context
        "mirostat": 0,
        "stop": ["</s>", "USER:", "ASSISTANT:"]
    }
    
    # Only include format if specified
    kwargs = {"model": get_model_name(), "messages": [{"role": "user", "content": prompt}], "options": options}
    if format:
        kwargs["format"] = format
    
    response = ollama.chat(**kwargs)
    return response["message"]["content"]

async def run_ai_streaming(prompt: str, max_tokens: int = 120, format: str = None):
    """
    Stream AI responses for real-time user feedback.
    """
    prompt_hash = _get_prompt_hash(prompt)
    
    stream = ollama.chat(
        model=get_model_name(),
        messages=[
            {"role": "user", "content": prompt}
        ],
        format=format,
        options={
            "num_predict": max_tokens,
            "temperature": 0.05,
            "top_p": 0.7,
            "num_gpu": -1,
            "num_ctx": 4096
        },
        stream=True
    )
    
    full_response = ""
    for chunk in stream:
        if chunk.get("message", {}).get("content"):
            content = chunk["message"]["content"]
            full_response += content
            yield content
    
    return

def run_ai_batch(prompts: list, max_tokens: int = 120, format: str = None) -> list:
    """
    Process multiple prompts efficiently for batch operations.
    """
    responses = []
    for prompt in prompts:
        response = run_ai_optimized(prompt, max_tokens, format)
        responses.append(response)
    return responses

async def run_ai_batch_async(prompts: list, max_tokens: int = 120, format: str = None) -> list:
    """
    Process multiple prompts asynchronously for maximum throughput.
    """
    tasks = [
        run_ai_optimized(prompt, max_tokens, format) 
        for prompt in prompts
    ]
    responses = await asyncio.gather(*tasks)
    return responses

def run_ai_with_retry(
    prompt: str,
    max_tokens: int = 1536,
    format: str = None,
    max_retries: int = 1,
) -> str:
    """
    Run AI inference with automatic retry on empty or failed responses.

    On each attempt the full ``run_ai_optimized`` call is made.  If the
    model returns an empty string (or raises an exception) the call is
    retried up to *max_retries* additional times.

    Parameters
    ----------
    prompt      : The fully-built prompt string.
    max_tokens  : Maximum tokens to generate (default 200 – slightly higher
                  than the base optimised value to accommodate JSON overhead).
    format      : Ollama format hint – ``"json"`` enforces JSON mode.
    max_retries : Number of *extra* attempts after the first one (default 1,
                  so the function tries at most twice).

    Returns
    -------
    The raw string returned by the model, or an empty string when every
    attempt fails.  Callers are responsible for validating / parsing the
    returned string.
    """
    last_response: str = ""

    for attempt in range(max_retries + 1):
        try:
            response = run_ai_optimized(prompt, max_tokens=max_tokens, format=format)

            if response and response.strip():
                if attempt > 0:
                    logger.info("run_ai_with_retry: succeeded on attempt %d", attempt + 1)
                return response

            logger.warning(
                "run_ai_with_retry: attempt %d returned empty response – retrying…",
                attempt + 1,
            )
            last_response = response or ""

        except Exception as exc:
            logger.warning(
                "run_ai_with_retry: attempt %d raised %s: %s – retrying…",
                attempt + 1, type(exc).__name__, exc,
            )
            last_response = ""

    logger.error(
        "run_ai_with_retry: all %d attempt(s) failed – returning last response",
        max_retries + 1,
    )
    return last_response


# ── Backward compatibility ─────────────────────────────────────────────────────

def run_ai(prompt: str, format: str = None):
    """Legacy function - now uses optimized settings"""
    return run_ai_optimized(prompt, max_tokens=120, format=format)

async def run_ai_async(prompt: str, format: str = None):
    """Legacy async function - now uses optimized settings"""
    return await run_ai_streaming(prompt, max_tokens=120, format=format)
