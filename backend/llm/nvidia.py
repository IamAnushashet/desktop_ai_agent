"""NVIDIA LLM Provider and Health Checker for Desktop AI Agent."""

import os
from typing import Dict, Any, Tuple
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from backend.config.settings import settings
from backend.utils.logger import logger


def classify_nvidia_error(exc: Exception) -> Tuple[str, str]:
    """
    Classify exceptions from NVIDIA API calls into standardized error types.
    Returns (error_type, user_friendly_message).
    """
    err_str = str(exc).lower()
    
    if "api key" in err_str and ("missing" in err_str or "empty" in err_str):
        return "CONFIGURATION_ERROR", "NVIDIA API key is missing or not configured."
    
    if "401" in err_str or "403" in err_str or "unauthorized" in err_str or "forbidden" in err_str or "invalid api key" in err_str:
        return "AUTHENTICATION_ERROR", "NVIDIA API authentication failed. Check your API key."
    
    if "410" in err_str or "gone" in err_str or "end of life" in err_str or "retired" in err_str:
        return "MODEL_UNAVAILABLE", f"The configured NVIDIA model '{settings.NVIDIA_MODEL}' is retired or unavailable."
    
    if "404" in err_str or "not found" in err_str:
        return "MODEL_UNAVAILABLE", f"The configured NVIDIA model '{settings.NVIDIA_MODEL}' was not found."
    
    if "429" in err_str or "rate limit" in err_str or "too many requests" in err_str:
        return "RATE_LIMITED", "NVIDIA API rate limit exceeded. Please try again shortly."
    
    if "connection" in err_str or "timeout" in err_str or "getaddrinfo" in err_str or "network" in err_str:
        return "NETWORK_ERROR", "Network failure connecting to NVIDIA API endpoint."
    
    return "UNKNOWN_NVIDIA_ERROR", f"NVIDIA API Error: {str(exc)}"


def get_nvidia_llm() -> BaseChatModel:
    """
    Initialize and return an NVIDIA LLM Chat Model instance using LangChain.
    Reads model configuration exclusively from centralized settings.
    """
    api_key = settings.NVIDIA_API_KEY or os.environ.get("NVIDIA_API_KEY", "")
    base_url = (settings.NVIDIA_BASE_URL or os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")).rstrip("/")
    model_name = settings.NVIDIA_MODEL or os.environ.get("NVIDIA_MODEL", "meta/llama-3.2-11b-vision-instruct")

    if not api_key:
        logger.warning("[NVIDIA LLM] NVIDIA_API_KEY is not configured!")

    logger.info(f"[NVIDIA LLM] Initializing ChatOpenAI against NVIDIA base URL '{base_url}' with model '{model_name}'")
    
    return ChatOpenAI(
        model=model_name,
        api_key=api_key if api_key else "missing_key",
        base_url=base_url,
        temperature=0.1,
        max_completion_tokens=1024,
    )


def check_nvidia_health() -> Dict[str, Any]:
    """
    Perform a safe model health check against the configured NVIDIA LLM endpoint.
    Never exposes API keys in the output payload.
    """
    if not settings.NVIDIA_API_KEY:
        return {
            "success": False,
            "status": "failed",
            "error_type": "CONFIGURATION_ERROR",
            "message": "NVIDIA_API_KEY is missing in configuration.",
            "model": settings.NVIDIA_MODEL,
        }

    try:
        llm = get_nvidia_llm()
        # Perform minimal test ping
        response = llm.invoke("Say OK")
        if response and response.content:
            logger.info(f"[NVIDIA HEALTH] Model '{settings.NVIDIA_MODEL}' is READY")
            return {
                "success": True,
                "status": "ready",
                "model": settings.NVIDIA_MODEL,
                "message": f"NVIDIA model '{settings.NVIDIA_MODEL}' is ready.",
            }
        else:
            return {
                "success": False,
                "status": "failed",
                "error_type": "UNKNOWN_NVIDIA_ERROR",
                "message": "Empty response received from NVIDIA model.",
                "model": settings.NVIDIA_MODEL,
            }
    except Exception as e:
        error_type, error_msg = classify_nvidia_error(e)
        logger.error(f"[NVIDIA HEALTH FAILED] [{error_type}]: {error_msg}")
        return {
            "success": False,
            "status": "failed",
            "error_type": error_type,
            "message": error_msg,
            "model": settings.NVIDIA_MODEL,
        }
