"""
Comprehensive Test Suite for Feature 4 — Global Permission Before Application Closing.
Verifies the 10 mandated scenarios proving universal, centralized close permission gate behavior.
"""

import time
import threading
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.security.permissions import close_permission_gate
from backend.control.window import window_controller


@pytest.fixture
def client():
    return TestClient(app)


def test_scenario_1_close_chrome_permission_requested():
    """
    Test 1: Attempt to close Chrome.
    Expected: Permission requested, Chrome NOT closed until approval is given.
    """
    requested_event = threading.Event()
    received_cid = []

    def on_broadcast(req_data):
        if req_data.get("target") == "Google Chrome":
            received_cid.append(req_data.get("confirmation_id"))
            requested_event.set()

    close_permission_gate.register_broadcast_callback(on_broadcast)

    close_thread_result = []

    def run_close():
        with patch.object(window_controller, "get_active_window", return_value={"title": "Google Chrome"}):
            with patch.object(window_controller, "verify_window_closed", return_value=True):
                res = window_controller.close_window(target_name="Google Chrome", timeout_seconds=5.0)
                close_thread_result.append(res)

    t = threading.Thread(target=run_close)
    t.start()

    # Verify permission request was issued before closing
    assert requested_event.wait(timeout=3.0) is True
    cid = received_cid[0]

    # Verify pending state in gate
    pending = close_permission_gate.get_pending_requests()
    assert any(p["confirmation_id"] == cid and p["target"] == "Google Chrome" for p in pending)

    # Approve to finish thread cleanly
    close_permission_gate.respond(cid, "allow")
    t.join(timeout=3.0)
    close_permission_gate.unregister_broadcast_callback(on_broadcast)

    assert len(close_thread_result) == 1
    assert "successfully closed" in close_thread_result[0].lower()


def test_scenario_2_close_chrome_approval():
    """
    Test 2: Approve close request.
    Expected: Chrome closes and verification succeeds.
    """
    close_result = []

    def run_close():
        with patch.object(window_controller, "verify_window_closed", return_value=True):
            res = window_controller.close_window(target_name="Google Chrome", timeout_seconds=5.0)
            close_result.append(res)

    t = threading.Thread(target=run_close)
    t.start()

    # Wait for pending request to register
    time.sleep(0.3)
    pending = close_permission_gate.get_pending_requests()
    chrome_req = next((p for p in pending if p["target"] == "Google Chrome"), None)
    assert chrome_req is not None

    # User Approves
    resp = close_permission_gate.respond(chrome_req["confirmation_id"], "allow")
    assert resp["success"] is True
    assert resp["status"] == "approved"

    t.join(timeout=3.0)
    assert len(close_result) == 1
    assert "successfully closed" in close_result[0].lower()


def test_scenario_3_close_chrome_rejection():
    """
    Test 3: Reject close request.
    Expected: Operation is cancelled, Chrome remains open.
    """
    close_result = []

    def run_close():
        with patch.object(window_controller, "verify_window_closed", return_value=False):
            res = window_controller.close_window(target_name="Google Chrome", timeout_seconds=5.0)
            close_result.append(res)

    t = threading.Thread(target=run_close)
    t.start()

    time.sleep(0.3)
    pending = close_permission_gate.get_pending_requests()
    chrome_req = next((p for p in pending if p["target"] == "Google Chrome"), None)
    assert chrome_req is not None

    # User Rejects / Cancels
    resp = close_permission_gate.respond(chrome_req["confirmation_id"], "cancel")
    assert resp["success"] is True
    assert resp["status"] == "rejected"

    t.join(timeout=3.0)
    assert len(close_result) == 1
    assert "cancelled" in close_result[0].lower() or "denied" in close_result[0].lower()


def test_scenario_4_close_word_permission_requested():
    """
    Test 4: Attempt to close Microsoft Word.
    Expected: Permission requested dynamically for Microsoft Word.
    """
    close_result = []

    def run_close():
        res = window_controller.close_window(target_name="Microsoft Word", timeout_seconds=5.0)
        close_result.append(res)

    t = threading.Thread(target=run_close)
    t.start()

    time.sleep(0.3)
    pending = close_permission_gate.get_pending_requests()
    word_req = next((p for p in pending if p["target"] == "Microsoft Word"), None)
    assert word_req is not None

    # Clean up
    close_permission_gate.respond(word_req["confirmation_id"], "cancel")
    t.join(timeout=3.0)


