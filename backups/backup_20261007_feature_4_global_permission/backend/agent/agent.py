"""Desktop AI Agent Orchestrator class using LangGraph and LangChain tools."""

import asyncio
import uuid
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from backend.agent.graph.agent_graph import agent_executor_graph
from backend.agent.prompts.system import SYSTEM_PROMPT
from backend.agent.state import AgentState
from backend.config.settings import settings
from backend.llm.nvidia import check_nvidia_health, classify_nvidia_error
from backend.utils.logger import logger


class DesktopAIAgent:
    """
    High-level agent orchestrator that accepts natural-language user tasks
    and executes them using LangGraph workflow.
    """

    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def execute_task(self, task_description: str) -> Dict[str, Any]:
        """
        Execute a natural language task asynchronously using LangGraph.
        Returns initial task metadata and status.
        """
        task_id = str(uuid.uuid4())[:8]
        task_info = {
            "task_id": task_id,
            "task_description": task_description,
            "status": "queued",
            "completed": False,
            "current_step": 0,
            "max_steps": settings.AGENT_MAX_STEPS,
            "execution_log": [],
            "error": None,
            "error_type": None,
            "final_result": "",
        }

        async with self._lock:
            self._tasks[task_id] = task_info

        # Run background execution task
        asyncio.create_task(self._run_graph_task(task_id, task_description))
        return task_info

    async def _run_graph_task(self, task_id: str, task_description: str):
        """
        Internal worker to run the LangGraph workflow and update task state.
        Ensures failed executions NEVER set completed=True or status='completed'.
        """
        logger.info(f"[AGENT WORKER] Starting task execution [{task_id}]: '{task_description}'")

        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = "running"

        if not settings.AGENT_ENABLE:
            err_msg = "AI Agent execution is currently disabled in settings (AGENT_ENABLE=false)."
            async with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id]["status"] = "failed"
                    self._tasks[task_id]["completed"] = False
                    self._tasks[task_id]["error"] = err_msg
                    self._tasks[task_id]["error_type"] = "CONFIGURATION_ERROR"
                    self._tasks[task_id]["final_result"] = err_msg
            return

        initial_state: AgentState = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=task_description),
            ],
            "task_id": task_id,
            "task_description": task_description,
            "current_step": 0,
            "max_steps": settings.AGENT_MAX_STEPS,
            "status": "planning",
            "completed": False,
            "error": None,
            "error_type": None,
            "execution_log": [],
            "final_result": "",
        }

        try:
            # Execute LangGraph in threadpool with configured timeout
            final_state = await asyncio.wait_for(
                asyncio.to_thread(agent_executor_graph.invoke, initial_state),
                timeout=float(settings.AGENT_TOOL_TIMEOUT * settings.AGENT_MAX_STEPS),
            )

            is_failed = (
                final_state.get("status") == "failed"
                or final_state.get("completed") is False
                or bool(final_state.get("error"))
            )

            messages = final_state.get("messages", [])
            last_msg = messages[-1] if messages else None
            final_text = (
                final_state.get("error")
                or (last_msg.content if isinstance(last_msg, AIMessage) else "Task completed.")
            )

            async with self._lock:
                if task_id in self._tasks:
                    if is_failed:
                        self._tasks[task_id]["status"] = "failed"
                        self._tasks[task_id]["completed"] = False
                        self._tasks[task_id]["error"] = final_state.get("error") or "Task execution failed."
                        self._tasks[task_id]["error_type"] = final_state.get("error_type") or "UNKNOWN_NVIDIA_ERROR"
                        self._tasks[task_id]["final_result"] = final_text
                    else:
                        self._tasks[task_id]["status"] = "completed"
                        self._tasks[task_id]["completed"] = True
                        self._tasks[task_id]["final_result"] = final_text

                    self._tasks[task_id]["current_step"] = final_state.get("current_step", 1)
                    self._tasks[task_id]["execution_log"] = final_state.get("execution_log", [])

            if is_failed:
                logger.error(f"[AGENT WORKER] Task [{task_id}] FAILED: {self._tasks[task_id].get('error')}")
            else:
                logger.info(f"[AGENT WORKER] Task [{task_id}] COMPLETED successfully")

        except asyncio.TimeoutError:
            err_msg = f"Task execution timed out after {settings.AGENT_TOOL_TIMEOUT * settings.AGENT_MAX_STEPS}s."
            logger.error(f"[AGENT WORKER TIMEOUT] [{task_id}]: {err_msg}")
            async with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id]["status"] = "failed"
                    self._tasks[task_id]["completed"] = False
                    self._tasks[task_id]["error"] = err_msg
                    self._tasks[task_id]["error_type"] = "NETWORK_ERROR"
                    self._tasks[task_id]["final_result"] = err_msg

        except Exception as e:
            err_type, err_msg = classify_nvidia_error(e)
            logger.error(f"[AGENT WORKER ERROR] [{task_id}] [{err_type}]: {err_msg}")
            async with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id]["status"] = "failed"
                    self._tasks[task_id]["completed"] = False
                    self._tasks[task_id]["error"] = err_msg
                    self._tasks[task_id]["error_type"] = err_type
                    self._tasks[task_id]["final_result"] = err_msg

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve status and log for a specific task ID, populating pending confirmations."""
        from backend.security.permissions import close_permission_gate
        async with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                return None
            res = dict(task_info)
            pending_list = close_permission_gate.get_pending_requests()
            if pending_list and res.get("status") in ["running", "planning", "executing"]:
                res["pending_confirmation"] = pending_list[0]
                res["status"] = "pending_confirmation"
            else:
                res["pending_confirmation"] = None
            return res

    async def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Return list of all past/active tasks."""
        from backend.security.permissions import close_permission_gate
        async with self._lock:
            tasks = []
            pending_list = close_permission_gate.get_pending_requests()
            for t in self._tasks.values():
                res = dict(t)
                if pending_list and res.get("status") in ["running", "planning", "executing"]:
                    res["pending_confirmation"] = pending_list[0]
                    res["status"] = "pending_confirmation"
                else:
                    res["pending_confirmation"] = None
                tasks.append(res)
            return tasks


# Shared Desktop AI Agent singleton instance
desktop_ai_agent = DesktopAIAgent()
