"""Network utilities for discovering LAN IP addresses."""

import socket
import psutil
from typing import List
from backend.utils.logger import logger

# Interface keywords to ignore (virtual / docker / vpn / loopback)
IGNORE_TERMS = [
    "loopback", "virtual", "vethernet", "wsl", "vmnet", "docker",
    "tap", "tun", "vpn", "vbox", "host-only", "bluetooth"
]


def get_all_lan_ips() -> List[str]:
    """
    Return a list of all active, non-virtual LAN IPv4 addresses on the laptop.
    Filters out loopback, link-local (169.254.x.x), and virtual adapters.
    """
    valid_ips: List[str] = []
    try:
        for interface_name, addrs in psutil.net_if_addrs().items():
            lower_name = interface_name.lower()
            if any(term in lower_name for term in IGNORE_TERMS):
                continue

            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    if not ip.startswith("127.") and not ip.startswith("169.254."):
                        if ip not in valid_ips:
                            valid_ips.append(ip)
    except Exception as e:
        logger.debug(f"Interface scan error: {e}")

    # Fallback via socket probe if no interfaces matched filter
    if not valid_ips:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                    valid_ips.append(ip)
        except Exception:
            pass

    return valid_ips or ["127.0.0.1"]


def get_local_ip() -> str:
    """
    Automatically determine the primary LAN IPv4 address (Wi-Fi or Ethernet).
    """
    # Method 1: Active UDP probe to public DNS
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception as e:
        logger.debug(f"Socket probe failed to find local IP: {e}")

    # Method 2: Inspect active network interfaces
    ips = get_all_lan_ips()
    for ip in ips:
        if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
            return ip

    return ips[0] if ips else "127.0.0.1"
