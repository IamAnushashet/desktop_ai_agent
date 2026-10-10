"""Mouse control tools wrapping MouseController."""

from typing import Optional
from langchain_core.tools import tool
from backend.control.mouse import mouse_controller
from backend.utils.logger import logger


@tool
def move_mouse(x: float, y: float, normalized: bool = True) -> str:
    """
    Move the mouse cursor to specific coordinates on the Windows screen.
    
    Args:
        x: X-coordinate (normalized float between 0.0 and 1.0 if normalized=True, or pixel index).
        y: Y-coordinate (normalized float between 0.0 and 1.0 if normalized=True, or pixel index).
        normalized: True if coordinates are relative [0.0, 1.0] (default), False for raw screen pixels.
    """
    success = mouse_controller.move(x, y, normalized=normalized)
    if success:
        logger.info(f"[TOOL] Mouse moved to ({x}, {y}) [normalized={normalized}]")
        return f"Successfully moved mouse cursor to ({x}, {y})"
    return f"Failed to move mouse cursor to ({x}, {y})"


@tool
def click_mouse(button: str = "left") -> str:
    """
    Perform a mouse click at the current cursor position.
    
    Args:
        button: Mouse button to click ('left', 'right', or 'middle'). Defaults to 'left'.
    """
    success = mouse_controller.click(button=button)
    if success:
        logger.info(f"[TOOL] Mouse click performed ({button})")
        return f"Clicked mouse {button} button"
    return f"Failed to perform mouse click ({button})"


@tool
def double_click_mouse(button: str = "left") -> str:
    """
    Perform a double click at the current mouse position.
    
    Args:
        button: Mouse button to double click ('left', 'right', 'middle'). Defaults to 'left'.
    """
    success = mouse_controller.double_click(button=button)
    if success:
        logger.info(f"[TOOL] Mouse double-click performed ({button})")
        return f"Double-clicked mouse {button} button"
    return f"Failed to perform double click ({button})"


@tool
def scroll_mouse(delta: float) -> str:
    """
    Scroll mouse vertical wheel up or down.
    
    Args:
        delta: Scroll amount. Positive value scrolls up, negative value scrolls down.
    """
    success = mouse_controller.scroll(delta=delta)
    if success:
        logger.info(f"[TOOL] Mouse scrolled delta={delta}")
        return f"Scrolled mouse wheel by delta {delta}"
    return "Failed to scroll mouse wheel"
