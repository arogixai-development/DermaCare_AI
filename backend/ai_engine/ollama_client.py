"""
Ollama Client Module - DermaCare AI
====================================
AI Engine with:
- Monte Carlo Dropout for uncertainty estimation
- Confidence Interval calculation
- Variance Score reporting
"""

import ollama
import asyncio
import hashlib
import json
import logging
import statistics
import threading
import urllib.error
import urllib.request
from typing import Optional, Dict, Any, List, Tuple
from functools import lru_cache
from backend.config import get_model_name, get_reliability_config

logger = logging.getLogger("DermaCare_AI.ollama_client")

GROQ_COST_PER_1K_TOKENS_USD = 0.0018
_GROQ_INIT_LOGGED = False
_GROQ_MISSING_LOGGED = False

class OllamaConnectionError(Exception):
    """Raised when Ollama is not available or not running."""
    pass


class OllamaOverloadError(OllamaConnectionError):
    """Raised when concurrency guard rejects due to high load."""
    pass


class OllamaTimeoutError(OllamaConnectionError):
    """Raised when AI call exceeds the configured timeout."""
    pass


_LLM_CONCURRENCY_LIMIT = 6
_LLM_ASYNC_SEMAPHORE = asyncio.Semaphore(_LLM_CONCURRENCY_LIMIT)
_LLM_SYNC_SEMAPHORE = threading.BoundedSemaphore(_LLM_CONCURRENCY_LIMIT)
_LLM_ACTIVE_CALLS = 0
_LLM_ACTIVE_LOCK = threading.Lock()

