"""Session management for remote mobile clients."""

import time
from typing import Dict, Optional, Set, Tuple
from fastapi import WebSocket
from backend.config.settings import settings
from backend.security.permissions import Permission, DEFAULT_PERMISSIONS
from backend.security.validator import RateLimiter
from backend.utils.logger import logger


class Session:
    """Represents an authenticated mobile controller session."""

    def __init__(self, token: str, client_ip: str, permissions: Optional[Set[Permission]] = None):
        self.token = token
        self.client_ip = client_ip
        self.created_at = time.time()
        self.last_activity = time.time()
        self.permissions: Set[Permission] = permissions or set(DEFAULT_PERMISSIONS)
        self.websocket: Optional[WebSocket] = None
        self.is_connected = False
        self.rate_limiter = RateLimiter(max_per_second=120)

    def is_expired(self, timeout_seconds: int = settings.SESSION_TIMEOUT) -> bool:
        """Check if session has timed out due to inactivity."""
        return (time.time() - self.last_activity) > timeout_seconds

    def touch(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()


class SessionManager:
    """Manages active sessions with single-active-controller enforcement."""

    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._active_session_token: Optional[str] = None

    def register_session(self, token: str, client_ip: str) -> Session:
        """Register a newly paired session token."""
        # Purge any expired sessions first
        self.clean_expired_sessions()

        session = Session(token=token, client_ip=client_ip)
        self._sessions[token] = session
        logger.info(f"Registered new session for IP {client_ip}")
        return session

    def get_session(self, token: str) -> Optional[Session]:
        """Retrieve session by token if valid and not expired."""
        session = self._sessions.get(token)
        if not session:
            return None
        if session.is_expired():
            logger.info(f"Session expired for client {session.client_ip}")
            self.terminate_session(token)
            return None
        return session

    def validate_token(self, token: str) -> bool:
        """Check whether a session token is currently valid."""
        return self.get_session(token) is not None

    def connect_controller(self, token: str, websocket: WebSocket) -> Tuple[bool, Optional[str]]:
        """
        Attach WebSocket to session.
        Enforces single active controller policy.
        """
        session = self.get_session(token)
        if not session:
            return False, "Invalid or expired session token"

        # Check if another controller is currently connected
        if self._active_session_token and self._active_session_token != token:
            current_active = self._sessions.get(self._active_session_token)
            if current_active and current_active.is_connected:
                logger.warning(
                    f"Rejected connection attempt from {session.client_ip}: "
                    f"Controller already active from {current_active.client_ip}"
                )
                return False, "Another mobile device is currently controlling the laptop"

        session.websocket = websocket
        session.is_connected = True
        session.touch()
        self._active_session_token = token
        logger.info(f"Mobile controller connected from {session.client_ip}")
        return True, None

    def disconnect_controller(self, token: str):
        """Handle disconnection of controller."""
        session = self._sessions.get(token)
        if session:
            session.is_connected = False
            session.websocket = None
            session.touch()
            if self._active_session_token == token:
                self._active_session_token = None
            logger.info(f"Mobile controller disconnected: {session.client_ip}")

    def terminate_session(self, token: str):
        """Terminate and remove session."""
        self.disconnect_controller(token)
        if token in self._sessions:
            del self._sessions[token]

    def is_controller_connected(self) -> bool:
        """Check if there is an active connected controller."""
        if not self._active_session_token:
            return False
        active = self._sessions.get(self._active_session_token)
        return bool(active and active.is_connected)

    def clean_expired_sessions(self):
        """Remove any sessions that exceeded timeout."""
        expired = [token for token, sess in self._sessions.items() if sess.is_expired()]
        for token in expired:
            self.terminate_session(token)


# Shared session manager instance
session_manager = SessionManager()
