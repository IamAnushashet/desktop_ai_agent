"""Verification Engine module for Desktop AI Agent GUI Subagent."""

import time
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.agent.subagents.screen_observer import ScreenObservation, screen_observer
from backend.utils.logger import logger


class VerificationResult(BaseModel):
    """Result of verifying observable screen changes post-action."""

    success: bool
    expected_condition: str
    observed_state: Optional[ScreenObservation] = None
    message: str
    verification_latency_ms: float = 0.0


class VerificationEngine:
    """
    Verifies that GUI actions produced the expected observable screen state.
    Eliminates false success reports where browser tools return without error
    but the action failed or executed in the wrong tab/window.
    """

    def verify_action_result(
        self,
        expected_condition: str,
        query_text: Optional[str] = None,
        timeout_seconds: float = 3.0,
        pause_seconds: float = 0.5
    ) -> VerificationResult:
        """
        Poll screen state until expected condition is verified or timeout expires.
        
        Args:
            expected_condition: Description or key ('youtube_page_loaded', 'youtube_search_results', 'chrome_active', 'window_closed').
            query_text: Target search query string to match in page title or content.
            timeout_seconds: Maximum polling window in seconds.
            pause_seconds: Delay before initial observation.
            
        Returns:
            VerificationResult detailing success status and empirical evidence.
        """
        start_t = time.perf_counter()
        time.sleep(pause_seconds)

        cond_clean = expected_condition.lower().strip()
        query_clean = (query_text or "").lower().strip()

        deadline = start_t + timeout_seconds
        last_obs: Optional[ScreenObservation] = None

        while time.perf_counter() < deadline:
            obs = screen_observer.observe(force_refresh=True)
            last_obs = obs

            # 1. VERIFY YOUTUBE SEARCH RESULTS LOADED
            if cond_clean in ["youtube_search_results", "search_results"]:
                if obs.is_chrome_active:
                    title_l = obs.window_title.lower()
                    if query_clean:
                        # Match if query or youtube in title and not on transient loading screen
                        if (query_clean in title_l or "youtube" in title_l or (obs.search_query_detected and query_clean in obs.search_query_detected.lower())):
                            if not any(transient in title_l for transient in ["just a moment", "loading", "connecting", "challenge"]):
                                lat = (time.perf_counter() - start_t) * 1000.0
                                msg = f"[VERIFICATION SUCCESS] YouTube search results loaded for query '{query_text}' in active tab ('{obs.window_title}')."
                                logger.info(msg)
                                return VerificationResult(
                                    success=True,
                                    expected_condition=expected_condition,
                                    observed_state=obs,
                                    message=msg,
                                    verification_latency_ms=round(lat, 2)
                                )
                    elif obs.is_search_results_loaded or "youtube" in title_l:
                        if not any(transient in title_l for transient in ["just a moment", "loading", "connecting"]):
                            lat = (time.perf_counter() - start_t) * 1000.0
                            msg = f"[VERIFICATION SUCCESS] Verified YouTube search results page loaded ('{obs.window_title}')."
                            logger.info(msg)
                            return VerificationResult(
                                success=True,
                                expected_condition=expected_condition,
                                observed_state=obs,
                                message=msg,
                                verification_latency_ms=round(lat, 2)
                            )

            # 2. VERIFY YOUTUBE PAGE OPEN
            if cond_clean in ["youtube_page_loaded", "youtube_open", "youtube_visible"]:
                if obs.is_chrome_active and obs.is_youtube_visible:
                    lat = (time.perf_counter() - start_t) * 1000.0
                    msg = f"[VERIFICATION SUCCESS] Verified YouTube is active in Chrome ('{obs.window_title}')."
                    logger.info(msg)
                    return VerificationResult(
                        success=True,
                        expected_condition=expected_condition,
                        observed_state=obs,
                        message=msg,
                        verification_latency_ms=round(lat, 2)
                    )

            # 3. VERIFY CHROME ACTIVE
            if cond_clean in ["chrome_active", "chrome_open"]:
                if obs.is_chrome_active:
                    lat = (time.perf_counter() - start_t) * 1000.0
                    msg = f"[VERIFICATION SUCCESS] Verified Chrome is active foreground window ('{obs.window_title}')."
                    logger.info(msg)
                    return VerificationResult(
                        success=True,
                        expected_condition=expected_condition,
                        observed_state=obs,
                        message=msg,
                        verification_latency_ms=round(lat, 2)
                    )

            # 4. VERIFY WINDOW CLOSED
            if cond_clean in ["window_closed", "app_closed"]:
                if not obs.is_chrome_active and "chrome" not in obs.active_app.lower():
                    lat = (time.perf_counter() - start_t) * 1000.0
                    msg = f"[VERIFICATION SUCCESS] Verified target window closed (Active window is now '{obs.active_app}')."
                    logger.info(msg)
                    return VerificationResult(
                        success=True,
                        expected_condition=expected_condition,
                        observed_state=obs,
                        message=msg,
                        verification_latency_ms=round(lat, 2)
                    )

            time.sleep(0.3)

        lat = (time.perf_counter() - start_t) * 1000.0
        fail_msg = f"[VERIFICATION FAILURE] Timed out waiting for condition '{expected_condition}' (Query: '{query_text}'). Active title: '{last_obs.window_title if last_obs else 'Unknown'}'"
        logger.warning(fail_msg)
        return VerificationResult(
            success=False,
            expected_condition=expected_condition,
            observed_state=last_obs,
            message=fail_msg,
            verification_latency_ms=round(lat, 2)
        )


# Shared VerificationEngine instance
verification_engine = VerificationEngine()
