"""Configuration settings for Desktop AI Agent Remote Control."""

import os
import socket
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file."""
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEVICE_NAME: str = socket.gethostname()
    
    # Screen capture settings
    SCREEN_FPS: int = 20
    SCREEN_QUALITY: int = 60
    SCREEN_MAX_WIDTH: int = 1280
    
    # Security and session settings
    PAIRING_CODE_EXPIRY: int = 300  # seconds
    SESSION_TIMEOUT: int = 1800     # seconds (30 minutes)
    MOUSE_SENSITIVITY: float = 1.0

    # NVIDIA LLM & AI Agent Settings
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    AGENT_MAX_STEPS: int = 10
    AGENT_TOOL_TIMEOUT: int = 15
    AGENT_ENABLE: bool = True

    model_config = SettingsConfigDict(
        env_file=os.path.join(Path(__file__).resolve().parent.parent.parent, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
