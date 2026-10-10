"""YouTube Workflow Subagent for Screen-Aware Desktop AI Agent.

Implements the Observe -> Decide -> Act -> Verify loop for browser YouTube operations,
fixing the wrong-tab issue and guaranteeing verified execution.
"""

import time
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.agent.subagents.screen_observer import screen_observer, ScreenObservation
from backend.agent.subagents.gui_grounding import gui_grounding, GroundedTarget
from backend.agent.subagents.action_decider import action_decider, ActionPlan
from backend.agent.subagents.verification import verification_engine, VerificationResult
from backend.tools.browser.browser import open_chrome, bring_chrome_to_foreground
from backend.control.mouse import mouse_controller
from backend.control.keyboard import keyboard_controller
from backend.utils.logger import logger


class YouTubeTaskResult(BaseModel):
    """Execution output from YouTube workflow subagent."""

    success: bool
    query: str
    initial_active_window: str = ""
    grounding_method_used: str = ""
    grounded_coordinates: Optional[Dict[str, int]] = None
    executed_actions: list = Field(default_factory=list)
    verification_message: str = ""
    total_duration_seconds: float = 0.0
    observation_latency_ms: float = 0.0
    grounding_latency_ms: float = 0.0
    action_latency_ms: float = 0.0
    verification_latency_ms: float = 0.0
    recovery_steps_taken: int = 0


