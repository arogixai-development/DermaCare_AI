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
    }

def get_model_name() -> str:
    """Get the configured Ollama model name."""
    return get_config()["ollama_model"]

def get_ollama_url() -> str:
    """Get the configured Ollama base URL."""
    return get_config()["ollama_base_url"]
