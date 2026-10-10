"""Windows keyboard controller for Desktop AI Agent."""

import threading
from typing import List, Dict
import pyautogui
from backend.security.validator import validate_key, validate_hotkey
from backend.utils.logger import logger

# Map mobile key names / aliases to PyAutoGUI key names
KEY_ALIASES: Dict[str, str] = {
    "enter": "enter",
    "return": "enter",
    "backspace": "backspace",
    "delete": "delete",
    "del": "delete",
    "tab": "tab",
    "escape": "escape",
    "esc": "escape",
    "space": "space",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "home": "home",
    "end": "end",
    "pageup": "pageup",
    "pagedown": "pagedown",
    "shift": "shift",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "win": "win",
    "windows": "win",
    "capslock": "capslock",
}


class KeyboardController:
    """Provides safe keyboard control and shortcuts on Windows."""

    def __init__(self):
        self._lock = threading.Lock()

    def _normalize_key(self, key: str) -> str:
        """Map key to canonical PyAutoGUI key name."""
        k = key.strip().lower()
        return KEY_ALIASES.get(k, key)

    def press(self, key: str) -> bool:
        """Press and release a single key."""
        if not validate_key(key):
            logger.warning(f"Rejected unvalidated key input: {key}")
            return False

        mapped = self._normalize_key(key)
        try:
            with self._lock:
                pyautogui.press(mapped)
            return True
        except Exception as e:
            logger.error(f"Failed to press key: {e}")
            return False

    def hotkey(self, keys: List[str]) -> bool:
        """Execute a key combination (e.g. ['ctrl', 'c'], ['alt', 'tab'], ['win', 'd'])."""
        if not validate_hotkey(keys):
            logger.warning("Rejected unvalidated hotkey combination")
            return False

        mapped_keys = [self._normalize_key(k) for k in keys]
        try:
            with self._lock:
                pyautogui.hotkey(*mapped_keys)
            return True
        except Exception as e:
            logger.error(f"Failed to execute hotkey: {e}")
            return False

    def write(self, text: str) -> bool:
        """Safely type text into the active Windows application."""
        if not isinstance(text, str):
            return False

        # Limit text length per message to prevent buffer overflow attacks
        if len(text) > 2000:
            logger.warning("Rejected oversized text typing request")
            return False

        try:
            with self._lock:
                pyautogui.write(text, interval=0.005)
            return True
        except Exception as e:
            logger.error(f"Failed to write text: {e}")
            return False

    def press_key(self, key: str) -> bool:
        """Alias for press(key)."""
        return self.press(key)

    def press_hotkey(self, *keys) -> bool:
        """Alias for hotkey(keys)."""
        if len(keys) == 1 and isinstance(keys[0], (list, tuple)):
            return self.hotkey(list(keys[0]))
        return self.hotkey(list(keys))

    def type_text(self, text: str, interval: float = 0.005) -> bool:
        """Alias for write(text)."""
        return self.write(text)


# Shared keyboard controller instance
keyboard_controller = KeyboardController()