def test_scenario_5_close_powerpoint_permission_requested():
    """
    Test 5: Attempt to close Microsoft PowerPoint.
    Expected: Permission requested dynamically for Microsoft PowerPoint.
    """
    close_result = []

    def run_close():
        res = window_controller.close_window(target_name="Microsoft PowerPoint", timeout_seconds=5.0)
        close_result.append(res)

    t = threading.Thread(target=run_close)
    t.start()

    time.sleep(0.3)
    pending = close_permission_gate.get_pending_requests()
    ppt_req = next((p for p in pending if p["target"] == "Microsoft PowerPoint"), None)
    assert ppt_req is not None

    close_permission_gate.respond(ppt_req["confirmation_id"], "cancel")
    t.join(timeout=3.0)


def test_scenario_6_close_paint_permission_requested():
    """
    Test 6: Attempt to close Paint.
    Expected: Permission requested dynamically for Microsoft Paint.
    """
    close_result = []

    def run_close():
        res = window_controller.close_window(target_name="Microsoft Paint", timeout_seconds=5.0)
        close_result.append(res)

    t = threading.Thread(target=run_close)
    t.start()

    time.sleep(0.3)
    pending = close_permission_gate.get_pending_requests()
    paint_req = next((p for p in pending if p["target"] == "Microsoft Paint"), None)
    assert paint_req is not None

    close_permission_gate.respond(paint_req["confirmation_id"], "cancel")
    t.join(timeout=3.0)


def test_scenario_7_new_future_application_permission_requested():
    """
    Test 7: Attempt to close a new/arbitrary application (e.g. 'Spotify' or 'CustomApp').
    Expected: Permission requested dynamically without any app-specific hardcoded rules.
    """
    close_result = []
    custom_app_name = "Spotify Music Player"

    def run_close():
        res = window_controller.close_window(target_name=custom_app_name, timeout_seconds=5.0)
        close_result.append(res)

    t = threading.Thread(target=run_close)
    t.start()

    time.sleep(0.3)
    pending = close_permission_gate.get_pending_requests()
    custom_req = next((p for p in pending if p["target"] == custom_app_name), None)
    assert custom_req is not None
    assert custom_req["type"] == "close_window"

    close_permission_gate.respond(custom_req["confirmation_id"], "cancel")
    t.join(timeout=3.0)


def test_scenario_8_direct_close_without_confirmation_rejected():
    """
    Test 8: Attempt direct close without gate confirmation or via taskkill command line.
    Expected: Backend gate blocks direct execution and rejects operation.
    """
    from backend.tools.system.system import run_system_app

    # Test taskkill command injection block
    err_res = run_system_app.invoke({"app_name": "taskkill /f /im chrome.exe"})
    assert "strictly blocked" in err_res or "Global Close Permission Gate" in err_res

    # Test direct permission gate request without approving
    gate_res = close_permission_gate.request_close_permission(target="TestApp", timeout_seconds=0.1)
    assert gate_res["approved"] is False
    assert gate_res["status"] in ["expired", "rejected"]


def test_scenario_9_expired_confirmation_denies_close():
    """
    Test 9: Expired confirmation (user does not respond within timeout).
    Expected: Request expires, close is rejected, application remains open.
    """
    close_result = []

    def run_close():
        res = window_controller.close_window(target_name="Notepad", timeout_seconds=0.5)
        close_result.append(res)

    t = threading.Thread(target=run_close)
    t.start()

    # Do not respond; wait for 0.5s timeout expiration
    t.join(timeout=3.0)

    assert len(close_result) == 1
    assert "cancelled" in close_result[0].lower() or "expired" in close_result[0].lower()


def test_scenario_10_reuse_consumed_confirmation_rejected():
    """
    Test 10: Reuse an already-consumed or expired confirmation ID.
    Expected: Backend gate rejects response attempt.
    """
    res = close_permission_gate.request_close_permission(target="Calculator", timeout_seconds=0.1)
    cid = res["confirmation_id"]

    # Attempt to respond to an already consumed confirmation
    second_attempt = close_permission_gate.respond(cid, "allow")
    assert second_attempt["success"] is False
    assert "already" in second_attempt["error"].lower() or "not found" in second_attempt["error"].lower()


def test_rest_api_confirmation_endpoints(client):
    """Verify REST API /confirmations/pending and /confirmations/{id}/respond endpoints."""
    # Fetch pending
    res = client.get("/api/agent/confirmations/pending")
    assert res.status_code == 200
    assert "confirmations" in res.json()
