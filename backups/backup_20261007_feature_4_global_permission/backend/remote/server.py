"""WebSocket server and remote controller dispatcher."""

import asyncio
import json
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from backend.config.settings import settings
from backend.control.keyboard import keyboard_controller
from backend.control.mouse import mouse_controller
from backend.control.window import window_controller
from backend.remote.protocol import (
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
)
from backend.agent.agent import desktop_ai_agent
from backend.remote.session import session_manager, Session
from backend.screen.capture import screen_capture
from backend.security.permissions import Permission, has_permission
from backend.security.validator import MAX_MESSAGE_BYTES
from backend.utils.logger import logger, sanitize_message


async def handle_remote_websocket(websocket: WebSocket, token: Optional[str] = None):
    """
    Handle lifecycle and event routing for an authenticated mobile WebSocket client.
    """
    await websocket.accept()
    client_ip = websocket.client.host if websocket.client else "unknown"
    user_agent = websocket.headers.get("user-agent", "unknown")
    logger.info(f"[REMOTE] WebSocket connection attempt from IP: {client_ip} | User-Agent: {user_agent}")

    session: Optional[Session] = None
    stream_task: Optional[asyncio.Task] = None
    force_frame_event = asyncio.Event()

    try:
        # Step 1: Obtain session token (via URL query param for instant connection or fallback to 1st message)
        if not token:
            try:
                raw_auth = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                auth_data = json.loads(raw_auth)
                auth_msg = AuthMessage(**auth_data)
                token = auth_msg.token
            except asyncio.TimeoutError:
                logger.warning(f"[REMOTE] WebSocket client authentication timed out from IP: {client_ip}")
                await websocket.send_json({"type": "error", "message": "Authentication timed out"})
                await websocket.close(code=1008)
                return
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"[REMOTE] Malformed authentication payload from IP {client_ip}: {e}")
                await websocket.send_json({"type": "error", "message": "Invalid authentication message"})
                await websocket.close(code=1008)
                return

        # Step 2: Validate session and enforce single active controller
        connected, reason = session_manager.connect_controller(token, websocket)
        if not connected:
            logger.warning(f"[REMOTE] Authentication failure for IP {client_ip}: {reason}")
            await websocket.send_json({"type": "error", "message": reason or "Authentication failed"})
            await websocket.close(code=1008)
            return

        session = session_manager.get_session(token)
        if not session:
            logger.warning(f"[REMOTE] Session not found for token from IP {client_ip}")
            await websocket.close(code=1008)
            return

        logger.info(f"[REMOTE] Authentication successful for mobile client at IP: {client_ip}")

        loop = asyncio.get_running_loop()
        from backend.security.permissions import close_permission_gate

        def on_gate_request(req_data: dict):
            try:
                asyncio.run_coroutine_threadsafe(
                    websocket.send_json({
                        "type": "close_confirmation_request",
                        "data": req_data
                    }),
                    loop
                )
            except Exception as e:
                logger.debug(f"[WS GATE NOTIFY ERROR] {e}")

        close_permission_gate.register_broadcast_callback(on_gate_request)

        # Send status confirmation
        await websocket.send_json({
            "type": "status",
            "status": "connected",
            "message": f"Connected to {settings.DEVICE_NAME}",
        })
        force_frame_event.set()

        # Step 3: Screen streaming background task with backpressure flow control
        client_ready = [True]
        last_sent_time = [0.0]

        async def stream_screen():
            frame_interval = 1.0 / max(1, settings.SCREEN_FPS)
            heartbeat_interval = 2.0  # Force a frame every 2 seconds if idle

            while True:
                try:
                    now = asyncio.get_event_loop().time()
                    # Safety reset: if client ack is delayed over 0.5s, force ready to avoid freeze
                    if not client_ready[0] and (now - last_sent_time[0] > 0.5):
                        client_ready[0] = True

                    force = force_frame_event.is_set() or (now - last_sent_time[0] > heartbeat_interval)
                    if force_frame_event.is_set():
                        force_frame_event.clear()

                    if client_ready[0] or force:
                        frame = await asyncio.to_thread(screen_capture.capture_frame, force)
                        if frame:
                            client_ready[0] = False
                            last_sent_time[0] = now
                            await websocket.send_json({
                                "type": "screen",
                                "data": frame["data"],
                                "width": frame["width"],
                                "height": frame["height"],
                                "orig_width": frame["orig_width"],
                                "orig_height": frame["orig_height"],
                            })

                    await asyncio.sleep(frame_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"Streaming frame loop warning: {e}")
                    await asyncio.sleep(frame_interval)

        stream_task = asyncio.create_task(stream_screen())

        # Step 4: Message handling loop
        while True:
            text = await websocket.receive_text()

            # Reject oversized payloads
            if len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
                await websocket.send_json({"type": "error", "message": "Payload size exceeded limit"})
                continue

            session.touch()

            # Rate limit check
            if not session.rate_limiter.allow():
                # Silently drop flood messages (e.g. runaway touch events)
                continue

            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Malformed JSON payload"})
                continue

            msg_type = data.get("type")

            # Route by message type
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "frame_ack":
                client_ready[0] = True

            elif msg_type == "request_frame":
                client_ready[0] = True
                force_frame_event.set()

            elif msg_type == "mouse_move":
                if not has_permission(session.permissions, Permission.MOUSE_CONTROL):
                    continue
                try:
                    move_msg = MouseMoveMessage(**data)
                    if move_msg.relative:
                        await asyncio.to_thread(mouse_controller.move_relative, move_msg.dx or 0.0, move_msg.dy or 0.0)
                    elif move_msg.x is not None and move_msg.y is not None:
                        await asyncio.to_thread(mouse_controller.move, move_msg.x, move_msg.y, True)
                except ValidationError:
                    pass

            elif msg_type == "mouse_click":
                if not has_permission(session.permissions, Permission.MOUSE_CONTROL):
                    continue
                try:
                    click_msg = MouseClickMessage(**data)
                    await asyncio.to_thread(mouse_controller.click, click_msg.button)
                except ValidationError:
                    pass

            elif msg_type == "mouse_double_click":
                if not has_permission(session.permissions, Permission.MOUSE_CONTROL):
                    continue
                try:
                    dclick_msg = MouseDoubleClickMessage(**data)
                    await asyncio.to_thread(mouse_controller.double_click, dclick_msg.button)
                except ValidationError:
                    pass

            elif msg_type == "mouse_down":
                if not has_permission(session.permissions, Permission.MOUSE_CONTROL):
                    continue
                try:
                    mdown_msg = MouseDownMessage(**data)
                    await asyncio.to_thread(mouse_controller.mouse_down, mdown_msg.button)
                except ValidationError:
                    pass

            elif msg_type == "mouse_up":
                if not has_permission(session.permissions, Permission.MOUSE_CONTROL):
                    continue
                try:
                    mup_msg = MouseUpMessage(**data)
                    await asyncio.to_thread(mouse_controller.mouse_up, mup_msg.button)
                except ValidationError:
                    pass

            elif msg_type == "mouse_drag":
                if not has_permission(session.permissions, Permission.MOUSE_CONTROL):
                    continue
                try:
                    drag_msg = MouseDragMessage(**data)
                    await asyncio.to_thread(mouse_controller.drag, drag_msg.x, drag_msg.y, True)
                except ValidationError:
                    pass

            elif msg_type == "scroll":
                if not has_permission(session.permissions, Permission.MOUSE_CONTROL):
                    continue
                try:
                    scroll_msg = ScrollMessage(**data)
                    await asyncio.to_thread(mouse_controller.scroll, scroll_msg.delta)
                except ValidationError:
                    pass

            elif msg_type == "key":
                if not has_permission(session.permissions, Permission.KEYBOARD_CONTROL):
                    continue
                try:
                    key_msg = KeyMessage(**data)
                    await asyncio.to_thread(keyboard_controller.press, key_msg.key)
                except ValidationError:
                    pass

            elif msg_type == "hotkey":
                if not has_permission(session.permissions, Permission.KEYBOARD_CONTROL):
                    continue
                try:
                    hotkey_msg = HotkeyMessage(**data)
                    await asyncio.to_thread(keyboard_controller.hotkey, hotkey_msg.keys)
                except ValidationError:
                    pass

            elif msg_type == "type_text":
                if not has_permission(session.permissions, Permission.KEYBOARD_CONTROL):
                    continue
                try:
                    type_msg = TypeTextMessage(**data)
                    await asyncio.to_thread(keyboard_controller.write, type_msg.text)
                except ValidationError:
                    pass

            elif msg_type == "window_action":
                if not has_permission(session.permissions, Permission.WINDOW_CONTROL):
                    continue
                try:
                    win_msg = WindowActionMessage(**data)
                    if win_msg.action == "minimize":
                        await asyncio.to_thread(window_controller.minimize)
                    elif win_msg.action == "maximize":
                        await asyncio.to_thread(window_controller.maximize)
                    elif win_msg.action == "restore":
                        await asyncio.to_thread(window_controller.restore)
                except ValidationError:
                    pass

            elif msg_type == "ai_task":
                try:
                    task_msg = AITaskMessage(**data)
                    logger.info(f"[REMOTE WS] Received AI Agent task from mobile client: '{task_msg.task}'")
                    task_info = await desktop_ai_agent.execute_task(task_msg.task)
                    await websocket.send_json({
                        "type": "ai_task_started",
                        "task_id": task_info["task_id"],
                        "task": task_msg.task,
                    })
                except ValidationError:
                    pass

            elif msg_type == "close_confirmation_response":
                cid = data.get("confirmation_id")
                act = data.get("action", "cancel")
                if cid:
                    from backend.security.permissions import close_permission_gate
                    res = close_permission_gate.respond(cid, act)
                    await websocket.send_json({
                        "type": "close_confirmation_ack",
                        "confirmation_id": cid,
                        "success": res.get("success", False),
                        "status": res.get("status", "unknown"),
                    })

            else:
                logger.warning(f"Unrecognized message type received: {msg_type}")
                await websocket.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {session.client_ip if session else 'Unknown'}")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket handler: {e}")
    finally:
        try:
            close_permission_gate.unregister_broadcast_callback(on_gate_request)
        except Exception:
            pass
        if stream_task:
            stream_task.cancel()
        if session:
            session_manager.disconnect_controller(session.token)
