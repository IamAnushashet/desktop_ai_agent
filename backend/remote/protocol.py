"""WebSocket protocol definitions and Pydantic message models."""

from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field


# --- Inbound Mobile Messages ---

class AuthMessage(BaseModel):
    type: Literal["auth"] = "auth"
    token: str


class MouseMoveMessage(BaseModel):
    type: Literal["mouse_move"] = "mouse_move"
    x: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    y: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    relative: Optional[bool] = False
    dx: Optional[float] = 0.0
    dy: Optional[float] = 0.0


class MouseClickMessage(BaseModel):
    type: Literal["mouse_click"] = "mouse_click"
    button: Literal["left", "right", "middle"] = "left"


class MouseDoubleClickMessage(BaseModel):
    type: Literal["mouse_double_click"] = "mouse_double_click"
    button: Literal["left", "right"] = "left"


class MouseDownMessage(BaseModel):
    type: Literal["mouse_down"] = "mouse_down"
    button: Literal["left", "right", "middle"] = "left"


class MouseUpMessage(BaseModel):
    type: Literal["mouse_up"] = "mouse_up"
    button: Literal["left", "right", "middle"] = "left"


class MouseDragMessage(BaseModel):
    type: Literal["mouse_drag"] = "mouse_drag"
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class ScrollMessage(BaseModel):
    type: Literal["scroll"] = "scroll"
    delta: float


class KeyMessage(BaseModel):
    type: Literal["key"] = "key"
    key: str


class HotkeyMessage(BaseModel):
    type: Literal["hotkey"] = "hotkey"
    keys: List[str]


class TypeTextMessage(BaseModel):
    type: Literal["type_text"] = "type_text"
    text: str


class WindowActionMessage(BaseModel):
    type: Literal["window_action"] = "window_action"
    action: Literal["minimize", "maximize", "restore"]


class PingMessage(BaseModel):
    type: Literal["ping"] = "ping"


class RequestFrameMessage(BaseModel):
    type: Literal["request_frame"] = "request_frame"


class AITaskMessage(BaseModel):
    type: Literal["ai_task"] = "ai_task"
    task: str


ClientMessage = Union[
    AuthMessage,
    MouseMoveMessage,
    MouseClickMessage,
    MouseDoubleClickMessage,
    MouseDownMessage,
    MouseUpMessage,
    MouseDragMessage,
    ScrollMessage,
    KeyMessage,
    HotkeyMessage,
    TypeTextMessage,
    WindowActionMessage,
    PingMessage,
    RequestFrameMessage,
    AITaskMessage,
]


# --- Outbound Server Messages ---

class ScreenMessage(BaseModel):
    type: Literal["screen"] = "screen"
    data: str
    width: int
    height: int
    orig_width: int
    orig_height: int


class StatusMessage(BaseModel):
    type: Literal["status"] = "status"
    status: str
    message: Optional[str] = None
    session_id: Optional[str] = None


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    message: str


class PongMessage(BaseModel):
    type: Literal["pong"] = "pong"
