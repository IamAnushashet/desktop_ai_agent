"""Security package for Desktop AI Agent."""

from backend.security.authentication import auth_manager, AuthManager
from backend.security.permissions import Permission, DEFAULT_PERMISSIONS, has_permission
from backend.security.validator import (
    validate_coordinate,
    validate_delta,
    validate_key,
    validate_hotkey,
    validate_button,
    RateLimiter,
)

__all__ = [
    "auth_manager",
    "AuthManager",
    "Permission",
    "DEFAULT_PERMISSIONS",
    "has_permission",
    "validate_coordinate",
    "validate_delta",
    "validate_key",
    "validate_hotkey",
    "validate_button",
    "RateLimiter",
]
