"""Screen capture module using MSS with JPEG compression and change detection."""

import base64
import ctypes
import hashlib
import io
import threading
from typing import Optional, Tuple, Dict, Any
from PIL import Image
import mss

from backend.config.settings import settings
from backend.utils.logger import logger


def ensure_thread_desktop():
    """Ensure the calling thread is attached to the active Default desktop."""
    try:
        user32 = ctypes.windll.user32
        h_default = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_default:
            user32.SetThreadDesktop(h_default)
    except Exception as e:
        logger.debug(f"Unable to switch thread desktop: {e}")


class ScreenCapture:
    """Captures and compresses Windows desktop frames for remote streaming."""

    def __init__(
        self,
        max_width: int = settings.SCREEN_MAX_WIDTH,
        quality: int = settings.SCREEN_QUALITY,
        fps: int = settings.SCREEN_FPS,
    ):
        self.max_width = max_width
        self.quality = quality
        self.fps = fps
        self._last_hash: Optional[str] = None
        self._last_raw_hash: Optional[str] = None
        self._lock = threading.Lock()
        self._sct: Optional[mss.MSS] = None

    def _get_sct(self) -> mss.MSS:
        """Get or initialize MSS instance for current thread."""
        ensure_thread_desktop()
        if self._sct is None:
            self._sct = mss.MSS()
        return self._sct

    def get_screen_size(self) -> Tuple[int, int]:
        """Return primary desktop screen dimensions."""
        try:
            sct = self._get_sct()
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            return int(mon["width"]), int(mon["height"])
        except Exception as e:
            logger.error(f"Failed to get screen size: {e}")
            return (1920, 1080)

    def capture_frame(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        Capture desktop screen, resize if larger than max_width, compress to JPEG.
        Returns dict with base64 data and metadata, or None if frame is unchanged.
        """
        try:
            with self._lock:
                sct = self._get_sct()
                mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                shot = sct.grab(mon)

                orig_w, orig_h = shot.size
                raw_bgra = shot.bgra

                # Fast uniform change detection across entire screen
                raw_sample = raw_bgra[::128]
                raw_hash = hashlib.md5(raw_sample).hexdigest()
                if not force and raw_hash == self._last_raw_hash:
                    return None
                self._last_raw_hash = raw_hash

                # Convert raw BGRA to PIL Image
                img = Image.frombytes("RGB", (orig_w, orig_h), raw_bgra, "raw", "BGRX")

                # Resize if exceeding max_width using ultra-fast BOX resampling
                if orig_w > self.max_width:
                    ratio = self.max_width / float(orig_w)
                    target_h = int(round(orig_h * ratio))
                    img = img.resize((self.max_width, target_h), Image.Resampling.BOX)

                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=self.quality, optimize=False)
                jpeg_bytes = buf.getvalue()

                b64_str = base64.b64encode(jpeg_bytes).decode("ascii")

                return {
                    "data": b64_str,
                    "width": img.width,
                    "height": img.height,
                    "orig_width": orig_w,
                    "orig_height": orig_h,
                }
        except Exception as e:
            logger.error(f"Error capturing screen: {e}")
            return None

    def close(self):
        """Clean up MSS resources."""
        if self._sct:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None


# Shared screen capture instance
screen_capture = ScreenCapture()
