"""Automated test suite for Desktop AI Agent Remote Control.

Mocks all physical OS actions so no mouse or keyboard inputs occur during test execution.
"""

import time
from unittest.mock import patch, MagicMock
import pytest
from starlette.testclient import TestClient

from backend.config.settings import Settings
from backend.control.mouse import MouseController
from backend.control.keyboard import KeyboardController
from backend.control.window import WindowController
from backend.screen.capture import ScreenCapture
from backend.main import app
from backend.remote.protocol import (
    AuthMessage,
    MouseMoveMessage,
    MouseClickMessage,
    ScrollMessage,
    KeyMessage,
    HotkeyMessage,
)
from backend.remote.session import SessionManager, Session
from backend.security.authentication import AuthManager
from backend.security.permissions import Permission, has_permission, DEFAULT_PERMISSIONS
from backend.security.validator import (
    validate_coordinate,
    validate_delta,
    validate_key,
    validate_hotkey,
    validate_button,
    RateLimiter,
)


# --- 1. Pairing Code Generation Tests ---

def test_pairing_code_generation():
    auth = AuthManager(expiry_seconds=300)
    code = auth.generate_pairing_code()
    assert isinstance(code, str)
    assert len(code) == 6
    assert code.isdigit()
    assert 100000 <= int(code) <= 999999
    assert auth.get_pairing_code() == code


def test_pairing_code_expiration():
    auth = AuthManager(expiry_seconds=1)
    code = auth.generate_pairing_code()
    assert auth.get_pairing_code() == code

    # Artificially shift timestamp back
    auth._code_created_at = time.time() - 2
    assert auth.get_pairing_code() is None

    # Verification of expired code must fail
    success, reason = auth.verify_and_consume_code(code)
    assert success is False
    assert "expired" in reason.lower()


# --- 2. Authentication Flow Tests ---

def test_successful_authentication():
    auth = AuthManager(expiry_seconds=300)
    code = auth.generate_pairing_code()

    success, token = auth.verify_and_consume_code(code)
    assert success is True
    assert isinstance(token, str)
    assert len(token) > 20

    # Code must be invalidated after first use (prevent replay)
    success_again, _ = auth.verify_and_consume_code(code)
    assert success_again is False


def test_failed_authentication():
    auth = AuthManager(expiry_seconds=300)
    auth.generate_pairing_code()

    success, reason = auth.verify_and_consume_code("000000")
    assert success is False
    assert "invalid" in reason.lower()


# --- 3. Session Management Tests ---

def test_session_creation_and_permissions():
    mgr = SessionManager()
    token = "test_token_123"
    session = mgr.register_session(token=token, client_ip="192.168.1.50")

    assert session.token == token
    assert session.client_ip == "192.168.1.50"
    assert mgr.validate_token(token) is True
    assert has_permission(session.permissions, Permission.MOUSE_CONTROL)
    assert has_permission(session.permissions, Permission.KEYBOARD_CONTROL)
    assert has_permission(session.permissions, Permission.SCREEN_VIEW)
    assert has_permission(session.permissions, Permission.WINDOW_CONTROL)


def test_session_expiration():
    mgr = SessionManager()
    token = "expiring_token_456"
    session = mgr.register_session(token=token, client_ip="192.168.1.50")

    # Shift last activity past timeout
    session.last_activity = time.time() - 2000
    assert session.is_expired(timeout_seconds=1800) is True
    assert mgr.get_session(token) is None


def test_single_active_controller_policy():
    mgr = SessionManager()
    tok1 = "token_controller_1"
    tok2 = "token_controller_2"

    mgr.register_session(tok1, "192.168.1.101")
    mgr.register_session(tok2, "192.168.1.102")

    mock_ws1 = MagicMock()
    mock_ws2 = MagicMock()

    # Controller 1 connects
    conn1, err1 = mgr.connect_controller(tok1, mock_ws1)
    assert conn1 is True
    assert err1 is None

    # Controller 2 tries to connect simultaneously -> must be rejected
    conn2, err2 = mgr.connect_controller(tok2, mock_ws2)
    assert conn2 is False
    assert "controlling" in err2.lower() or "already" in err2.lower()

    # Disconnect 1
    mgr.disconnect_controller(tok1)

    # Now Controller 2 can connect
    conn2_retry, _ = mgr.connect_controller(tok2, mock_ws2)
    assert conn2_retry is True


