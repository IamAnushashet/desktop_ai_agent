"""Authentication and pairing manager for Desktop AI Agent."""

import secrets
import time
from typing import Optional, Tuple
from backend.config.settings import settings
from backend.utils.logger import logger


class AuthManager:
    """Manages pairing code generation, expiration, and session token issuance."""

    def __init__(self, expiry_seconds: Optional[int] = None):
        self.expiry_seconds = expiry_seconds or settings.PAIRING_CODE_EXPIRY
        self._current_code: Optional[str] = None
        self._code_created_at: float = 0.0

    def generate_pairing_code(self) -> str:
        """
        Generate a cryptographically secure 6-digit pairing code.
        Replaces any prior pairing code.
        """
        self._current_code = f"{secrets.randbelow(900000) + 100000:06d}"
        self._code_created_at = time.time()
        logger.info(f"[AUTH] Generated new pairing code (valid for {self.expiry_seconds}s)")
        return self._current_code

    def is_expired(self) -> bool:
        """Check whether current pairing code has expired."""
        if not self._current_code:
            return True
        return (time.time() - self._code_created_at) > self.expiry_seconds

    def get_pairing_code(self) -> Optional[str]:
        """Return the current pairing code if not expired, else None."""
        if not self._current_code or self.is_expired():
            return None
        return self._current_code

    def get_or_create_active_code(self) -> str:
        """
        Return the current valid pairing code.
        If expired or missing, automatically generate a fresh 5-minute code.
        """
        if not self._current_code or self.is_expired():
            return self.generate_pairing_code()
        return self._current_code

    def get_remaining_seconds(self) -> int:
        """Return remaining seconds of current pairing code validity."""
        if not self._current_code or self.is_expired():
            return 0
        elapsed = time.time() - self._code_created_at
        remaining = int(self.expiry_seconds - elapsed)
        return max(0, remaining)

    def verify_and_consume_code(self, submitted_code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate submitted code against current active code.
        If valid: invalidate the pairing code and return (True, session_token).
        If invalid or expired: return (False, error_reason).
        """
        if not self._current_code:
            logger.warning("[AUTH] Authentication failed: No active pairing code.")
            return False, "No active pairing code. Please generate a new one."

        if self.is_expired():
            self._current_code = None
            logger.warning("[AUTH] Authentication failed: Pairing code expired.")
            return False, "Pairing code has expired."

        # Constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(str(self._current_code).strip(), str(submitted_code).strip()):
            logger.warning("[AUTH] Authentication failed: Invalid pairing code submitted.")
            return False, "Invalid pairing code."

        # Code matched! Invalidate code to prevent replay attacks
        self._current_code = None
        session_token = secrets.token_urlsafe(32)
        logger.info("[AUTH] Pairing authentication successful! Issued new session token.")
        return True, session_token


# Global authentication manager instance
auth_manager = AuthManager()
