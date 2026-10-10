"""FastAPI router for AI Desktop Agent natural language task orchestration."""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.agent.agent import desktop_ai_agent
from backend.llm.nvidia import check_nvidia_health
from backend.tools.registry import get_tool_descriptions
from backend.security.permissions import close_permission_gate
from backend.utils.logger import logger


router = APIRouter()


class TaskRequest(BaseModel):
    task: str = Field(..., description="Natural language task instruction for the Windows AI Agent", json_schema_extra={"example": "Open Chrome and search for LangChain"})


class ConfirmationResponseRequest(BaseModel):
    action: str = Field(..., description="'allow' (or 'approve') to approve close action, 'cancel' (or 'reject') to deny", json_schema_extra={"example": "allow"})


class TaskResponse(BaseModel):
    success: bool
    status: str  # "queued", "running", "planning", "executing", "verifying", "completed", "failed", "pending_confirmation"
    completed: bool
    task_id: str
    task_description: str
    current_step: int
    max_steps: int
    execution_log: List[Dict[str, Any]] = []
    message: str = ""
    error: Optional[str] = None
    error_type: Optional[str] = None
    final_result: str = ""
    pending_confirmation: Optional[Dict[str, Any]] = None


@router.get("/health")
def agent_model_health_check():
    """
    Perform an NVIDIA model health check.
    Verifies that configuration, API key, base URL, model name, and model connectivity are ready.
    """
    return check_nvidia_health()


@router.post("/task", response_model=TaskResponse)
async def create_agent_task(req: TaskRequest):
    """
    Submit a natural language task for the NVIDIA LLM-powered AI Desktop Agent.
    """
    clean_task = req.task.strip()
    if not clean_task:
        raise HTTPException(status_code=400, detail="Task description cannot be empty.")

    logger.info(f"[API] Received AI agent task request: '{clean_task}'")
    task_info = await desktop_ai_agent.execute_task(clean_task)
    
    is_failed = task_info.get("status") == "failed" or task_info.get("completed") is False and bool(task_info.get("error"))
    success = not is_failed

    return TaskResponse(
        success=success,
        status=task_info.get("status", "queued"),
        completed=task_info.get("completed", False),
        task_id=task_info.get("task_id", ""),
        task_description=task_info.get("task_description", clean_task),
        current_step=task_info.get("current_step", 0),
        max_steps=task_info.get("max_steps", 10),
        execution_log=task_info.get("execution_log", []),
        message="Task started." if success else "Task failed.",
        error=task_info.get("error"),
        error_type=task_info.get("error_type"),
        final_result=task_info.get("final_result", ""),
        pending_confirmation=task_info.get("pending_confirmation"),
    )


@router.get("/status/{task_id}", response_model=TaskResponse)
async def get_agent_task_status(task_id: str):
    """
    Check current status, execution logs, and result of an AI desktop task.
    """
    task_info = await desktop_ai_agent.get_task_status(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail=f"Task ID '{task_id}' not found.")
    
    is_failed = task_info.get("status") == "failed" or task_info.get("completed") is False and bool(task_info.get("error"))
    success = not is_failed

    return TaskResponse(
        success=success,
        status=task_info.get("status", "running"),
        completed=task_info.get("completed", False),
        task_id=task_info.get("task_id", task_id),
        task_description=task_info.get("task_description", ""),
        current_step=task_info.get("current_step", 0),
        max_steps=task_info.get("max_steps", 10),
        execution_log=task_info.get("execution_log", []),
        message="Task completed successfully." if task_info.get("completed") else ("Task failed." if is_failed else "Task in progress."),
        error=task_info.get("error"),
        error_type=task_info.get("error_type"),
        final_result=task_info.get("final_result", ""),
        pending_confirmation=task_info.get("pending_confirmation"),
    )


@router.get("/history", response_model=List[TaskResponse])
async def get_agent_task_history():
    """
    Retrieve history of all agent tasks executed in the current session.
    """
    tasks = await desktop_ai_agent.get_all_tasks()
    responses = []
    for t in tasks:
        is_failed = t.get("status") == "failed" or t.get("completed") is False and bool(t.get("error"))
        responses.append(TaskResponse(
            success=not is_failed,
            status=t.get("status", "running"),
            completed=t.get("completed", False),
            task_id=t.get("task_id", ""),
            task_description=t.get("task_description", ""),
            current_step=t.get("current_step", 0),
            max_steps=t.get("max_steps", 10),
            execution_log=t.get("execution_log", []),
            message="Task completed successfully." if t.get("completed") else ("Task failed." if is_failed else "Task in progress."),
            error=t.get("error"),
            error_type=t.get("error_type"),
            final_result=t.get("final_result", ""),
            pending_confirmation=t.get("pending_confirmation"),
        ))
    return responses


@router.get("/confirmations/pending")
def list_pending_confirmations():
    """
    Retrieve all active pending window close confirmation requests.
    """
    return {"confirmations": close_permission_gate.get_pending_requests()}


@router.post("/confirmations/{confirmation_id}/respond")
def respond_to_confirmation(confirmation_id: str, req: ConfirmationResponseRequest):
    """
    Submit user approval ('allow') or denial ('cancel') for a pending window close request.
    """
    res = close_permission_gate.respond(confirmation_id, req.action)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to process confirmation response."))
    return res


@router.get("/tools")
def list_agent_tools():
    """
    List all available LangChain tools exposed to the AI Desktop Agent.
    """
    return {"tools": get_tool_descriptions()}