# --- 4. Coordinate & Security Validation Tests ---

def test_coordinate_validation():
    assert validate_coordinate(0.0) is True
    assert validate_coordinate(0.5) is True
    assert validate_coordinate(1.0) is True

    # Out of range
    assert validate_coordinate(-0.01) is False
    assert validate_coordinate(1.01) is False
    assert validate_coordinate("invalid") is False
    assert validate_coordinate(None) is False


def test_coordinate_conversion():
    mouse = MouseController()

    with patch.object(mouse, "get_screen_size", return_value=(1920, 1080)):
        # Top-left corner
        px, py = mouse.to_screen_coordinates(0.0, 0.0)
        assert px == 0 and py == 0

        # Center
        px, py = mouse.to_screen_coordinates(0.5, 0.5)
        assert abs(px - 960) <= 1
        assert abs(py - 540) <= 1

        # Bottom-right corner
        px, py = mouse.to_screen_coordinates(1.0, 1.0)
        assert px == 1919 and py == 1079


def test_validator_rules():
    # Mouse buttons
    assert validate_button("left") is True
    assert validate_button("right") is True
    assert validate_button("middle") is True
    assert validate_button("invalid_btn") is False

    # Scroll delta
    assert validate_delta(5.0) is True
    assert validate_delta(-10.0) is True
    assert validate_delta(5000.0) is False

    # Keyboard validation
    assert validate_key("a") is True
    assert validate_key("enter") is True
    assert validate_key("ctrl") is True
    assert validate_key("dangerous_command_exec") is False

    # Hotkey validation
    assert validate_hotkey(["ctrl", "c"]) is True
    assert validate_hotkey(["alt", "tab"]) is True
    assert validate_hotkey(["ctrl", "unknown_bad_key"]) is False


def test_rate_limiter():
    limiter = RateLimiter(max_per_second=5)
    for _ in range(5):
        assert limiter.allow() is True
    # 6th request within same second must be rejected
    assert limiter.allow() is False


# --- 5. Protocol Message Validation Tests ---

def test_protocol_models():
    # Auth
    auth = AuthMessage(token="valid_token")
    assert auth.type == "auth"

    # Mouse move normalized
    move = MouseMoveMessage(x=0.25, y=0.75)
    assert move.x == 0.25
    assert move.y == 0.75

    # Invalid coordinates in protocol
    with pytest.raises(Exception):
        MouseMoveMessage(x=1.5, y=0.5)

    # Click
    click = MouseClickMessage(button="left")
    assert click.button == "left"

    # Scroll
    scroll = ScrollMessage(delta=-3.5)
    assert scroll.delta == -3.5


# --- 6. Controller Interfaces Unit Tests (Mocked OS Actions) ---

@patch("backend.control.mouse.pyautogui")
def test_mouse_controller_actions(mock_pag):
    mouse = MouseController(sensitivity=1.5)
    mock_pag.size.return_value = (1920, 1080)

    # Move normalized
    res = mouse.move(0.5, 0.5, normalized=True)
    assert res is True
    mock_pag.moveTo.assert_called_with(960, 540)

    # Move relative with sensitivity
    res = mouse.move_relative(10, 20)
    assert res is True
    mock_pag.moveRel.assert_called_with(15, 30)

    # Click
    res = mouse.click("right")
    assert res is True
    mock_pag.click.assert_called_with(button="right")

    # Double click
    res = mouse.double_click("left")
    assert res is True
    mock_pag.doubleClick.assert_called_with(button="left")

    # Mouse down / up
    mouse.mouse_down("left")
    mock_pag.mouseDown.assert_called_with(button="left")
    mouse.mouse_up("left")
    mock_pag.mouseUp.assert_called_with(button="left")

    # Drag
    mouse.drag(0.2, 0.4, normalized=True)
    mock_pag.dragTo.assert_called()

    # Scroll
    mouse.scroll(-5)
    mock_pag.scroll.assert_called()


