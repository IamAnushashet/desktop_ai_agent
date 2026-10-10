"""LangGraph Task Orchestration Workflow for Desktop AI Agent."""

from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END

from backend.agent.state import AgentState
from backend.agent.prompts.system import SYSTEM_PROMPT
from backend.llm.nvidia import get_nvidia_llm, classify_nvidia_error
from backend.tools.registry import ALL_TOOLS, TOOL_MAP
from backend.config.settings import settings
from backend.utils.logger import logger


def call_llm_node(state: AgentState) -> Dict[str, Any]:
    """
    Node that calls the NVIDIA LLM for task planning and tool selection.
    Propagates any NVIDIA LLM failure directly as state failure.
    """
    if state.get("status") == "failed" or (state.get("completed") is False and state.get("error")):
        return {
            "status": "failed",
            "completed": False,
        }

    try:
        llm = get_nvidia_llm()
        llm_with_tools = llm.bind_tools(ALL_TOOLS)

        messages = list(state.get("messages", []))
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

        response = llm_with_tools.invoke(messages)
        
        step_num = state.get("current_step", 0) + 1
        tool_calls = [
            {"name": tc.get("name"), "args": tc.get("args")}
            for tc in getattr(response, "tool_calls", [])
        ]
        
        log_entry = {
            "step": step_num,
            "node": "agent",
            "message": response.content or ("Selected tool calls: " + ", ".join([t["name"] for t in tool_calls]) if tool_calls else "Task analysis"),
            "tool_calls": tool_calls,
        }
        
        exec_log = list(state.get("execution_log", []))
        exec_log.append(log_entry)

        # If LLM didn't return any more tool calls, check if an error occurred previously
        has_prev_error = bool(state.get("error"))
        is_completed = not bool(tool_calls) and not has_prev_error
        is_failed = has_prev_error

        return {
            "messages": [response],
            "current_step": step_num,
            "status": "failed" if is_failed else ("executing" if tool_calls else "completed"),
            "completed": is_completed,
            "execution_log": exec_log,
        }
    except Exception as e:
        err_type, err_msg = classify_nvidia_error(e)
        logger.error(f"[LANGGRAPH LLM FAILURE] [{err_type}]: {err_msg}")
        
        err_log_entry = {
            "step": state.get("current_step", 0) + 1,
            "node": "agent",
            "error_type": err_type,
            "message": f"NVIDIA LLM Error: {err_msg}",
        }
        exec_log = list(state.get("execution_log", []))
        exec_log.append(err_log_entry)

        return {
            "messages": [AIMessage(content=f"Task Failed: {err_msg}")],
            "status": "failed",
            "completed": False,
            "error": err_msg,
            "error_type": err_type,
            "execution_log": exec_log,
            "final_result": err_msg,
        }


def execute_tools_node(state: AgentState) -> Dict[str, Any]:
    """
    Node that executes tool calls requested by the LLM response.
    Catches tool execution failures and marks state status as failed.
    """
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    tool_messages: List[ToolMessage] = []
    log_entries: List[Dict[str, Any]] = []

    has_tool_failure = False
    first_tool_error = None

    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id", "call_default")

            logger.info(f"[LANGGRAPH TOOL EXECUTION] Tool: {tool_name}, Args: {tool_args}")
            
            tool_instance = TOOL_MAP.get(tool_name)
            is_error = False
            if tool_instance:
                try:
                    result = tool_instance.invoke(tool_args)
                    res_str = str(result)
                    if (res_str.startswith("Error") or res_str.startswith("Failed") or "[ERROR]" in res_str) and "Close action cancelled" not in res_str:
                        is_error = True
                        if not first_tool_error:
                            first_tool_error = res_str
                except Exception as err:
                    result = f"Error executing tool '{tool_name}': {str(err)}"
                    is_error = True
                    if not first_tool_error:
                        first_tool_error = str(result)
            else:
                result = f"Error: Tool '{tool_name}' not found in registry."
                is_error = True
                if not first_tool_error:
                    first_tool_error = result

            if is_error:
                has_tool_failure = True

            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_call_id)
            )
            log_entries.append({
                "step": state.get("current_step", 0),
                "node": "tools",
                "tool": tool_name,
                "args": tool_args,
                "result": str(result),
                "status": "failed" if is_error else "success",
            })

    exec_log = list(state.get("execution_log", []))
    exec_log.extend(log_entries)

    update: Dict[str, Any] = {
        "messages": tool_messages,
        "execution_log": exec_log,
    }

    if has_tool_failure:
        update["status"] = "failed"
        update["completed"] = False
        update["error"] = first_tool_error or "Tool execution failed."
        update["error_type"] = "TOOL_EXECUTION_ERROR"
        update["final_result"] = first_tool_error or "Tool execution failed."

    return update


def should_continue(state: AgentState) -> str:
    """
    Conditional routing edge to determine whether to execute tools or end the workflow.
    """
    if state.get("status") == "failed" or (state.get("completed") is False and bool(state.get("error"))):
        return END

    messages = state.get("messages", [])
    if not messages:
        return END

    last_message = messages[-1]
    step = state.get("current_step", 0)
    max_steps = state.get("max_steps", settings.AGENT_MAX_STEPS)

    if step >= max_steps:
        logger.warning(f"[LANGGRAPH] Reached max steps limit ({max_steps})")
        return END

    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "tools"

    return END


def create_agent_graph() -> StateGraph:
    """
    Build and compile the LangGraph workflow.
    """
    builder = StateGraph(AgentState)
    builder.add_node("agent", call_llm_node)
    builder.add_node("tools", execute_tools_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")

    return builder.compile()


# Compiled agent graph instance
agent_executor_graph = create_agent_graph()
