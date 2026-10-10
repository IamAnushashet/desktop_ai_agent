"""QR code generator module for LAN-specific remote pairing."""

import base64
import io
import qrcode
from backend.utils.logger import logger


def generate_qr_base64(url: str) -> str:
    """
    Generate QR code for a given LAN URL as a PNG Base64 data URI string.
    Example output: "data:image/png;base64,iVBORw0..."
    """
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        b64_str = base64.b64encode(png_bytes).decode("ascii")
        return f"data:image/png;base64,{b64_str}"
    except Exception as e:
        logger.error(f"Failed to generate QR code for URL {url}: {e}")
        return ""
