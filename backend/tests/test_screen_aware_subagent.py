"""Automated tests for Screen-Aware GUI Subagent and YouTube Workflow."""

import pytest
from unittest.mock import MagicMock, patch

from backend.agent.subagents.screen_observer import ScreenObserver, ScreenObservation
from backend.agent.subagents.gui_grounding import GUIGrounding, GroundedTarget
from backend.agent.subagents.action_decider import ActionDecider, ActionPlan
from backend.agent.subagents.verification import VerificationEngine, VerificationResult
from backend.agent.subagents.youtube_workflow import YouTubeWorkflow
from backend.security.permissions import close_permission_gate


class TestScreenObserver:
    """Unit tests for ScreenObserver UI perception."""

    @patch("backend.agent.subagents.screen_observer.window_controller")
    def test_observe_active_chrome_youtube(self, mock_win):
        mock_win.get_screen_size.return_value = (1920, 1080)
        mock_win.get_active_window.return_value = {
            "title": "Python tutorials - YouTube - Google Chrome",
            "x": 0, "y": 0, "width": 1920, "height": 1080
        }
        mock_win.resolve_friendly_app_name.return_value = "Google Chrome"

        observer = ScreenObserver()
        obs = observer.observe(force_refresh=True)

        assert obs.is_chrome_active is True
        assert obs.is_youtube_visible is True
        assert obs.is_search_results_loaded is True
        assert obs.search_query_detected == "Python tutorials"
        assert obs.perception_method == "ui_automation"
        assert obs.obs_latency_ms >= 0.0

    @patch("backend.agent.subagents.screen_observer.window_controller")
    def test_observe_error_state(self, mock_win):
        mock_win.get_screen_size.return_value = (1920, 1080)
        mock_win.get_active_window.return_value = {
            "title": "404 Not Found - Google Chrome",
            "x": 0, "y": 0, "width": 1920, "height": 1080
        }
        mock_win.resolve_friendly_app_name.return_value = "Google Chrome"

        observer = ScreenObserver()
        obs = observer.observe(force_refresh=True)

        assert obs.has_error_dialog is True


class TestGUIGrounding:
    """Unit tests for GUI Grounding and priority routing."""

    def test_priority1_youtube_search_grounding(self):
        grounding = GUIGrounding()
        obs = ScreenObservation(
            window_bounds={"x": 100, "y": 50, "width": 1000, "height": 800},
            screen_size=(1920, 1080),
            is_chrome_active=True,
            is_youtube_visible=True,
            window_title="YouTube - Google Chrome"
        )

        res = grounding.ground_target("youtube_search_box", obs=obs)

        assert res.is_valid is True
        assert res.confidence >= 0.70
        assert res.method_used in ["ui_automation", "ocr_opencv", "fallback_shortcut"]
        assert res.x > 0
        assert res.y > 0

    @patch("backend.agent.subagents.gui_grounding.get_nvidia_llm")
    def test_priority3_vision_llm_fallback(self, mock_llm_getter):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"x": 960, "y": 140, "confidence": 0.85, "details": "Grounded search box"}'
        mock_llm.invoke.return_value = mock_response
        mock_llm_getter.return_value = mock_llm

        grounding = GUIGrounding()
        obs = ScreenObservation(
            window_bounds={"x": 0, "y": 0, "width": 1920, "height": 1080},
            screen_size=(1920, 1080),
            screenshot_b64="fake_base64_data",
            window_title="Unknown App"
        )

        res = grounding._ground_priority3_vision_llm("custom_element", obs)

        assert res.is_valid is True
        assert res.x == 960
        assert res.y == 140
        assert res.method_used == "vision_llm"


class TestActionDecider:
    """Unit tests for Action Decider safety checks."""

    def test_close_action_triggers_permission_flag(self):
        decider = ActionDecider()
        obs = ScreenObservation(active_app="Google Chrome", window_title="Google Chrome")

        plan = decider.decide_next_action(
            task_intent="Close Chrome browser",
            target_name="chrome_window",
            obs=obs,
            action_type="close"
        )

        assert plan.requires_permission is True
        assert plan.action_type == "close"
        assert plan.can_proceed is True

    def test_ungrounded_target_refuses_click(self):
        decider = ActionDecider()
        obs = ScreenObservation(screen_size=(1920, 1080), window_title="Desktop")

        with patch("backend.agent.subagents.action_decider.gui_grounding.ground_target") as mock_ground:
            mock_ground.return_value = GroundedTarget(
                target_name="non_existent", confidence=0.1, is_valid=False, method_used="none"
            )
            plan = decider.decide_next_action(
                task_intent="Click missing element",
                target_name="non_existent",
                obs=obs,
                action_type="click"
            )

            assert plan.can_proceed is False
            assert plan.action_type == "noop"
            assert "Refusing to execute ungrounded" in plan.reason


