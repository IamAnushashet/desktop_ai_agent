"""System tools for launching Windows applications."""

import subprocess
from langchain_core.tools import tool
from backend.utils.logger import logger


@tool
def run_system_app(app_name: str) -> str:
    """
    Launch a Windows desktop application by executable name or alias.
    
    Args:
        app_name: Application name or command (e.g. 'chrome', 'notepad', 'calc', 'explorer', 'cmd', 'mspaint').
    """
    name = app_name.lower().strip()

    # FORCE TERMINATION GUARD: Prevent bypassing permission gate via kill/taskkill
    blocked_keywords = ["taskkill", "kill", "stop-process", "terminate", "pskill", "tskill"]
    if any(k in name for k in blocked_keywords):
        err_msg = "Error: Direct process termination via command line is strictly blocked. All application closing actions must go through the Global Close Permission Gate."
        logger.warning(f"[SECURITY BLOCKED] {err_msg}")
        return err_msg

    cmd_map = {
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "paint": "mspaint.exe",
    }
    executable = cmd_map.get(name, f"{name}.exe" if not name.endswith(".exe") else name)

    try:
        subprocess.Popen([executable], shell=True)
        logger.info(f"[TOOL] Launched system app '{executable}'")
        return f"Successfully launched system application '{app_name}'"
    except Exception as e:
        logger.error(f"[TOOL ERROR] Failed launching system app '{app_name}': {e}")
        return f"Error launching application '{app_name}': {str(e)}"
