"""Control package for Windows desktop automation."""

from backend.control.mouse import MouseController, mouse_controller
from backend.control.keyboard import KeyboardController, keyboard_controller
from backend.control.window import WindowController, window_controller

__all__ = [
    "MouseController",
    "mouse_controller",
    "KeyboardController",
    "keyboard_controller",
    "WindowController",
    "window_controller",
]
