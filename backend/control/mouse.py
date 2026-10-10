"""Windows mouse controller for Desktop AI Agent."""

import threading
from typing import Tuple, Optional
import pyautogui
from backend.config.settings import settings
from backend.security.validator import (
    validate_coordinate,
    validate_button,
    validate_delta,
)
from backend.utils.logger import logger

# Optimize PyAutoGUI for low latency and headless safety
pyautogui.PAUSE = 0.001
pyautogui.FAILSAFE = False


class MouseController:
    """Provides safe, normalized and relative mouse control on Windows."""

    def __init__(self, sensitivity: float = settings.MOUSE_SENSITIVITY):
        self.sensitivity = sensitivity
        self._lock = threading.Lock()

    @staticmethod
    def get_screen_size() -> Tuple[int, int]:
        """Return the Windows desktop screen width and height in pixels."""
        size = pyautogui.size()
        if hasattr(size, "width") and hasattr(size, "height"):
            return int(size.width), int(size.height)
        return int(size[0]), int(size[1])

    def to_screen_coordinates(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """Map normalized [0.0, 1.0] coordinates to Windows screen pixel coordinates."""
        width, height = self.get_screen_size()
        clamped_x = max(0.0, min(1.0, float(norm_x)))
        clamped_y = max(0.0, min(1.0, float(norm_y)))

        pixel_x = int(round(clamped_x * (width - 1)))
        pixel_y = int(round(clamped_y * (height - 1)))
        return pixel_x, pixel_y

    def move(self, x: float, y: float, normalized: bool = True) -> bool:
        """Move cursor to specified coordinate (normalized or pixel)."""
        try:
            if normalized:
                if not (validate_coordinate(x) and validate_coordinate(y)):
                    logger.warning(f"Invalid normalized coordinates: x={x}, y={y}")
                    return False
                px, py = self.to_screen_coordinates(x, y)
            else:
                px, py = int(x), int(y)

            with self._lock:
                pyautogui.moveTo(px, py)
            return True
        except Exception as e:
            logger.error(f"Failed to move mouse: {e}")
            return False

    def move_relative(self, dx: float, dy: float) -> bool:
        """Move cursor relatively based on delta and sensitivity (for touchpad mode)."""
        try:
            offset_x = int(dx * self.sensitivity)
            offset_y = int(dy * self.sensitivity)
            if offset_x == 0 and offset_y == 0:
                return True

            with self._lock:
                pyautogui.moveRel(offset_x, offset_y)
            return True
        except Exception as e:
            logger.error(f"Failed relative mouse move: {e}")
            return False

    def click(self, x: Optional[float] = None, y: Optional[float] = None, button: str = "left", normalized: bool = False) -> bool:
        """Perform a single click, optionally moving to (x, y) coordinates first."""
        if x is not None and y is not None:
            self.move(x, y, normalized=normalized)
        button_norm = button.lower().strip() if isinstance(button, str) else "left"
        if not validate_button(button_norm):
            logger.warning(f"Invalid mouse button: {button}")
            return False

        try:
            with self._lock:
                pyautogui.click(button=button_norm)
            return True
        except Exception as e:
            logger.error(f"Failed mouse click ({button_norm}): {e}")
            return False

    def click_at(self, x: float, y: float, normalized: bool = False, button: str = "left") -> bool:
        """Move cursor to (x, y) and perform single click."""
        return self.click(x=x, y=y, button=button, normalized=normalized)

    def double_click(self, button: str = "left") -> bool:
        """Perform a double click."""
        button_norm = button.lower().strip()
        if not validate_button(button_norm):
            logger.warning(f"Invalid mouse button: {button}")
            return False

        try:
            with self._lock:
                pyautogui.doubleClick(button=button_norm)
            return True
        except Exception as e:
            logger.error(f"Failed mouse double click ({button_norm}): {e}")
            return False

    def mouse_down(self, button: str = "left") -> bool:
        """Press and hold mouse button."""
        button_norm = button.lower().strip()
        if not validate_button(button_norm):
            return False

        try:
            with self._lock:
                pyautogui.mouseDown(button=button_norm)
            return True
        except Exception as e:
            logger.error(f"Failed mouse down ({button_norm}): {e}")
            return False

    def mouse_up(self, button: str = "left") -> bool:
        """Release mouse button."""
        button_norm = button.lower().strip()
        if not validate_button(button_norm):
            return False

        try:
            with self._lock:
                pyautogui.mouseUp(button=button_norm)
            return True
        except Exception as e:
            logger.error(f"Failed mouse up ({button_norm}): {e}")
            return False

    def drag(self, x: float, y: float, normalized: bool = True) -> bool:
        """Drag mouse to target coordinate."""
        try:
            if normalized:
                if not (validate_coordinate(x) and validate_coordinate(y)):
                    return False
                px, py = self.to_screen_coordinates(x, y)
            else:
                px, py = int(x), int(y)

            with self._lock:
                pyautogui.dragTo(px, py, button="left")
            return True
        except Exception as e:
            logger.error(f"Failed mouse drag: {e}")
            return False

    def scroll(self, delta: float) -> bool:
        """Scroll vertical wheel. Positive delta scrolls up, negative scrolls down."""
        if not validate_delta(delta):
            logger.warning(f"Invalid scroll delta: {delta}")
            return False

        try:
            clicks = int(delta * 120) if abs(delta) < 10 else int(delta)
            with self._lock:
                pyautogui.scroll(clicks)
            return True
        except Exception as e:
            logger.error(f"Failed mouse scroll: {e}")
            return False


# Shared mouse controller instance
mouse_controller = MouseController()
