"""Action Decider module for Desktop AI Agent GUI Subagent."""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.agent.subagents.screen_observer import ScreenObservation, screen_observer
from backend.agent.subagents.gui_grounding import GroundedTarget, gui_grounding
from backend.security.permissions import close_permission_gate
from backend.utils.logger import logger


class ActionPlan(BaseModel):
    """Execution plan for next GUI action based on grounded screen observation."""

    action_type: str  # "click" | "type" | "hotkey" | "navigate" | "close" | "noop" | "fail"
    intended_app: str = ""
    target_element: str = ""
    grounded_target: Optional[GroundedTarget] = None
    args: Dict[str, Any] = Field(default_factory=dict)
    requires_permission: bool = False
    expected_result_description: str = ""
    can_proceed: bool = True
    reason: str = ""


class ActionDecider:
    """
    Decides the next grounded GUI action by analyzing current screen observation,
    intended user task, safety permissions, and target element grounding.
    """

    def decide_next_action(
        self,
        task_intent: str,
        target_name: str,
        obs: Optional[ScreenObservation] = None,
        action_type: str = "click",
        payload_text: Optional[str] = None,
        grounded_target: Optional[GroundedTarget] = None
    ) -> ActionPlan:
        """
        Determine the safest, most precise next action.
        
        Args:
            task_intent: Description of task goal (e.g. 'search YouTube for Python tutorials').
            target_name: Name of target UI element (e.g. 'youtube_search_box').
            obs: ScreenObservation object.
            action_type: Intended action type ('click', 'type', 'navigate', 'close').
            payload_text: Optional text to type or URL to navigate to.
            grounded_target: Optional pre-grounded target object.
            
        Returns:
            ActionPlan object detailing execution parameters and verification criteria.
        """
        if obs is None:
            obs = screen_observer.observe(force_refresh=False)

        clean_action = action_type.lower().strip()
        logger.info(f"[ACTION DECIDER] Evaluating action '{clean_action}' on '{target_name}' for task '{task_intent}'")

        # 1. SECURITY & PERMISSION GATE CHECK
        if clean_action in ["close", "close_window", "close_app"]:
            app_target = obs.active_app or "Application Window"
            logger.info(f"[ACTION DECIDER SECURITY] Close action detected -> Requesting permission for '{app_target}'")
            return ActionPlan(
                action_type="close",
                intended_app=app_target,
                target_element=target_name,
                requires_permission=True,
                expected_result_description=f"Application window '{app_target}' should be closed.",
                can_proceed=True,
                reason="Requires Global Close Permission Gate approval before execution.",
            )

        # 2. NAVIGATION ACTIONS
        if clean_action == "navigate":
            target_url = payload_text or "https://www.youtube.com"
            return ActionPlan(
                action_type="navigate",
                intended_app="Google Chrome",
                target_element="chrome_address_bar",
                args={"url": target_url},
                requires_permission=False,
                expected_result_description=f"Chrome should navigate to '{target_url}' and render page.",
                can_proceed=True,
                reason="Navigation request queued for active browser.",
            )

        # 3. GROUNDING CHECK FOR GUI CLICK / TYPE ACTIONS
        grounded = grounded_target or gui_grounding.ground_target(target_name=target_name, obs=obs)

        if not grounded.is_valid or grounded.confidence < 0.50:
            err_msg = f"Cannot confidently ground target '{target_name}' (Confidence: {grounded.confidence:.2f}). Refusing to execute ungrounded click/type."
            logger.warning(f"[ACTION DECIDER REJECTED] {err_msg}")
            return ActionPlan(
                action_type="noop",
                intended_app=obs.active_app,
                target_element=target_name,
                grounded_target=grounded,
                requires_permission=False,
                expected_result_description="No action executed due to low grounding confidence.",
                can_proceed=False,
                reason=err_msg,
            )

        # 4. CLICK ACTION
        if clean_action == "click":
            return ActionPlan(
                action_type="click",
                intended_app=obs.active_app,
                target_element=target_name,
                grounded_target=grounded,
                args={"x": grounded.x, "y": grounded.y},
                requires_permission=False,
                expected_result_description=f"Target '{target_name}' at ({grounded.x}, {grounded.y}) should receive focus/click.",
                can_proceed=True,
                reason=f"Target '{target_name}' successfully grounded using {grounded.method_used}.",
            )

        # 5. TYPE ACTION
        if clean_action == "type":
            text_to_type = payload_text or ""
            return ActionPlan(
                action_type="type",
                intended_app=obs.active_app,
                target_element=target_name,
                grounded_target=grounded,
                args={"x": grounded.x, "y": grounded.y, "text": text_to_type},
                requires_permission=False,
                expected_result_description=f"Text '{text_to_type}' should be entered into '{target_name}'.",
                can_proceed=True,
                reason=f"Target input field '{target_name}' grounded at ({grounded.x}, {grounded.y}) via {grounded.method_used}.",
            )

        # Default fallback
        return ActionPlan(
            action_type=clean_action,
            intended_app=obs.active_app,
            target_element=target_name,
            grounded_target=grounded,
            can_proceed=True,
            reason="Action decision completed.",
        )


# Shared ActionDecider instance
action_decider = ActionDecider()