@patch("backend.control.keyboard.pyautogui")
def test_keyboard_controller_actions(mock_pag):
    kb = KeyboardController()

    # Press key
    res = kb.press("enter")
    assert res is True
    mock_pag.press.assert_called_with("enter")

    # Hotkey
    res = kb.hotkey(["ctrl", "c"])
    assert res is True
    mock_pag.hotkey.assert_called_with("ctrl", "c")

    # Write text
    res = kb.write("Hello World")
    assert res is True
    mock_pag.write.assert_called_with("Hello World", interval=0.005)


@patch("backend.control.window.gw")
def test_window_controller_actions(mock_gw):
    wc = WindowController()
    mock_win = MagicMock()
    mock_win.title = "Test Window"
    mock_win.left = 100
    mock_win.top = 100
    mock_win.width = 800
    mock_win.height = 600
    mock_win.isMaximized = False
    mock_win.isMinimized = False
    mock_gw.getActiveWindow.return_value = mock_win

    info = wc.get_active_window()
    assert info["title"] == "Test Window"

    assert wc.minimize() is True
    mock_win.minimize.assert_called_once()

    assert wc.maximize() is True
    mock_win.maximize.assert_called_once()

    assert wc.restore() is True
    mock_win.restore.assert_called_once()


# --- 7. FastAPI REST & WebSocket Endpoints Tests ---

def test_rest_health_endpoint():
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_rest_remote_info():
    client = TestClient(app)
    res = client.get("/remote/info")
    assert res.status_code == 200
    data = res.json()
    assert "name" in data
    assert "ip" in data
    assert "port" in data
    assert "status" in data


def test_rest_pairing_endpoint():
    from backend.security.authentication import auth_manager
    code = auth_manager.generate_pairing_code()

    client = TestClient(app)

    # Test invalid code
    bad_res = client.post("/remote/pair", json={"code": "000000"})
    assert bad_res.status_code == 401

    # Test valid code
    good_res = client.post("/remote/pair", json={"code": code})
    assert good_res.status_code == 200
    json_data = good_res.json()
    assert json_data["success"] is True
    assert "session_token" in json_data


def test_unauthenticated_websocket_rejected():
    client = TestClient(app)
    with client.websocket_connect("/ws/remote") as ws:
        # Send non-auth message as first message
        ws.send_json({"type": "mouse_move", "x": 0.5, "y": 0.5})
        res = ws.receive_json()
        assert res["type"] == "error"
        assert "auth" in res["message"].lower() or "invalid" in res["message"].lower()


def test_authenticated_websocket_flow():
    from backend.security.authentication import auth_manager
    from backend.remote.session import session_manager

    # Generate and pair
    code = auth_manager.generate_pairing_code()
    client = TestClient(app)
    pair_res = client.post("/remote/pair", json={"code": code})
    token = pair_res.json()["session_token"]

    with client.websocket_connect("/ws/remote") as ws:
        # Send valid auth
        ws.send_json({"type": "auth", "token": token})

        # Expect status: connected
        msg = ws.receive_json()
        assert msg["type"] == "status"
        assert msg["status"] == "connected"

        # Ping-Pong
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        # May receive pong or screen frame; verify we can receive pong
        if pong["type"] == "screen":
            pong = ws.receive_json()
        assert pong["type"] in ("pong", "screen")


# --- 8. LAN QR Code & Automatic QR Pairing Tests ---

def test_qr_code_generation():
    from backend.remote.qr import generate_qr_base64
    qr_b64 = generate_qr_base64("http://192.168.1.38:8000/pair?code=123456")
    assert isinstance(qr_b64, str)
    assert qr_b64.startswith("data:image/png;base64,")


def test_qr_endpoints_flow():
    client = TestClient(app)

    # Test /remote/qr
    res = client.get("/remote/qr")
    assert res.status_code == 200
    data = res.json()
    assert "qr_base64" in data
    assert "pairing_code" in data
    assert "pairing_url" in data
    assert "expires_in" in data

    code = data["pairing_code"]

    # Test /pairing HTML endpoint
    pairing_page = client.get("/pairing")
    assert pairing_page.status_code == 200
    assert "Desktop AI Agent - QR Pairing" in pairing_page.text

    # Test automatic QR pairing /pair?code=...
    pair_res = client.get(f"/pair?code={code}")
    assert pair_res.status_code == 200
    assert "Pairing Verified!" in pair_res.text
    assert "sessionStorage.setItem('desktop_remote_token'" in pair_res.text