class YouTubeWorkflow:
    """
    Subagent orchestrator for executing YouTube search tasks with end-to-end
    screen perception, grounding, execution, and verification.
    """

    def execute_youtube_search(
        self,
        query: str,
        max_retries: int = 2
    ) -> YouTubeTaskResult:
        """
        Execute YouTube search query using Observe -> Decide -> Act -> Verify loop.
        
        Args:
            query: Search term (e.g. 'Python tutorials').
            max_retries: Maximum recovery retries allowed.
            
        Returns:
            YouTubeTaskResult containing empirical evidence and timing metrics.
        """
        start_time = time.perf_counter()
        executed_actions = []
        clean_query = query.strip()
        recovery_count = 0

        logger.info(f"[YOUTUBE SUBAGENT START] Executing search for '{clean_query}'")

        # ------------------------------------------------------------------
        # STEP 1: OBSERVE CURRENT SCREEN & WINDOW STATE
        # ------------------------------------------------------------------
        obs = screen_observer.observe(force_refresh=True)
        initial_window = obs.window_title or obs.active_app
        executed_actions.append(f"Observed active window: '{initial_window}'")

        # ------------------------------------------------------------------
        # STEP 2: ENSURE YOUTUBE TAB / NAVIGATE TO YOUTUBE
        # ------------------------------------------------------------------
        bring_chrome_to_foreground()
        time.sleep(0.3)
        obs = screen_observer.observe(force_refresh=True)

        if not obs.is_youtube_visible:
            logger.info("[YOUTUBE SUBAGENT] YouTube not visible in active tab -> Navigating active tab to https://www.youtube.com")
            
            # 1. Launch/focus Chrome executable
            open_chrome.invoke({"url": "https://www.youtube.com"})
            bring_chrome_to_foreground()
            time.sleep(0.3)

            # 2. Navigate active tab explicitly via Ctrl+L to avoid wrong tab execution
            keyboard_controller.press_hotkey("ctrl", "l")
            time.sleep(0.2)
            keyboard_controller.type_text("https://www.youtube.com")
            time.sleep(0.1)
            keyboard_controller.press_key("enter")

            executed_actions.append("Navigated active Chrome tab to https://www.youtube.com")

            # 3. Verify navigation
            v_nav = verification_engine.verify_action_result("youtube_page_loaded", timeout_seconds=6.0)
            if not v_nav.success:
                logger.warning("[YOUTUBE SUBAGENT NAV NOTICE] Navigation check unconfirmed, retrying navigation via Ctrl+L")
                bring_chrome_to_foreground()
                time.sleep(0.2)
                keyboard_controller.press_hotkey("ctrl", "l")
                time.sleep(0.2)
                keyboard_controller.type_text("https://www.youtube.com")
                time.sleep(0.1)
                keyboard_controller.press_key("enter")
                recovery_count += 1
                verification_engine.verify_action_result("youtube_page_loaded", timeout_seconds=6.0)

        # Re-observe active tab state
        bring_chrome_to_foreground()
        time.sleep(0.4)
        obs = screen_observer.observe(force_refresh=True)

        # ------------------------------------------------------------------
        # STEP 3: GROUND YOUTUBE SEARCH BOX (Priority 1 -> 2 -> 3)
        # ------------------------------------------------------------------
        grounded: GroundedTarget = gui_grounding.ground_target("youtube_search_box", obs=obs)
        executed_actions.append(f"Grounded search box via {grounded.method_used} at ({grounded.x}, {grounded.y})")

        if not grounded.is_valid:
            logger.warning("[YOUTUBE SUBAGENT] Primary search box grounding returned invalid -> Attempting fallback focus")
            recovery_count += 1

        # ------------------------------------------------------------------
        # STEP 4: DECIDE & EXECUTE ACTIONS (Click -> Focus -> Type -> Enter)
        # ------------------------------------------------------------------
        plan = action_decider.decide_next_action(
            task_intent=f"Search YouTube for '{clean_query}'",
            target_name="youtube_search_box",
            obs=obs,
            action_type="type",
            payload_text=clean_query,
            grounded_target=grounded,
        )

        act_start = time.perf_counter()

        # Ensure active focus is strictly on Chrome
        bring_chrome_to_foreground()
        time.sleep(0.2)

        # Action Execution Sequence:
        # A. Focus search field
        if grounded.is_valid and grounded.x > 0 and grounded.y > 0:
            mouse_controller.click(grounded.x, grounded.y)
            time.sleep(0.2)
            executed_actions.append(f"Clicked grounded search box at ({grounded.x}, {grounded.y})")
        else:
            # Shortcut fallback: '/' on YouTube focuses search bar
            keyboard_controller.press_key("/")
            time.sleep(0.2)
            executed_actions.append("Pressed '/' shortcut to focus YouTube search bar")

        # B. Clear existing text (Ctrl+A -> Backspace) & Type Query
        keyboard_controller.press_hotkey("ctrl", "a")
        time.sleep(0.1)
        keyboard_controller.type_text(clean_query, interval=0.02)
        executed_actions.append(f"Typed search query: '{clean_query}'")

        # C. Submit query with Enter
        time.sleep(0.2)
        keyboard_controller.press_key("enter")
        executed_actions.append("Pressed Enter to submit search")

        act_lat = (time.perf_counter() - act_start) * 1000.0

        # ------------------------------------------------------------------
        # STEP 5: VERIFY OBSERVED SEARCH RESULTS
        # ------------------------------------------------------------------
        v_res = verification_engine.verify_action_result(
            expected_condition="youtube_search_results",
            query_text=clean_query,
            timeout_seconds=5.0,
            pause_seconds=1.0
        )

        total_sec = time.perf_counter() - start_time

        result = YouTubeTaskResult(
            success=v_res.success,
            query=clean_query,
            initial_active_window=initial_window,
            grounding_method_used=grounded.method_used,
            grounded_coordinates={"x": grounded.x, "y": grounded.y} if grounded.is_valid else None,
            executed_actions=executed_actions,
            verification_message=v_res.message,
            total_duration_seconds=round(total_sec, 2),
            observation_latency_ms=round(obs.obs_latency_ms, 2),
            grounding_latency_ms=round(grounded.grounding_latency_ms, 2),
            action_latency_ms=round(act_lat, 2),
            verification_latency_ms=round(v_res.verification_latency_ms, 2),
            recovery_steps_taken=recovery_count,
        )

        if v_res.success:
            logger.info(f"[YOUTUBE SUBAGENT SUCCESS] {v_res.message} (Total time: {total_sec:.2f}s)")
        else:
            logger.error(f"[YOUTUBE SUBAGENT FAILURE] {v_res.message}")

        return result


# Shared YouTubeWorkflow instance
youtube_workflow = YouTubeWorkflow()
