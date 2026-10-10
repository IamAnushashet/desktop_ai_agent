"""Centralized logging for Desktop AI Agent Remote Control."""

import logging
import os
import sys
from pathlib import Path

# Ensure logs directory exists
LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "remote.log"

logger = logging.getLogger("desktop_remote")
logger.setLevel(logging.INFO)

# Avoid duplicate handlers if reloaded
if not logger.handlers:
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)


def sanitize_message(data: dict) -> dict:
    """Sanitize data to prevent leaking tokens, passwords, or keystrokes."""
    sanitized = {}
    for k, v in data.items():
        if k in ("token", "session_token", "password", "code"):
            sanitized[k] = "***REDACTED***"
        elif k in ("key", "text", "keys") and len(str(v)) > 0:
            sanitized[k] = "[KEY_INPUT]"
        else:
            sanitized[k] = v
    return sanitized
