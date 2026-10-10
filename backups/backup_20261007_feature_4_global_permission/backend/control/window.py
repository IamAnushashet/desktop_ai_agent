"""Windows window controller for Desktop AI Agent."""

import ctypes
from typing import Dict, Any, Tuple, Optional
import pyautogui
import pygetwindow as gw
from backend.utils.logger import logger


class WindowController:
    """Controls active windows and desktop state on Windows."""

    @staticmethod
    def get_screen_size() -> Tuple[int, int]:
        """Return desktop resolution as (width, height)."""
        size = pyautogui.size()
        return int(size.width), int(size.height)

    @staticmethod
    def _get_active_title_ctypes() -> str:
        """Fallback to Win32 ctypes to retrieve foreground window title."""
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value
        except Exception:
            return ""

    def get_active_window(self) -> Dict[str, Any]:
        """Get details about the currently active foreground window."""
        try:
            active = gw.getActiveWindow()
            if active:
                return {
                    "title": active.title,
                    "x": active.left,
                    "y": active.top,
                    "width": active.width,
                    "height": active.height,
                    "is_maximized": active.isMaximized,
                    "is_minimized": active.isMinimized,
                }
            title = self._get_active_title_ctypes()
            return {
                "title": title or "Desktop",
                "x": 0,
                "y": 0,
                "width": 0,
                "height": 0,
                "is_maximized": False,
                "is_minimized": False,
            }
        except Exception as e:
            logger.error(f"Failed to get active window: {e}")
            return {"title": "Unknown", "error": str(e)}

    def minimize(self) -> bool:
        """Minimize the currently active foreground window."""
        try:
            active = gw.getActiveWindow()
            if active:
                active.minimize()
                return True
            # Fallback using Win32 API
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                # SW_MINIMIZE = 6
                ctypes.windll.user32.ShowWindow(hwnd, 6)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to minimize active window: {e}")
            return False

    def maximize(self) -> bool:
        """Maximize the currently active foreground window."""
        try:
            active = gw.getActiveWindow()
            if active:
                active.maximize()
                return True
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                # SW_MAXIMIZE = 3
                ctypes.windll.user32.ShowWindow(hwnd, 3)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to maximize active window: {e}")
            return False

    def restore(self) -> bool:
        """Restore the currently active foreground window."""
        try:
            active = gw.getActiveWindow()
            if active:
                active.restore()
                return True
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                # SW_RESTORE = 9
                ctypes.windll.user32.ShowWindow(hwnd, 9)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to restore active window: {e}")
            return False

    def close_window(self, target_name: Optional[str] = None, timeout_seconds: float = 60.0) -> str:
        """
        Close an application or window through the Central Global Permission Gate.
        Enforces explicit user confirmation before executing any window close.
        
        Args:
            target_name: Optional application name or window title to close. If None, resolves foreground window.
            timeout_seconds: Permission request expiration timeout (default 60s).
            
        Returns:
            Human readable result string detailing confirmation outcome and verification.
        """
        from backend.security.permissions import close_permission_gate
        import time

        # 1. Resolve dynamic target name
        active_info = self.get_active_window()
        active_title = active_info.get("title", "")

        if target_name and target_name.strip():
            display_target = target_name.strip()
        else:
            display_target = self.resolve_friendly_app_name(active_title)

        logger.info(f"[WINDOW CONTROL] Close requested for target: '{display_target}' (active title: '{active_title}')")

        # 2. GLOBAL CLOSE PERMISSION GATE
        gate_result = close_permission_gate.request_close_permission(
            target=display_target,
            timeout_seconds=timeout_seconds
        )

        if not gate_result.get("approved"):
            reason = gate_result.get("reason", "Permission denied.")
            status = gate_result.get("status", "rejected")
            logger.warning(f"[WINDOW CONTROL REJECTED] Close operation for '{display_target}' blocked by gate ({reason})")
            return f"Close action cancelled ({status}): User permission denied to close '{display_target}'."

        # 3. USER APPROVED -> Perform Window Close Operation
        logger.info(f"[WINDOW CONTROL APPROVED] Executing actual close for '{display_target}'")
        closed_attempted = False

        try:
            active = gw.getActiveWindow()
            if active:
                active.close()
                closed_attempted = True
            else:
                # Win32 WM_CLOSE (0x0010) fallback
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd:
                    ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
                    closed_attempted = True
        except Exception as err:
            logger.warning(f"[WINDOW CONTROL] Active window close call error: {err}, falling back to Alt+F4")

        if not closed_attempted:
            try:
                pyautogui.hotkey("alt", "f4")
                closed_attempted = True
            except Exception as err:
                logger.error(f"[WINDOW CONTROL] Alt+F4 fallback failed: {err}")

        # 4. VERIFICATION STEP
        time.sleep(1.0)
        verified = self.verify_window_closed(active_title, display_target)

        if verified:
            msg = f"Successfully closed application '{display_target}' after user confirmation."
            logger.info(f"[WINDOW CONTROL SUCCESS] {msg}")
            return msg
        else:
            msg = f"Close verification failed: Application '{display_target}' remains open."
            logger.warning(f"[WINDOW CONTROL VERIFY FAILED] {msg}")
            return msg

    @staticmethod
    def resolve_friendly_app_name(window_title: str) -> str:
        """Helper to extract clean human-readable application name from window title."""
        if not window_title or window_title.strip() == "" or window_title == "Desktop":
            return "Desktop Window"

        t_lower = window_title.lower()
        if "chrome" in t_lower:
            return "Google Chrome"
        elif "word" in t_lower or "winword" in t_lower:
            return "Microsoft Word"
        elif "powerpoint" in t_lower or "ppt" in t_lower or "powerpnt" in t_lower:
            return "Microsoft PowerPoint"
        elif "paint" in t_lower or "mspaint" in t_lower:
            return "Microsoft Paint"
        elif "notepad" in t_lower:
            return "Notepad"
        elif "calculator" in t_lower or "calc" in t_lower:
            return "Calculator"
        elif "spotify" in t_lower:
            return "Spotify"
        elif "cmd" in t_lower or "prompt" in t_lower or "powershell" in t_lower:
            return "Terminal Window"

        # Return title or last part if separated by dash
        if " - " in window_title:
            parts = window_title.split(" - ")
            return parts[-1].strip()
        return window_title.strip()

    @staticmethod
    def verify_window_closed(previous_title: str, target_name: str) -> bool:
        """Verify window or application process is no longer active."""
        try:
            current_active = gw.getActiveWindow()
            if not current_active:
                return True
            curr_title = current_active.title or ""
            if not curr_title or curr_title == "Desktop":
                return True
            # Check if previous specific title is gone
            if previous_title and previous_title != "Desktop" and previous_title.lower() in curr_title.lower():
                return False
            # Check target name
            if target_name and target_name.lower() in curr_title.lower():
                return False
            return True
        except Exception:
            return True


# Shared window controller instance
window_controller = WindowController()

