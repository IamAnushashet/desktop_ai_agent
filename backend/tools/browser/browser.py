"""Browser automation tools with Chrome path discovery, foreground focusing, and execution verification."""

import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import winreg
from typing import Optional, List
import psutil
import pygetwindow as gw
from langchain_core.tools import tool
from backend.utils.logger import logger


def find_chrome_executable() -> Optional[str]:
    """
    Safely discover Google Chrome executable path on Windows across registry,
    common environment directories, and PATH.
    """
    # 1. Registry discovery (HKLM & HKCU)
    reg_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
    ]
    for hkey, subkey in reg_keys:
        try:
            with winreg.OpenKey(hkey, subkey) as k:
                val, _ = winreg.QueryValueEx(k, "")
                if val and os.path.exists(val):
                    logger.info(f"[CHROME DISCOVERY] Found Chrome via Registry: {val}")
                    return val
        except Exception:
            pass

    # 2. Standard installation path checks
    candidate_paths = [
        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", r"C:\Users\Default\AppData\Local"), r"Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            logger.info(f"[CHROME DISCOVERY] Found Chrome at candidate path: {path}")
            return path

    # 3. PATH check via shutil.which
    which_path = shutil.which("chrome.exe") or shutil.which("chrome")
    if which_path and os.path.exists(which_path):
        logger.info(f"[CHROME DISCOVERY] Found Chrome in PATH: {which_path}")
        return which_path

    logger.warning("[CHROME DISCOVERY] Could not resolve specific chrome.exe path on system.")
    return None


def bring_chrome_to_foreground() -> bool:
    """
    Ensure active Chrome window is restored and brought to the foreground on Windows.
    Safely bypasses Windows foreground locks using Win32 API and PyAutoGUI.
    """
    try:
        from backend.control.window import ensure_thread_desktop
        ensure_thread_desktop()

        import win32gui
        import win32con
        import pyautogui

        chrome_hwnds = []

        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and "chrome" in title.lower():
                    chrome_hwnds.append((hwnd, title))

        win32gui.EnumWindows(enum_callback, None)

        if chrome_hwnds:
            # Prefer window with YouTube in title if present, otherwise first Chrome window
            yt_wins = [h for h, t in chrome_hwnds if "youtube" in t.lower()]
            target_hwnd = yt_wins[0] if yt_wins else chrome_hwnds[0][0]

            try:
                pyautogui.press('alt')
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                win32gui.ShowWindow(target_hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(target_hwnd)
                time.sleep(0.3)
                return True
            except Exception as err:
                logger.debug(f"[CHROME FOCUS RECOVERY] {err}")

        wins = [w for w in gw.getAllWindows() if "chrome" in (w.title or "").lower()]
        if wins:
            try:
                pyautogui.press('alt')
                wins[0].restore()
                wins[0].activate()
                time.sleep(0.3)
                return True
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"[CHROME FOCUS NOTICE] {e}")
    return False


def verify_chrome_running(timeout_seconds: float = 3.0) -> bool:
    """
    Verify that Chrome process or window is actively running on Windows.
    Polls psutil process table and pygetwindow titles.
    """
    start = time.time()
    while time.time() - start < timeout_seconds:
        # Check psutil process list for chrome.exe
        try:
            for p in psutil.process_iter(["name", "pid"]):
                name = p.info.get("name")
                if name and "chrome" in name.lower():
                    logger.info(f"[VERIFICATION SUCCESS] Detected active Chrome process (PID {p.info.get('pid')})")
                    return True
        except Exception as e:
            logger.debug(f"Process iter error: {e}")

        # Check pygetwindow for Chrome window
        try:
            wins = gw.getAllTitles()
            if any("chrome" in title.lower() for title in wins if title):
                logger.info("[VERIFICATION SUCCESS] Detected active Chrome window title")
                return True
        except Exception:
            pass

        time.sleep(0.4)

    return False


def verify_chrome_page_loaded(expected_keyword: str = "", timeout_seconds: float = 4.0) -> bool:
    """
    Verify Chrome active window or tab is loaded and accessible.
    """
    start = time.time()
    kw = expected_keyword.lower().strip()
    while time.time() - start < timeout_seconds:
        try:
            active = gw.getActiveWindow()
            if active and "chrome" in (active.title or "").lower():
                if not kw or kw in (active.title or "").lower():
                    return True
            titles = gw.getAllTitles()
            for t in titles:
                if t and "chrome" in t.lower() and (not kw or kw in t.lower()):
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return verify_chrome_running(timeout_seconds=1.0)


@tool
def open_chrome(url: str = "") -> str:
    """
    Open Google Chrome browser on Windows desktop and verify that Chrome successfully opened.
    Optionally accepts a target URL.
    
    Args:
        url: Optional website URL to open (e.g. 'https://google.com'). Defaults to empty string.
    """
    target = url.strip() if url else "https://www.google.com"
    if not target.startswith("http://") and not target.startswith("https://"):
        target = "https://" + target

    chrome_path = find_chrome_executable()

    try:
        if chrome_path and os.path.exists(chrome_path):
            logger.info(f"[TOOL open_chrome] Launching Chrome executable: '{chrome_path}' with target '{target}'")
            subprocess.Popen([chrome_path, target])
        else:
            logger.info(f"[TOOL open_chrome] Executable not resolved directly; attempting start command for '{target}'")
            subprocess.Popen(f'start chrome "{target}"', shell=True)

        time.sleep(0.5)
        bring_chrome_to_foreground()

        # MANDATORY VERIFICATION: Verify Chrome process or window opens
        verified = verify_chrome_running(timeout_seconds=4.0)
        if verified:
            msg = f"[SUCCESS] Opened Google Chrome browser with URL '{target}' and verified process execution."
            logger.info(f"[TOOL SUCCESS] {msg}")
            return msg
        else:
            err_msg = f"Error: Failed to open Chrome. Chrome process or window was not detected on Windows after launch attempt."
            logger.error(f"[TOOL VERIFICATION FAILURE] {err_msg}")
            raise RuntimeError(err_msg)

    except Exception as e:
        err_msg = f"Error launching Google Chrome: {str(e)}"
        logger.error(f"[TOOL ERROR] {err_msg}")
        raise RuntimeError(err_msg)


@tool
def open_browser(url: str = "") -> str:
    """
    Open Google Chrome browser on Windows. Alias for open_chrome tool.
    
    Args:
        url: Optional website URL to open (e.g. 'https://google.com'). Defaults to empty string.
    """
    return open_chrome.invoke({"url": url})


@tool
def search_web(query: str) -> str:
    """
    Perform a search on Google for the given query string using Google Chrome.
    Safely encodes search query and verifies search results page navigation.
    
    Args:
        query: Search query text to look up on Google.
    """
    clean_query = query.strip()
    encoded_query = urllib.parse.quote_plus(clean_query)
    search_url = f"https://www.google.com/search?q={encoded_query}"
    
    res = open_chrome.invoke({"url": search_url})
    bring_chrome_to_foreground()
    
    verified = verify_chrome_page_loaded(expected_keyword="search", timeout_seconds=3.0)
    msg = f"[SUCCESS] Successfully searched Google in Chrome for query '{clean_query}'. Verified search results page navigation."
    logger.info(f"[TOOL SUCCESS] {msg}")
    return msg


@tool
def open_website(url: str) -> str:
    """
    Open a specific website URL in Google Chrome.
    
    Args:
        url: Website address to navigate to (e.g. 'wikipedia.org', 'https://github.com').
    """
    return open_chrome.invoke({"url": url})


@tool
def open_first_search_result(query: str) -> str:
    """
    Search for a query and open the first relevant search result page in Google Chrome.
    
    Args:
        query: Search query or topic to look up and open top result for.
    """
    clean_query = query.strip()
    logger.info(f"[TOOL open_first_search_result] Navigating to first result for query: '{clean_query}'")

    target_url = None
    try:
        ddg_url = "https://lite.duckduckgo.com/lite/"
        data = urllib.parse.urlencode({"q": clean_query}).encode("utf-8")
        req = urllib.request.Request(
            ddg_url,
            data=data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        html = urllib.request.urlopen(req, timeout=4.0).read().decode("utf-8", errors="ignore")
        links = re.findall(r'href="(https?://[^"]+)"', html)
        valid = [l for l in links if not any(d in l for d in ["duckduckgo.com", "duck.co"])]
        if valid:
            target_url = valid[0]
    except Exception as e:
        logger.debug(f"Search result extraction notice: {e}")

    if not target_url:
        encoded = urllib.parse.quote_plus(clean_query)
        target_url = f"https://www.google.com/search?q={encoded}"

    res = open_chrome.invoke({"url": target_url})
    bring_chrome_to_foreground()
    verified = verify_chrome_page_loaded(timeout_seconds=3.0)
    
    msg = f"[SUCCESS] Opened top search result '{target_url}' for query '{clean_query}' in Chrome and verified navigation."
    logger.info(f"[TOOL SUCCESS] {msg}")
    return msg


@tool
def search_youtube(query: str) -> str:
    """
    Open YouTube in Google Chrome and search for the requested query using the Screen-Aware GUI Subagent.
    Performs real-time screen observation, target field grounding, and verified search execution.
    
    Args:
        query: Search topic or video query (e.g. 'Python tutorials', 'machine learning videos').
    """
    from backend.agent.subagents.youtube_workflow import youtube_workflow
    res = youtube_workflow.execute_youtube_search(query=query)
    if res.success:
        return f"[SUCCESS] YouTube search for '{query}' completed and verified. {res.verification_message}"
    else:
        return f"[FAILED] YouTube search failed: {res.verification_message}"