class UncertaintyEstimator:
    """
    Implements Monte Carlo Dropout-style uncertainty estimation.
    Runs multiple inferences and calculates variance/confidence intervals.
    """
    
    DEFAULT_ITERATIONS = 5
    MIN_ITERATIONS = 3
    MAX_ITERATIONS = 10
    
    def __init__(self, iterations: int = DEFAULT_ITERATIONS):
        self.iterations = max(self.MIN_ITERATIONS, min(iterations, self.MAX_ITERATIONS))
    
    async def run_monte_carlo(
        self, 
        prompt: str, 
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Run multiple inferences and calculate uncertainty metrics.
        
        Returns:
            Dict with:
            - results: List of all inference results
            - variance_score: Float (0.0-1.0) - higher = more uncertain
            - confidence_interval: [lower%, upper%]
            - consensus_score: Float (0.0-1.0) - agreement between runs
            - uncertainty_flag: Boolean - True if variance is high
        """
        results = []
        raw_responses = []
        
        temperature_variations = [
            0.2, 0.3, 0.4, 0.35, 0.25
        ][:self.iterations]
        
        for i in range(self.iterations):
            try:
                temp = temperature_variations[i % len(temperature_variations)]
                
                response = await self._single_inference(prompt, max_tokens, temperature=temp)
                raw_responses.append(response)
                
                try:
                    parsed = json.loads(response)
                    results.append(parsed)
                except json.JSONDecodeError:
                    results.append({"raw": response, "parse_error": True})
                    
            except Exception as e:
                logger.warning(f"Monte Carlo iteration {i} failed: {e}")
                raw_responses.append("")
                results.append({"error": str(e)})
        
        return self._calculate_uncertainty_metrics(results, raw_responses)
    
    async def _single_inference(
        self, 
        prompt: str, 
        max_tokens: int,
        temperature: float = 0.3
    ) -> str:
        """Single inference call with specific temperature."""
        try:
            response = ollama.chat(
                model=get_model_name(),
                messages=[{"role": "user", "content": prompt}],
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "top_k": 40,
                    "num_ctx": 4096,
                },
                format="json" if "json" in prompt.lower() else None
            )
            return response["message"]["content"]
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            raise OllamaConnectionError(str(e))
    
    def _calculate_uncertainty_metrics(
        self, 
        results: List[Dict], 
        raw_responses: List[str]
    ) -> Dict[str, Any]:
        """Calculate variance, confidence intervals, and uncertainty flags."""
        
        valid_results = [r for r in results if "error" not in r and "parse_error" not in r]
        
        if not valid_results:
            return {
                "results": results,
                "variance_score": 1.0,
                "confidence_interval": [0, 100],
                "consensus_score": 0.0,
                "uncertainty_flag": True,
                "uncertainty_reason": "all_inferences_failed"
            }
        
        variance_score = self._calculate_diagnosis_variance(valid_results)
        
        consensus_score = self._calculate_consensus(valid_results)
        
        confidence_interval = self._calculate_confidence_interval(valid_results, consensus_score)
        
        uncertainty_threshold = 0.3
        uncertainty_flag = variance_score > uncertainty_threshold or consensus_score < 0.5
        
        discordant_indicators = self._find_discordant_indicators(valid_results)
        
        return {
            "results": results,
            "variance_score": round(variance_score, 3),
            "confidence_interval": confidence_interval,
            "consensus_score": round(consensus_score, 3),
            "uncertainty_flag": uncertainty_flag,
            "discordant_indicators": discordant_indicators,
            "iterations_completed": len(valid_results),
            "iterations_total": self.iterations,
            "uncertainty_reduction_suggestions": self._get_uncertainty_reduction_suggestions(
                variance_score, consensus_score, discordant_indicators
            )
        }
    
    def _calculate_diagnosis_variance(self, results: List[Dict]) -> float:
        """
        Calculate variance in diagnoses across runs.
        Uses Jaccard similarity on condition names.
        """
        if len(results) < 2:
            return 0.0
        
        all_conditions = set()
        for r in results:
            if "differential_diagnosis" in r:
                for dx in r["differential_diagnosis"]:
                    if "condition" in dx:
                        all_conditions.add(dx["condition"].lower())
        
        similarities = []
        for i, r1 in enumerate(results):
            for r2 in results[i+1:]:
                conditions1 = set()
                conditions2 = set()
                
                if "differential_diagnosis" in r1:
                    conditions1 = {d.get("condition", "").lower() for d in r1["differential_diagnosis"]}
                if "differential_diagnosis" in r2:
                    conditions2 = {d.get("condition", "").lower() for d in r2["differential_diagnosis"]}
                
                if conditions1 or conditions2:
                    intersection = len(conditions1 & conditions2)
                    union = len(conditions1 | conditions2)
                    jaccard = intersection / union if union > 0 else 0
                    similarities.append(jaccard)
        
        if not similarities:
            return 0.5
        
        avg_similarity = statistics.mean(similarities)
        variance = 1.0 - avg_similarity
        
        return min(max(variance, 0.0), 1.0)
    
    def _calculate_consensus(self, results: List[Dict]) -> float:
        """Calculate how much the runs agree on the top diagnosis."""
        if not results:
            return 0.0
        
        top_conditions = []
        for r in results:
            if "differential_diagnosis" in r and r["differential_diagnosis"]:
                top = r["differential_diagnosis"][0].get("condition", "").lower()
                top_conditions.append(top)
        
        if not top_conditions:
            return 0.0
        
        most_common = statistics.mode(top_conditions)
        agreement_count = top_conditions.count(most_common)
        
        return agreement_count / len(top_conditions)
    
    def _calculate_confidence_interval(
        self, 
        results: List[Dict], 
        consensus_score: float
    ) -> List[float]:
        """
        Calculate confidence interval based on consensus and variance.
        Returns [lower_bound, upper_bound] percentages.
        """
        base_confidence = consensus_score * 100
        
        prob_ranges = []
        for r in results:
            if "differential_diagnosis" in r:
                for dx in r["differential_diagnosis"]:
                    prob_str = dx.get("probability", "0%")
                    try:
                        prob = float(prob_str.replace("%", ""))
                        prob_ranges.append(prob)
                    except:
                        pass
        
        if prob_ranges:
            variance_factor = statistics.stdev(prob_ranges) / 100 if len(prob_ranges) > 1 else 0
        else:
            variance_factor = 0
        
        margin = 10 + (variance_factor * 20)
        
        lower = max(0, base_confidence - margin)
        upper = min(100, base_confidence + margin)
        
        if consensus_score > 0.8:
            lower = max(0, base_confidence - 10)
            upper = min(100, base_confidence + 15)
        elif consensus_score < 0.5:
            lower = max(0, base_confidence - 20)
            upper = min(100, base_confidence + 10)
        
        return [round(lower, 1), round(upper, 1)]
    
    def _find_discordant_indicators(self, results: List[Dict]) -> List[str]:
        """Find indicators where runs disagreed."""
        discordant = []
        
        confidence_levels = []
        for r in results:
            if "uncertainty_flags" in r:
                conf = r["uncertainty_flags"].get("overall_confidence", "UNKNOWN")
                confidence_levels.append(conf)
        
        if len(set(confidence_levels)) > 1:
            discordant.append(f"Confidence level varied: {set(confidence_levels)}")
        
        triage_levels = []
        for r in results:
            if "triage" in r:
                triage_levels.append(r["triage"])
        
        if len(set(triage_levels)) > 1:
            discordant.append(f"Triage level disagreement: {set(triage_levels)}")
        
        return discordant
    
    def _get_uncertainty_reduction_suggestions(
        self, 
        variance: float, 
        consensus: float,
        discordant: List[str]
    ) -> List[str]:
        """Suggest ways to reduce uncertainty."""
        suggestions = []
        
        if variance > 0.5:
            suggestions.append("High variance detected - consider additional imaging or biopsy")
        if consensus < 0.5:
            suggestions.append("Low consensus - results should be reviewed by specialist")
        if not discordant:
            suggestions.append("Consider dermoscopy for clearer visual assessment")
        
        suggestions.append("Obtain detailed history and previous records")
        suggestions.append("Request higher quality images with better lighting")
        
        return suggestions


def check_ollama_connection() -> Dict[str, Any]:
    """
    Check if Ollama is running and accessible.
    Returns status info with connection details.
    """
    try:
        models = ollama.list()
        
        # Check if any model is loaded (indicates GPU usage)
        gpu_enabled = False
        try:
            # Try to get show info for first model
            if models.get("models"):
                model_name = models["models"][0].get("name")
                model_info = ollama.show(model_name)
                # Check model info for GPU indicators
                if model_info:
                    gpu_enabled = True
        except Exception:
            pass
        
        return {
            "connected": True,
            "models": [m.get("name") for m in models.get("models", [])],
            "error": None,
            "gpu_available": gpu_enabled
        }
    except Exception as e:
        error_msg = str(e)
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            return {
                "connected": False,
                "models": [],
                "error": "Ollama is not running. Please start Ollama: `ollama serve`",
                "gpu_available": False
            }
        return {
            "connected": False,
            "models": [],
            "error": f"Ollama error: {error_msg}",
            "gpu_available": False
        }


@lru_cache(maxsize=128)
def _get_prompt_hash(prompt: str) -> str:
    """Generate a hash for the prompt to use as cache key"""
    return hashlib.sha256(prompt.encode()).hexdigest()


def run_ai_optimized(prompt: str, max_tokens: int = 2000, format: str = None) -> str:
    """
    Run AI inference with optimized parameters for phi3.
    Forces JSON mode when requested for reliable parsing.
    """
    status = check_ollama_connection()
    if not status["connected"]:
        raise OllamaConnectionError(status["error"])
    
    options = {
        "num_predict": min(max_tokens, 2048),
        "temperature": 0.2,  # Lower temperature for more consistent JSON
        "top_p": 0.85,
        "top_k": 40,
        "repeat_penalty": 1.05,
        "num_ctx": 2048,
        "mirostat": 0,
    }
    
    kwargs = {
        "model": get_model_name(), 
        "messages": [{"role": "user", "content": prompt}], 
        "options": options
    }
    
    # CRITICAL: Always force JSON format when requested
    if format == "json":
        kwargs["format"] = "json"
        logger.info(f"[OLLAMA] Requesting JSON format with model: {get_model_name()}")
    
    try:
        response = ollama.chat(**kwargs)
        content = response["message"]["content"]
        
        # Debug: Log response start
        if content:
            logger.info(f"[OLLAMA] Response received ({len(content)} chars), starts with: {content[:50]}...")
        else:
            logger.warning("[OLLAMA] Empty response received")
            
        return content
    except Exception as e:
        logger.error(f"Ollama chat error: {e}")
        raise OllamaConnectionError(f"AI request failed: {str(e)}")


async def run_ai_with_uncertainty(
    prompt: str, 
    max_tokens: int = 2000,
    monte_carlo_iterations: int = 5
) -> Tuple[str, Dict[str, Any]]:
    """
    Run AI inference with Monte Carlo uncertainty estimation.
    
    Returns:
        (best_response, uncertainty_metrics)
    """
    estimator = UncertaintyEstimator(iterations=monte_carlo_iterations)
    metrics = await estimator.run_monte_carlo(prompt, max_tokens)
    
    valid_results = [r for r in metrics["results"] if "error" not in r and "parse_error" not in r]
    
    if not valid_results:
        return "", metrics
    
    consensus_idx = 0
    best_consensus = 0
    
    for i, r in enumerate(valid_results):
        prob_str = ""
        if "differential_diagnosis" in r and r["differential_diagnosis"]:
            prob_str = r["differential_diagnosis"][0].get("probability", "0%")
        
        try:
            prob = float(prob_str.replace("%", ""))
            if prob > best_consensus:
                best_consensus = prob
                consensus_idx = i
        except:
            pass
    
    best_response = json.dumps(valid_results[consensus_idx])
    
    return best_response, metrics


async def run_ai_streaming(prompt: str, max_tokens: int = 120, format: str = None):
    """
    Stream AI responses for real-time user feedback.
    """
    stream = ollama.chat(
        model=get_model_name(),
        messages=[{"role": "user", "content": prompt}],
        format=format if format else None,
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
    """Process multiple prompts for batch operations."""
    responses = []
    for prompt in prompts:
        response = run_ai_optimized(prompt, max_tokens, format)
        responses.append(response)
    return responses


def run_ai_with_retry(
    prompt: str,
    max_tokens: int = 2000,
    format: str = None,
    max_retries: int = 1,
    timeout_seconds: Optional[float] = None,
    overload_wait_seconds: float = 0.2,
) -> str:
    """
    Run AI inference with automatic retry on empty or failed responses.
    """
    global _LLM_ACTIVE_CALLS
    with _LLM_ACTIVE_LOCK:
        if _LLM_ACTIVE_CALLS >= _LLM_CONCURRENCY_LIMIT:
            raise OllamaOverloadError("System under high load, please retry")
    acquired = _LLM_SYNC_SEMAPHORE.acquire(timeout=max(0.01, overload_wait_seconds))
    if not acquired:
        raise OllamaOverloadError("System under high load, please retry")
    try:
        with _LLM_ACTIVE_LOCK:
            _LLM_ACTIVE_CALLS += 1
        last_response = ""

        for attempt in range(max_retries + 1):
            try:
                if timeout_seconds and timeout_seconds > 0:
                    response = asyncio.run(
                        asyncio.wait_for(
                            asyncio.to_thread(
                                run_ai_optimized, prompt, max_tokens, format
                            ),
                            timeout=float(timeout_seconds),
                        )
                    )
                else:
                    response = run_ai_optimized(prompt, max_tokens=max_tokens, format=format)

                if response and response.strip():
                    if attempt > 0:
                        logger.info("run_ai_with_retry: succeeded on attempt %d", attempt + 1)
                    return response

                logger.warning(
                    "run_ai_with_retry: attempt %d returned empty response - retrying",
                    attempt + 1,
                )
                last_response = response or ""

            except TimeoutError:
                raise OllamaTimeoutError("AI request timed out")
            except Exception as exc:
                logger.warning(
                    "run_ai_with_retry: attempt %d raised %s: %s - retrying",
                    attempt + 1, type(exc).__name__, exc,
                )
                last_response = ""

        logger.error(
            "run_ai_with_retry: all %d attempt(s) failed - returning last response",
            max_retries + 1,
        )
        return last_response
    finally:
        with _LLM_ACTIVE_LOCK:
            _LLM_ACTIVE_CALLS = max(0, _LLM_ACTIVE_CALLS - 1)
        _LLM_SYNC_SEMAPHORE.release()


async def run_ai_with_retry_async(
    prompt: str,
    max_tokens: int = 2000,
    format: str = None,
    max_retries: int = 1,
    timeout_seconds: Optional[float] = None,
    overload_wait_seconds: float = 0.2,
) -> str:
    """
    Async variant with asyncio semaphore-based concurrency guard.
    """
    global _LLM_ACTIVE_CALLS
    with _LLM_ACTIVE_LOCK:
        if _LLM_ACTIVE_CALLS >= _LLM_CONCURRENCY_LIMIT:
            raise OllamaOverloadError("System under high load, please retry")
    try:
        await asyncio.wait_for(_LLM_ASYNC_SEMAPHORE.acquire(), timeout=max(0.01, overload_wait_seconds))
    except TimeoutError:
        raise OllamaOverloadError("System under high load, please retry")

    try:
        with _LLM_ACTIVE_LOCK:
            _LLM_ACTIVE_CALLS += 1
        last_response = ""
        for attempt in range(max_retries + 1):
            try:
                call = asyncio.to_thread(run_ai_optimized, prompt, max_tokens, format)
                response = await asyncio.wait_for(call, timeout=float(timeout_seconds)) if timeout_seconds else await call
                if response and response.strip():
                    return response
                last_response = response or ""
            except TimeoutError:
                raise OllamaTimeoutError("AI request timed out")
            except Exception as exc:
                logger.warning(
                    "run_ai_with_retry_async: attempt %d raised %s: %s",
                    attempt + 1,
                    type(exc).__name__,
                    exc,
                )
                last_response = ""
        return last_response
    finally:
        with _LLM_ACTIVE_LOCK:
            _LLM_ACTIVE_CALLS = max(0, _LLM_ACTIVE_CALLS - 1)
        _LLM_ASYNC_SEMAPHORE.release()


def estimate_tokens(text: str) -> int:
    """Rough token estimate for cost accounting."""
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def estimate_groq_cost_usd(prompt: str, completion: str) -> float:
    tokens = estimate_tokens(prompt) + estimate_tokens(completion)
    return round((tokens / 1000.0) * GROQ_COST_PER_1K_TOKENS_USD, 6)


def run_groq_fallback(
    prompt: str,
    max_tokens: int = 1024,
    model_override: Optional[str] = None,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    """
    Contingency fallback using Groq OpenAI-compatible API.
    Returns structured metadata for observability.
    """
    cfg = get_reliability_config()
    api_key = cfg.get("groq_api_key", "")
    model = model_override or cfg.get("groq_model", "llama3-70b-8192")
    global _GROQ_INIT_LOGGED, _GROQ_MISSING_LOGGED
    if not api_key:
        if not _GROQ_MISSING_LOGGED:
            logger.warning("GROQ_API_KEY is missing. Groq fallback is disabled.")
            _GROQ_MISSING_LOGGED = True
        return {
            "ok": False,
            "provider": "groq",
            "error": "groq_api_key_missing",
            "content": "",
            "estimated_cost_usd": 0.0,
        }
    if not _GROQ_INIT_LOGGED:
        logger.info("Groq fallback initialized successfully")
        _GROQ_INIT_LOGGED = True

    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": min(max_tokens, 1024),
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
            content = (
                data.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            return {
                "ok": bool(content and content.strip()),
                "provider": "groq",
                "error": None,
                "content": content or "",
                "model": model,
                "estimated_cost_usd": estimate_groq_cost_usd(prompt, content or ""),
            }
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")[:400]
        except Exception:
            body = str(exc)
        logger.warning("Groq fallback HTTP error: %s", body)
        return {
            "ok": False,
            "provider": "groq",
            "error": f"http_{exc.code}",
            "content": "",
            "estimated_cost_usd": 0.0,
        }
    except Exception as exc:
        logger.warning("Groq fallback error: %s", exc)
        return {
            "ok": False,
            "provider": "groq",
            "error": str(exc),
            "content": "",
            "estimated_cost_usd": 0.0,
        }


def run_ai(prompt: str, format: str = None):
    """Legacy function - now uses optimized settings"""
    return run_ai_optimized(prompt, max_tokens=120, format=format)


async def run_ai_async(prompt: str, format: str = None):
    """Legacy async function"""
    full_response = ""
    async for chunk in run_ai_streaming(prompt, max_tokens=120, format=format):
        full_response += chunk
    return full_response
