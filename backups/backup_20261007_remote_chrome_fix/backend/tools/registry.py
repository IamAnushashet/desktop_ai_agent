"""Central registry of all LangChain tools for Desktop AI Agent."""

from typing import List, Dict, Any
from langchain_core.tools import BaseTool

from backend.tools.browser.browser import open_chrome, open_browser, search_web, open_website, open_first_search_result
from backend.tools.desktop.mouse import move_mouse, click_mouse, double_click_mouse, scroll_mouse
from backend.tools.desktop.keyboard import type_text, press_key, press_hotkey
from backend.tools.desktop.window import window_action, get_active_window_info
from backend.tools.system.system import run_system_app
from backend.tools.office.word import write_word_document
from backend.tools.office.powerpoint import create_powerpoint_presentation
from backend.tools.desktop.paint import draw_sketch_in_paint


# List of all available LangChain tools for the AI Agent
ALL_TOOLS: List[BaseTool] = [
    open_chrome,
    open_browser,
    search_web,
    open_website,
    open_first_search_result,
    run_system_app,
    type_text,
    press_key,
    press_hotkey,
    move_mouse,
    click_mouse,
    double_click_mouse,
    scroll_mouse,
    window_action,
    get_active_window_info,
    write_word_document,
    create_powerpoint_presentation,
    draw_sketch_in_paint,
]

# Map tool names to tool instances for fast lookup
TOOL_MAP: Dict[str, BaseTool] = {t.name: t for t in ALL_TOOLS}


def get_all_tools() -> List[BaseTool]:
    """Return list of registered agent tools."""
    return ALL_TOOLS


def get_tool_descriptions() -> List[Dict[str, Any]]:
    """Return JSON serializable tool schemas for API endpoints and UI display."""
    descriptions = []
    for tool in ALL_TOOLS:
        descriptions.append({
            "name": tool.name,
            "description": tool.description,
            "args": tool.args,
        })
    return descriptions
