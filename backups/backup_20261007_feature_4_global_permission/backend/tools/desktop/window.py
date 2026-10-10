"""Window control tools wrapping WindowController."""

from langchain_core.tools import tool
from backend.control.window import window_controller
from backend.control.keyboard import keyboard_controller
from backend.utils.logger import logger


@tool
def window_action(action: str) -> str:
    """
    Perform a window management action on the active foreground window.
    
    Args:
        action: The window operation to execute ('minimize', 'maximize', 'restore', 'close').
    """
    act = action.lower().strip()
    if act == "minimize":
        success = window_controller.minimize()
        if success:
            logger.info(f"[TOOL] Window action '{act}' executed successfully")
            return f"Successfully executed window action '{act}'"
        return f"Failed to execute window action '{act}'"
    elif act == "maximize":
        success = window_controller.maximize()
        if success:
            logger.info(f"[TOOL] Window action '{act}' executed successfully")
            return f"Successfully executed window action '{act}'"
        return f"Failed to execute window action '{act}'"
    elif act == "restore":
        success = window_controller.restore()
        if success:
            logger.info(f"[TOOL] Window action '{act}' executed successfully")
            return f"Successfully executed window action '{act}'"
        return f"Failed to execute window action '{act}'"
    elif act in ["close", "exit", "quit", "terminate"]:
        # Route ALL close actions through central WindowController permission gate
        return window_controller.close_window()
    else:
        return f"Unknown window action '{action}'. Supported actions: minimize, maximize, restore, close."


@tool
def get_active_window_info() -> str:
    """
    Get information about the currently active foreground window on Windows (title, dimensions, state).
    """
    info = window_controller.get_active_window()
    logger.info(f"[TOOL] Retrieved active window info: {info}")
    return f"Active Window Title: '{info.get('title', 'Unknown')}', Dimensions: {info.get('width', 0)}x{info.get('height', 0)}"
