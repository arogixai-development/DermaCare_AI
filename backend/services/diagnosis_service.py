"""
Diagnosis Service – DermaCare AI
==================================
Generates dermatology diagnoses via the LLM pipeline and guarantees that the
frontend always receives a structurally valid JSON response.

Reliability pipeline (per request)
-----------------------------------
1. Check in-memory cache (skip LLM entirely on a cache hit).
2. Build prompt with strict JSON-only instructions.
3. Call ``run_ai_with_retry`` – retries once automatically on empty output.
4. Validate the raw LLM string with ``parse_and_validate``:
     a. Extract JSON from surrounding prose / markdown fences.
     b. ``json.loads()`` – hard parse check.
     c. Schema validation – coerce or fill missing fields.
5. If validation fails → retry the LLM call one final time.
6. If the retry also fails → return ``DIAGNOSIS_FALLBACK`` (guaranteed valid).
7. Only cache *successful* (non-fallback) results.
"""

import json
import hashlib
import logging
import time

from typing import Any, AsyncGenerator, Dict, Optional

from backend.ai_engine.ollama_client import run_ai_with_retry, run_ai_optimized, run_ai_streaming
from backend.ai_engine.json_validator import (
    parse_and_validate,
    DIAGNOSIS_SCHEMA,
    DIAGNOSIS_FALLBACK,
)
from backend.prompts.diagnosis_prompt import build_diagnosis_prompt_optimized

logger = logging.getLogger("DermaCare_AI.diagnosis_service")

# ── In-memory response cache (for get_last_diagnosis / streaming) ────────────
_last_diagnosis_cache: Dict[str, Any] = {}


def _get_case_hash(case_data: dict) -> str:
    """Generate a stable hash from the essential clinical fields using SHA-256."""
    essential = {
        "complaint":         case_data.get("complaint", ""),
        "lesion":            case_data.get("lesion", ""),
        "symptoms":          case_data.get("symptoms", ""),
        "patient_age":       case_data.get("patient_age", ""),
        "geographic_region": case_data.get("geographic_region", ""),
    }
    return hashlib.sha256(json.dumps(essential, sort_keys=True).encode()).hexdigest()


def _validate_llm_output(raw: str) -> tuple[Dict[str, Any], bool]:
    """
    Thin wrapper that calls ``parse_and_validate`` with the diagnosis schema.

    Returns
    -------
    (result_dict, success_bool)
    """
    return parse_and_validate(
        raw_str=raw,
        schema=DIAGNOSIS_SCHEMA,
        fallback=DIAGNOSIS_FALLBACK,
        context="diagnosis",
    )


# ── Public API ────────────────────────────────────────────────────────────────

# Internal dictionary for manual caching to avoid storing fallbacks
_diagnosis_response_cache: Dict[str, Any] = {}

def get_diagnosis(complaint: str, lesion: str, symptoms: str, age: int, region: str, phototype: str = "Type III") -> dict:
    """
    Internal function to process diagnosis with manual caching of successful results.
    """
    case_data = {
        "complaint": complaint,
        "lesion": lesion,
        "symptoms": symptoms,
        "patient_age": age,
        "geographic_region": region,
        "skin_phototype": phototype
    }
    
    case_hash = _get_case_hash(case_data)
    if case_hash in _diagnosis_response_cache:
        logger.info("diagnosis: cache hit for %s", case_hash)
        return dict(_diagnosis_response_cache[case_hash])

    prompt = build_diagnosis_prompt_optimized(case_data)

    start_time = time.time()

    raw = run_ai_with_retry(prompt, max_tokens=2000, format="json", max_retries=1)
    result, success = _validate_llm_output(raw)

    if not success:
        logger.warning(
            "diagnosis: first attempt produced invalid JSON – making one more LLM call"
        )
        raw2 = run_ai_with_retry(prompt, max_tokens=2000, format="json", max_retries=0)
        result, success = _validate_llm_output(raw2)

        if not success:
            logger.error(
                "diagnosis: both attempts failed – returning DIAGNOSIS_FALLBACK"
            )
            return dict(DIAGNOSIS_FALLBACK)

    result["_inference_time"] = f"{time.time() - start_time:.2f}s"
    result["_model"] = "phi3"
    
    _diagnosis_response_cache[case_hash] = result
    
    return result