class TestVerificationEngine:
    """Unit tests for Verification Engine."""

    @patch("backend.agent.subagents.verification.screen_observer")
    def test_verify_youtube_search_results_success(self, mock_obs):
        mock_obs.observe.return_value = ScreenObservation(
            is_chrome_active=True,
            is_youtube_visible=True,
            is_search_results_loaded=True,
            window_title="Python tutorials - YouTube - Google Chrome",
            search_query_detected="Python tutorials"
        )

        engine = VerificationEngine()
        res = engine.verify_action_result(
            expected_condition="youtube_search_results",
            query_text="Python tutorials",
            timeout_seconds=1.0,
            pause_seconds=0.1
        )

        assert res.success is True
        assert "YouTube search results loaded" in res.message


class TestYouTubeWorkflow:
    """Unit tests for YouTube Workflow subagent end-to-end execution scenarios."""

    @patch("backend.agent.subagents.youtube_workflow.open_chrome")
    @patch("backend.agent.subagents.youtube_workflow.keyboard_controller")
    @patch("backend.agent.subagents.youtube_workflow.mouse_controller")
    @patch("backend.agent.subagents.youtube_workflow.screen_observer")
    @patch("backend.agent.subagents.youtube_workflow.gui_grounding")
    @patch("backend.agent.subagents.youtube_workflow.verification_engine")
    def test_youtube_workflow_different_tab_switching(
        self, mock_verify, mock_grounding, mock_observer, mock_mouse, mock_kb, mock_chrome
    ):
        """Scenario: Different Chrome tab active before task starts (e.g. Google.com)."""
        # Initial observation: Google tab active
        obs_initial = ScreenObservation(
            is_chrome_active=True,
            is_youtube_visible=False,
            window_title="Google - Google Chrome"
        )
        # Post-navigation observation: YouTube tab active
        obs_yt = ScreenObservation(
            is_chrome_active=True,
            is_youtube_visible=True,
            window_title="YouTube - Google Chrome"
        )
        mock_observer.observe.side_effect = [obs_initial, obs_yt, obs_yt]

        mock_grounding.ground_target.return_value = GroundedTarget(
            target_name="youtube_search_box", x=960, y=140, confidence=0.90, is_valid=True, method_used="ui_automation"
        )

        mock_verify.verify_action_result.return_value = VerificationResult(
            success=True, expected_condition="youtube_search_results", message="Verified search results loaded."
        )

        workflow = YouTubeWorkflow()
        result = workflow.execute_youtube_search(query="Python tutorials")

        assert result.success is True
        assert result.grounding_method_used == "ui_automation"
        assert result.grounded_coordinates == {"x": 960, "y": 140}
        mock_chrome.invoke.assert_called_once()
        mock_kb.type_text.assert_called_with("Python tutorials", interval=0.02)
        mock_kb.press_key.assert_called_with("enter")

    @patch("backend.agent.subagents.youtube_workflow.open_chrome")
    @patch("backend.agent.subagents.youtube_workflow.keyboard_controller")
    @patch("backend.agent.subagents.youtube_workflow.mouse_controller")
    @patch("backend.agent.subagents.youtube_workflow.screen_observer")
    @patch("backend.agent.subagents.youtube_workflow.gui_grounding")
    @patch("backend.agent.subagents.youtube_workflow.verification_engine")
    def test_youtube_workflow_search_field_not_detected_fallback(
        self, mock_verify, mock_grounding, mock_observer, mock_mouse, mock_kb, mock_chrome
    ):
        """Scenario: Search field cannot be detected by P1/P2/P3 -> Uses shortcut fallback '/' safely."""
        obs = ScreenObservation(
            is_chrome_active=True,
            is_youtube_visible=True,
            window_title="YouTube - Google Chrome"
        )
        mock_observer.observe.return_value = obs

        # Grounding returns ungrounded
        mock_grounding.ground_target.return_value = GroundedTarget(
            target_name="youtube_search_box", confidence=0.0, is_valid=False, method_used="none"
        )

        mock_verify.verify_action_result.return_value = VerificationResult(
            success=True, expected_condition="youtube_search_results", message="Verified search results loaded."
        )

        workflow = YouTubeWorkflow()
        result = workflow.execute_youtube_search(query="LangGraph")

        assert result.success is True
        assert result.recovery_steps_taken >= 1
        # Verifies '/' shortcut was pressed to focus search bar
        mock_kb.press_key.assert_any_call("/")


class TestGlobalPermissionGatePreservation:
    """Ensure global application close permission gate is strictly preserved."""

    def test_close_window_requires_permission(self):
        from backend.control.window import window_controller
        with patch.object(close_permission_gate, "request_close_permission") as mock_gate:
            mock_gate.return_value = {"approved": False, "status": "rejected", "reason": "Denied by test"}
            res = window_controller.close_window("Google Chrome")
            assert "Close action cancelled" in res
            mock_gate.assert_called_once()
