"""Screen Observer module for Desktop AI Agent GUI Subagent."""

import time
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from backend.screen.capture import screen_capture
from backend.control.window import window_controller
from backend.utils.logger import logger


class ScreenObservation(BaseModel):
    """Structured observation snapshot of current Windows screen and UI state."""

    timestamp: float = Field(default_factory=time.time)
    active_app: str = "Unknown"
    window_title: str = ""
    window_bounds: Dict[str, int] = Field(default_factory=lambda: {"x": 0, "y": 0, "width": 1920, "height": 1080})
    screen_size: Tuple[int, int] = (1920, 1080)
    is_chrome_open: bool = False
    is_chrome_active: bool = False
    active_tab_title: Optional[str] = None
    is_youtube_visible: bool = False
    is_youtube_search_visible: bool = False
    is_search_results_loaded: bool = False
    search_query_detected: Optional[str] = None
    has_loading_state: bool = False
    has_error_dialog: bool = False
    perception_method: str = "ui_automation"
    obs_latency_ms: float = 0.0
    screenshot_b64: Optional[str] = None


class ScreenObserver:
    """
    Observes desktop screen and foreground window state continuously.
    Prefers lightweight UI Automation and window metadata observation.
    """

    def __init__(self):
        self._cached_obs: Optional[ScreenObservation] = None
        self._cache_ttl: float = 0.5  # Seconds
        self._last_obs_time: float = 0.0

    def observe(self, force_refresh: bool = True, include_screenshot: bool = False) -> ScreenObservation:
        """
        Capture current screen state and foreground window properties.
        
        Args:
            force_refresh: Bypass observation cache if True.
            include_screenshot: Attach base64 JPEG screenshot if True.
            
        Returns:
            ScreenObservation dataclass with populated UI flags and latency metrics.
        """
        now = time.time()
        if not force_refresh and self._cached_obs and (now - self._last_obs_time) < self._cache_ttl:
            return self._cached_obs

        start_t = time.perf_counter()

        # 1. Screen size and foreground window info
        scr_w, scr_h = window_controller.get_screen_size()
        active_info = window_controller.get_active_window()
        title = active_info.get("title", "") or ""
        app_name = window_controller.resolve_friendly_app_name(title)
        title_lower = title.lower()

        # 2. Window bounds
        bounds = {
            "x": active_info.get("x", 0),
            "y": active_info.get("y", 0),
            "width": active_info.get("width", scr_w),
            "height": active_info.get("height", scr_h),
        }

        # 3. Chrome and tab detection
        is_chrome_active = "chrome" in app_name.lower() or "chrome" in title_lower
        is_chrome_open = is_chrome_active or self._check_if_chrome_open()
        
        active_tab_title = None
        if is_chrome_active:
            # Active window title in Chrome typically ends with " - Google Chrome"
            if " - google chrome" in title_lower:
                active_tab_title = title.split(" - Google Chrome")[0].strip()
            else:
                active_tab_title = title

        # 4. YouTube visibility flags
        is_yt_visible = False
        if is_chrome_active and active_tab_title:
            tab_l = active_tab_title.lower()
            if "youtube" in tab_l:
                is_yt_visible = True

        # 5. Search box and search result detection
        is_yt_search_visible = is_yt_visible
        is_search_results_loaded = False
        detected_query = None

        if is_yt_visible and active_tab_title:
            tab_l = active_tab_title.lower()
            # YouTube search result titles usually take the form: "python tutorials - YouTube"
            if " - youtube" in tab_l:
                possible_q = active_tab_title.rsplit(" - YouTube", 1)[0].strip()
                if possible_q and possible_q.lower() != "youtube":
                    is_search_results_loaded = True
                    detected_query = possible_q

        # 6. Dialog or error page detection
        has_error = any(err_kw in title_lower for err_kw in ["404", "error", "not found", "offline", "site can't be reached"])
        has_loading = any(ld_kw in title_lower for ld_kw in ["loading", "connecting", "waiting"])

        # 7. Screenshot capture if requested
        screenshot_b64 = None
        if include_screenshot:
            frame = screen_capture.capture_frame(force=force_refresh)
            if frame:
                screenshot_b64 = frame.get("data")

        latency_ms = (time.perf_counter() - start_t) * 1000.0

        obs = ScreenObservation(
            timestamp=now,
            active_app=app_name,
            window_title=title,
            window_bounds=bounds,
            screen_size=(scr_w, scr_h),
            is_chrome_open=is_chrome_open,
            is_chrome_active=is_chrome_active,
            active_tab_title=active_tab_title,
            is_youtube_visible=is_yt_visible,
            is_youtube_search_visible=is_yt_search_visible,
            is_search_results_loaded=is_search_results_loaded,
            search_query_detected=detected_query,
            has_loading_state=has_loading,
            has_error_dialog=has_error,
            perception_method="ui_automation",
            obs_latency_ms=round(latency_ms, 2),
            screenshot_b64=screenshot_b64,
        )

        self._cached_obs = obs
        self._last_obs_time = now
        logger.debug(
            f"[SCREEN OBSERVER] App: '{app_name}' | Title: '{title}' | YT Visible: {is_yt_visible} | Latency: {obs.obs_latency_ms:.1f}ms"
        )
        return obs

    def _check_if_chrome_open(self) -> bool:
        """Check pygetwindow or process table for running Chrome instance."""
        try:
            import pygetwindow as gw
            titles = gw.getAllTitles()
            return any("chrome" in t.lower() for t in titles if t)
        except Exception:
            return False

    def invalidate_cache(self):
        """Invalidate the short-lived observation cache."""
        self._cached_obs = None
        self._last_obs_time = 0.0


# Shared ScreenObserver instance
screen_observer = ScreenObserver()