def generate_diagnosis(case_data: dict) -> dict:
    """
    Synchronous diagnosis generation with full reliability pipeline.
    Uses get_diagnosis (cached) to avoid redundant AI calls.
    """
    complaint = case_data.get("complaint", "")
    lesion = case_data.get("lesion", "")
    symptoms = case_data.get("symptoms", "")
    age = int(case_data.get("patient_age", 0))
    region = case_data.get("geographic_region", "")
    phototype = case_data.get("skin_phototype", "Type III")

    result = dict(get_diagnosis(complaint, lesion, symptoms, age, region, phototype))
    
    result["complaint"] = complaint
    result["lesion"] = lesion
    result["symptoms"] = symptoms
    result["patient_age"] = age
    result["geographic_region"] = region
    result["skin_phototype"] = phototype
    
    case_hash = _get_case_hash(case_data)
    _last_diagnosis_cache[case_hash] = result
    
    logger.info("diagnosis: generated/retrieved for %s", complaint[:30])
    return result


async def generate_diagnosis_async(case_data: dict) -> dict:
    """
    Async-compatible diagnosis generation (runs the sync pipeline in-thread).

    FastAPI's async endpoints call this; the sync LLM call is acceptable here
    since Ollama's Python client is blocking.  For true async, swap in an
    httpx-based Ollama client.
    """
    # asyncio.to_thread would be preferred in Python 3.9+; for broad compat
    # we call the sync function directly (FastAPI runs it in a thread pool
    # when the *route* is async).
    return generate_diagnosis(case_data)


async def generate_diagnosis_streaming(case_data: dict) -> AsyncGenerator[str, None]:
    """
    Stream raw LLM chunks for real-time UI feedback.

    The full accumulated response is validated and cached once streaming
    completes.  If validation fails the cache is NOT updated (next non-stream
    request will retry).
    """
    case_hash = _get_case_hash(case_data)

    # ── Cache hit – yield the whole result at once ─────────────────────────
    if case_hash in _last_diagnosis_cache:
        cached = dict(_last_diagnosis_cache[case_hash])
        cached["_cached"] = True
        yield json.dumps(cached)
        return

    prompt = build_diagnosis_prompt_optimized(case_data)

    # ── Stream chunks ──────────────────────────────────────────────────────
    full_response = ""
    async for chunk in run_ai_streaming(prompt, max_tokens=1536, format="json"):
        full_response += chunk
        yield chunk

    # ── Validate accumulated response ──────────────────────────────────────
    result, success = _validate_llm_output(full_response)
    if success:
        _last_diagnosis_cache[case_hash] = result
    else:
        logger.warning(
            "diagnosis streaming: accumulated response was invalid JSON – "
            "cache NOT updated; next non-stream request will retry"
        )


# ── Cache utilities ───────────────────────────────────────────────────────────

def get_last_diagnosis(case_data: Optional[dict] = None) -> Any:
    """
    Return the cached diagnosis for *case_data*, or the latest entry when
    *case_data* is ``None``.
    """
    if case_data:
        return _last_diagnosis_cache.get(_get_case_hash(case_data))
    # Return the most-recently inserted value (Python 3.7+ dict preserves order)
    return next(reversed(_last_diagnosis_cache.values()), None)


def clear_cache() -> None:
    """Clear the entire in-memory diagnosis cache."""
    _last_diagnosis_cache.clear()


def get_cache_stats() -> dict:
    """Return current cache performance statistics."""
    return {
        "cache_size":       len(_last_diagnosis_cache),
        "cache_keys":       list(_last_diagnosis_cache.keys()),
        "model_used":       "llama3:8b",
        "optimization_level": "high",
    }
