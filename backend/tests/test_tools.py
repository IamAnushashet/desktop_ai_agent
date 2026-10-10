"""Unit tests for LangChain Tools and Tool Registry."""

import pytest
from backend.tools.registry import ALL_TOOLS, TOOL_MAP, get_tool_descriptions


def test_tool_registry_contains_expected_tools():
    tool_names = [t.name for t in ALL_TOOLS]
    expected = [
        "open_chrome",
        "open_browser",
        "search_web",
        "open_website",
        "open_first_search_result",
        "run_system_app",
        "type_text",
        "press_key",
        "press_hotkey",
        "move_mouse",
        "click_mouse",
        "double_click_mouse",
        "scroll_mouse",
        "window_action",
        "get_active_window_info",
        "write_word_document",
        "create_powerpoint_presentation",
        "draw_sketch_in_paint",
    ]
    for exp in expected:
        assert exp in tool_names, f"Missing tool '{exp}' in tool registry"
        assert exp in TOOL_MAP, f"Missing tool '{exp}' in TOOL_MAP"


def test_tool_descriptions_schema():
    schemas = get_tool_descriptions()
    assert len(schemas) == len(ALL_TOOLS)
    for s in schemas:
        assert "name" in s
        assert "description" in s
        assert "args" in s


def test_browser_tool_invocations(monkeypatch):
    from unittest.mock import MagicMock
    from backend.tools.browser.browser import open_chrome, search_web, open_website, open_first_search_result

    monkeypatch.setattr("backend.tools.browser.browser.find_chrome_executable", lambda: r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    monkeypatch.setattr("backend.tools.browser.browser.subprocess.Popen", lambda args, **kwargs: MagicMock())
    monkeypatch.setattr("backend.tools.browser.browser.verify_chrome_running", lambda timeout_seconds=3.0: True)
    monkeypatch.setattr("backend.tools.browser.browser.verify_chrome_page_loaded", lambda expected_keyword="", timeout_seconds=4.0: True)
    monkeypatch.setattr("backend.tools.browser.browser.bring_chrome_to_foreground", lambda: True)

    # 1. Open Chrome
    res_open = open_chrome.invoke({"url": ""})
    assert "[SUCCESS]" in res_open

    # 2. Search web
    res_search = search_web.invoke({"query": "artificial intelligence"})
    assert "[SUCCESS]" in res_search
    assert "artificial intelligence" in res_search

    # 3. Open website
    res_site = open_website.invoke({"url": "https://www.python.org"})
    assert "[SUCCESS]" in res_site

    # 4. Open first search result
    res_first = open_first_search_result.invoke({"query": "MCA project ideas"})
    assert "[SUCCESS]" in res_first

