"""
Configuration module for DermaCare AI.
Loads settings from environment variables with fallback defaults.
"""
import os
from functools import lru_cache

@lru_cache(maxsize=1)
def get_config() -> dict:
    """
    Get configuration from environment variables with defaults.
    """
    return {
        # Ollama settings
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "phi3"),
        
        # API settings
        "api_host": os.getenv("API_HOST", "0.0.0.0"),
        "api_port": int(os.getenv("API_PORT", "8000")),
        
        # CORS settings (comma-separated origins)
        "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
        
        # Logging
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        
        # Cache settings
        "cache_max_size": int(os.getenv("CACHE_MAX_SIZE", "128")),
        
        # Inference settings
        "max_tokens": int(os.getenv("MAX_TOKENS", "1024")),
        "temperature": float(os.getenv("TEMPERATURE", "0.3")),

        # Reliability pipeline flags
        "reliability_pipeline_v2": os.getenv("RELIABILITY_PIPELINE_V2", "true").lower() == "true",
        "enable_groq_fallback": os.getenv("ENABLE_GROQ_FALLBACK", "true").lower() == "true",
        "enable_openai_final_contingency": os.getenv("ENABLE_OPENAI_FINAL_CONTINGENCY", "false").lower() == "true",
        "quick_allow_groq_fallback": os.getenv("QUICK_ALLOW_GROQ_FALLBACK", "false").lower() == "true",
        "partial_valid_threshold": float(os.getenv("PARTIAL_VALID_THRESHOLD", "0.5")),
        "low_confidence_escalation_threshold": float(
            os.getenv("LOW_CONFIDENCE_ESCALATION_THRESHOLD", "0.40")
        ),
        "groq_usage_cap_rate": float(os.getenv("GROQ_USAGE_CAP_RATE", "0.10")),
        "quick_retry_limit": int(os.getenv("QUICK_RETRY_LIMIT", "1")),
        "accurate_retry_limit": int(os.getenv("ACCURATE_RETRY_LIMIT", "2")),
        "quick_mode_max_tokens": int(os.getenv("QUICK_MODE_MAX_TOKENS", "384")),
        "accurate_mode_max_tokens": int(os.getenv("ACCURATE_MODE_MAX_TOKENS", "1024")),
        "accurate_time_budget_seconds": int(os.getenv("ACCURATE_TIME_BUDGET_SECONDS", "55")),
        "accurate_final_fallback_timeout_seconds": int(
            os.getenv("ACCURATE_FINAL_FALLBACK_TIMEOUT_SECONDS", "15")
        ),
        "groq_model": os.getenv("GROQ_MODEL", "llama3-70b-8192"),
        "groq_model_cheap": os.getenv("GROQ_MODEL_CHEAP", "llama3-8b-8192"),
        "groq_model_strategy": os.getenv("GROQ_MODEL_STRATEGY", "quality"),  # quality|cost
        "groq_api_key": os.getenv("GROQ_API_KEY", ""),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "price_per_request_usd": float(os.getenv("PRICE_PER_REQUEST_USD", "0.05")),
        "api_default_version": os.getenv("API_DEFAULT_VERSION", "v1"),
    }

def get_model_name() -> str:
    """Get the configured Ollama model name."""
    return get_config()["ollama_model"]

def get_ollama_url() -> str:
    """Get the configured Ollama base URL."""
    return get_config()["ollama_base_url"]


def get_reliability_config() -> dict:
    """Reliability/fallback-specific configuration."""
    config = get_config()
    return {
        "reliability_pipeline_v2": config["reliability_pipeline_v2"],
        "enable_groq_fallback": config["enable_groq_fallback"],
        "enable_openai_final_contingency": config["enable_openai_final_contingency"],
        "quick_allow_groq_fallback": config["quick_allow_groq_fallback"],
        "partial_valid_threshold": config["partial_valid_threshold"],
        "low_confidence_escalation_threshold": config["low_confidence_escalation_threshold"],
        "groq_usage_cap_rate": config["groq_usage_cap_rate"],
        "quick_retry_limit": config["quick_retry_limit"],
        "accurate_retry_limit": config["accurate_retry_limit"],
        "quick_mode_max_tokens": config["quick_mode_max_tokens"],
        "accurate_mode_max_tokens": config["accurate_mode_max_tokens"],
        "accurate_time_budget_seconds": config["accurate_time_budget_seconds"],
        "accurate_final_fallback_timeout_seconds": config["accurate_final_fallback_timeout_seconds"],
        "groq_model": config["groq_model"],
        "groq_model_cheap": config["groq_model_cheap"],
        "groq_model_strategy": config["groq_model_strategy"],
        "groq_api_key": config["groq_api_key"],
        "openai_api_key": config["openai_api_key"],
        "price_per_request_usd": config["price_per_request_usd"],
        "api_default_version": config["api_default_version"],
    }
