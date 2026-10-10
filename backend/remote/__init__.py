"""Remote control package for Desktop AI Agent."""

from backend.remote.server import handle_remote_websocket
from backend.remote.session import session_manager, Session
from backend.remote.protocol import ClientMessage, ScreenMessage, StatusMessage, ErrorMessage

__all__ = [
    "handle_remote_websocket",
    "session_manager",
    "Session",
    "ClientMessage",
    "ScreenMessage",
    "StatusMessage",
    "ErrorMessage",
]
