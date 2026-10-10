"""Permission model and Global Close Permission Gate for Desktop AI Agent."""

import time
import uuid
import threading
from enum import Enum
from typing import Set, Dict, Any, List, Optional, Callable
from backend.utils.logger import logger


class Permission(str, Enum):
    """Granular permissions for remote client operations."""
    SCREEN_VIEW = "SCREEN_VIEW"
    MOUSE_CONTROL = "MOUSE_CONTROL"
    KEYBOARD_CONTROL = "KEYBOARD_CONTROL"
    WINDOW_CONTROL = "WINDOW_CONTROL"


# Default permissions assigned to an authenticated mobile session
DEFAULT_PERMISSIONS: Set[Permission] = {
    Permission.SCREEN_VIEW,
    Permission.MOUSE_CONTROL,
    Permission.KEYBOARD_CONTROL,
    Permission.WINDOW_CONTROL,
}


def has_permission(granted_permissions: Set[Permission], required_permission: Permission) -> bool:
    """Check if the granted permissions include the required permission."""
    return required_permission in granted_permissions


class ClosePermissionGate:
    """
    Central Global Permission Gate for all window and application close operations.
    Enforces user confirmation before any application or window is allowed to close.
    """

    def __init__(self):
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._history: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._broadcast_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def register_broadcast_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback (e.g. WebSocket notifier) when a permission request is issued."""
        with self._lock:
            if callback not in self._broadcast_callbacks:
                self._broadcast_callbacks.append(callback)

    def unregister_broadcast_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Unregister a broadcast callback."""
        with self._lock:
            if callback in self._broadcast_callbacks:
                self._broadcast_callbacks.remove(callback)

    def _notify_callbacks(self, request_data: Dict[str, Any]):
        """Internal helper to notify all registered listeners of a new request."""
        callbacks = list(self._broadcast_callbacks)
        for cb in callbacks:
            try:
                cb(request_data)
            except Exception as e:
                logger.warning(f"[PERMISSION GATE] Broadcast callback error: {e}")

    def request_close_permission(
        self,
        target: str,
        targets: Optional[List[str]] = None,
        timeout_seconds: float = 60.0
    ) -> Dict[str, Any]:
        """
        Request explicit user permission before closing an application/window.
        Blocks execution until user responds or request times out (default 60s).
        
        Args:
            target: Main target application name (e.g. 'Google Chrome', 'Microsoft Word').
            targets: Optional list of target app names if closing multiple applications.
            timeout_seconds: Expiration period in seconds (default 60s).
            
        Returns:
            Dict containing 'approved' (bool), 'status' ('approved'|'rejected'|'expired'), 'confirmation_id', and 'reason'.
        """
        confirmation_id = str(uuid.uuid4())[:8]
        event = threading.Event()
        now = time.time()
        expires_at = now + timeout_seconds

        target_name = target.strip() if target and target.strip() else "Desktop Application"
        target_list = targets if (targets and isinstance(targets, list)) else [target_name]

        req_info = {
            "confirmation_id": confirmation_id,
            "type": "close_window",
            "target": target_name,
            "targets": target_list,
            "status": "pending",
            "created_at": now,
            "expires_at": expires_at,
            "timeout_seconds": int(timeout_seconds),
            "consumed": False,
            "_event": event,
        }

        with self._lock:
            self._pending[confirmation_id] = req_info

        logger.info(f"[CLOSE GATE REQUEST] [{confirmation_id}] Asking permission to close '{target_name}' (Expires in {int(timeout_seconds)}s)")

        # Notify UI/WebSocket listeners
        public_data = self._to_public_dict(req_info)
        self._notify_callbacks(public_data)

        # Block until user responds or timeout occurs
        got_response = event.wait(timeout=timeout_seconds)

        with self._lock:
            current_info = self._pending.pop(confirmation_id, None)
            if not current_info:
                current_info = self._history.get(confirmation_id, req_info)

            if not got_response or current_info.get("status") == "pending":
                current_info["status"] = "expired"
                current_info["consumed"] = True
                logger.warning(f"[CLOSE GATE EXPIRED] [{confirmation_id}] Request to close '{target_name}' expired after {int(timeout_seconds)}s -> DENIED")

            current_info["consumed"] = True
            self._history[confirmation_id] = current_info
            status = current_info.get("status", "expired")
            approved = (status == "approved")

            reason = "Approved by user" if approved else (
                "Cancelled by user" if status == "rejected" else f"Request expired after {int(timeout_seconds)} seconds"
            )

            return {
                "approved": approved,
                "status": status,
                "confirmation_id": confirmation_id,
                "target": target_name,
                "reason": reason,
            }

    def respond(self, confirmation_id: str, action: str) -> Dict[str, Any]:
        """
        Submit a user decision ('allow'/'approve' or 'cancel'/'reject') for a pending confirmation.
        
        Args:
            confirmation_id: The ID of the pending confirmation request.
            action: 'allow', 'approve', 'cancel', or 'reject'.
            
        Returns:
            Dict with 'success' (bool), 'confirmation_id', and 'status'.
        """
        clean_action = action.lower().strip()
        is_approve = clean_action in ["allow", "approve", "yes"]
        is_reject = clean_action in ["cancel", "reject", "no", "deny"]

        if not is_approve and not is_reject:
            return {
                "success": False,
                "error": f"Invalid response action '{action}'. Expected 'allow' or 'cancel'."
            }

        with self._lock:
            req_info = self._pending.get(confirmation_id)

            if not req_info:
                # Check history to see if already consumed or expired
                past = self._history.get(confirmation_id)
                if past:
                    return {
                        "success": False,
                        "error": f"Confirmation '{confirmation_id}' has already been consumed or expired (status: {past.get('status')})."
                    }
                return {
                    "success": False,
                    "error": f"Confirmation ID '{confirmation_id}' not found or no longer active."
                }

            if req_info.get("consumed") or req_info.get("status") != "pending":
                return {
                    "success": False,
                    "error": f"Confirmation '{confirmation_id}' was already processed (status: {req_info.get('status')})."
                }

            # Check expiration
            if time.time() > req_info.get("expires_at", 0):
                req_info["status"] = "expired"
                req_info["consumed"] = True
                event = req_info.get("_event")
                if event:
                    event.set()
                return {
                    "success": False,
                    "error": f"Confirmation '{confirmation_id}' expired."
                }

            # Update status
            new_status = "approved" if is_approve else "rejected"
            req_info["status"] = new_status
            req_info["consumed"] = True
            event = req_info.get("_event")
            if event:
                event.set()

            logger.info(f"[CLOSE GATE DECISION] [{confirmation_id}] User set status to '{new_status}' for target '{req_info.get('target')}'")

            return {
                "success": True,
                "confirmation_id": confirmation_id,
                "status": new_status,
                "target": req_info.get("target"),
            }

    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """Return list of active pending confirmation requests for UI rendering."""
        now = time.time()
        result = []
        with self._lock:
            for cid, info in list(self._pending.items()):
                if info.get("status") == "pending" and now < info.get("expires_at", 0):
                    result.append(self._to_public_dict(info))
                elif now >= info.get("expires_at", 0):
                    info["status"] = "expired"
                    info["consumed"] = True
                    event = info.get("_event")
                    if event:
                        event.set()
        return result

    def get_confirmation_status(self, confirmation_id: str) -> Optional[Dict[str, Any]]:
        """Check status of a specific confirmation request by ID."""
        with self._lock:
            info = self._pending.get(confirmation_id) or self._history.get(confirmation_id)
            if info:
                return self._to_public_dict(info)
            return None

    def _to_public_dict(self, req_info: Dict[str, Any]) -> Dict[str, Any]:
        """Strip internal non-serializable fields (like threading.Event)."""
        now = time.time()
        rem_sec = max(0, int(req_info.get("expires_at", 0) - now))
        return {
            "confirmation_id": req_info.get("confirmation_id"),
            "type": req_info.get("type", "close_window"),
            "target": req_info.get("target"),
            "targets": req_info.get("targets", [req_info.get("target")]),
            "status": req_info.get("status", "pending"),
            "created_at": req_info.get("created_at"),
            "expires_at": req_info.get("expires_at"),
            "timeout_seconds": req_info.get("timeout_seconds", 60),
            "remaining_seconds": rem_sec,
        }


# Global Close Permission Gate singleton instance
close_permission_gate = ClosePermissionGate()

