"""Keyboard control tools wrapping KeyboardController."""

from typing import List, Union
from langchain_core.tools import tool
from backend.control.keyboard import keyboard_controller
from backend.utils.logger import logger


@tool
def type_text(text: str, press_enter: bool = False) -> str:
    """
    Type out text strings into the currently focused window input field.
    
    Args:
        text: The exact text string to type into the active desktop application.
        press_enter: If True, automatically presses the Enter key after typing text. Default is False.
    """
    success = keyboard_controller.write(text)
    if success:
        logger.info(f"[TOOL] Typed text: '{text}' (press_enter={press_enter})")
        if press_enter:
            keyboard_controller.press("enter")
        return f"Successfully typed '{text}'" + (" and pressed Enter" if press_enter else "")
    return f"Failed to type text: '{text}'"


@tool
def press_key(key: str) -> str:
    """
    Press and release a single key on the Windows keyboard.
    
    Args:
        key: The key name to press (e.g. 'enter', 'tab', 'escape', 'backspace', 'space', 'down', 'up', 'left', 'right', 'win').
    """
    success = keyboard_controller.press(key)
    if success:
        logger.info(f"[TOOL] Pressed key: '{key}'")
        return f"Pressed key '{key}'"
    return f"Failed to press key '{key}'"


@tool
def press_hotkey(keys: List[str]) -> str:
    """
    Press a combination of keys simultaneously (shortcut / hotkey).
    
    Args:
        keys: List of key strings to press together (e.g. ['ctrl', 'c'], ['alt', 'tab'], ['win', 'd'], ['ctrl', 't'], ['alt', 'f4']).
    """
    from backend.control.window import window_controller

    norm_keys = [k.lower().strip() for k in keys if isinstance(k, str)]
    if ("alt" in norm_keys and "f4" in norm_keys) or ("alt" in norm_keys and "f4" in norm_keys):
        logger.info("[TOOL press_hotkey] Intercepted Alt+F4 close hotkey -> Routing through Global Close Permission Gate")
        return window_controller.close_window()

    success = keyboard_controller.hotkey(keys)
    if success:
        joined_keys = " + ".join(keys)
        logger.info(f"[TOOL] Pressed hotkey: {joined_keys}")
        return f"Pressed hotkey combination ({joined_keys})"
    return f"Failed to press hotkey combination ({keys})"
