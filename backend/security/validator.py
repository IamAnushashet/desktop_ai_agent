"""Security validation and rate limiting for remote desktop commands."""

import time
from typing import List, Optional, Set
from backend.utils.logger import logger

# Whitelist of allowed single keys for keyboard emulation
ALLOWED_KEYS: Set[str] = {
    # Alphanumeric
    *(chr(c) for c in range(ord('a'), ord('z') + 1)),
    *(chr(c) for c in range(ord('A'), ord('Z') + 1)),
    *(str(i) for i in range(10)),
    # Navigation and edit
    "enter", "return", "backspace", "delete", "tab", "escape", "esc", "space",
    "up", "down", "left", "right", "home", "end", "pageup", "pagedown", "insert",
    # Modifiers
    "shift", "ctrl", "control", "alt", "win", "windows", "capslock",
    # Function keys
    *(f"f{i}" for i in range(1, 13)),
    # Punctuation & symbols
    "!", "@", "#", "$", "%", "^", "&", "*", "(", ")", "-", "_", "=", "+",
    "[", "]", "{", "}", "\\", "|", ";", ":", "'", '"', ",", ".", "<", ">", "/", "?", "`", "~",
}

# Supported mouse buttons
ALLOWED_MOUSE_BUTTONS: Set[str] = {"left", "right", "middle"}

# Supported window actions
ALLOWED_WINDOW_ACTIONS: Set[str] = {"minimize", "maximize", "restore"}

# Maximum payload size in bytes (64 KB)
MAX_MESSAGE_BYTES: int = 64 * 1024


def validate_coordinate(val: float, name: str = "coordinate") -> bool:
    """Ensure normalized coordinates are within [0.0, 1.0]."""
    if not isinstance(val, (int, float)):
        return False
    if val < 0.0 or val > 1.0:
        return False
    return True


def validate_delta(delta: float) -> bool:
    """Ensure scroll delta is within reasonable bounds."""
    if not isinstance(delta, (int, float)):
        return False
    if delta < -1000.0 or delta > 1000.0:
        return False
    return True


def validate_key(key: str) -> bool:
    """Check if key is in the allowed keys whitelist."""
    if not isinstance(key, str):
        return False
    normalized = key.strip().lower()
    return normalized in ALLOWED_KEYS or key in ALLOWED_KEYS


def validate_hotkey(keys: List[str]) -> bool:
    """Check if all keys in hotkey combo are safe and allowed."""
    if not isinstance(keys, list) or len(keys) == 0 or len(keys) > 5:
        return False
    return all(validate_key(k) for k in keys)


def validate_button(button: str) -> bool:
    """Check if mouse button is valid."""
    if not isinstance(button, str):
        return False
    return button.strip().lower() in ALLOWED_MOUSE_BUTTONS


class RateLimiter:
    """Per-session rate limiter to prevent message flooding."""

    def __init__(self, max_per_second: int = 120):
        self.max_per_second = max_per_second
        self.events: List[float] = []

    def allow(self) -> bool:
        now = time.time()
        # Remove events older than 1 second
        self.events = [t for t in self.events if now - t < 1.0]
        if len(self.events) >= self.max_per_second:
            return False
        self.events.append(now)
        return True
