"""LangGraph State definition for Desktop AI Agent."""

from typing import List, Dict, Any, Optional, Annotated, Sequence
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    """
    State object passed between nodes in the LangGraph workflow.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    task_id: str
    task_description: str
    status: str  # "queued", "running", "planning", "executing", "verifying", "completed", "failed"
    completed: bool
    error: Optional[str]
    error_type: Optional[str]
    current_step: int
    max_steps: int
    execution_log: List[Dict[str, Any]]
    final_result: str
    pending_confirmation: Optional[Dict[str, Any]]
