"""Perception screen capture interface (bridges to backend.screen.capture)."""

from backend.screen.capture import ScreenCapture, screen_capture, ensure_thread_desktop

__all__ = ["ScreenCapture", "screen_capture", "ensure_thread_desktop"]
