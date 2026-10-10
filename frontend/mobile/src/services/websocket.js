/**
 * WebSocket service for communicating with Windows desktop agent.
 */

class WebSocketService {
  constructor() {
    this.ws = null;
    this.token = null;
    this.url = null;
    this.listeners = new Map();
    this.pingInterval = null;
    this.reconnectTimer = null;
    this.shouldReconnect = true;
    this.isConnected = false;
  }

  connect(token, wsUrl = null) {
    this.token = token;
    this.shouldReconnect = true;

    if (!wsUrl) {
      const loc = window.location;
      const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = loc.host || 'localhost:8000';
      this.url = `${protocol}//${host}/ws/remote?token=${encodeURIComponent(token)}`;
    } else {
      this.url = wsUrl;
    }

    this._initSocket();
  }

  _initSocket() {
    if (this.ws) {
      try {
        this.ws.close();
      } catch (e) {
        // ignore
      }
    }

    try {
      this.ws = new WebSocket(this.url);
    } catch (err) {
      this._emit('error', { message: 'Failed to create WebSocket connection' });
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.isConnected = true;
      this._emit('open', {});

      // Authenticate immediately as first message
      if (this.token) {
        this.send({ type: 'auth', token: this.token });
      }

      // Start ping heartbeat every 10 seconds
      this._startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type) {
          this._emit(msg.type, msg);
        }
        this._emit('message', msg);
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    };

    this.ws.onclose = (event) => {
      this.isConnected = false;
      this._stopHeartbeat();
      this._emit('close', event);

      if (this.shouldReconnect && event.code !== 1008) {
        this._scheduleReconnect();
      }
    };

    this.ws.onerror = (error) => {
      this._emit('error', error);
    };
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.pingInterval = setInterval(() => {
      if (this.isConnected) {
        this.send({ type: 'ping' });
      }
    }, 10000);
  }

  _stopHeartbeat() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.shouldReconnect) {
        console.log('Attempting WebSocket reconnect...');
        this._initSocket();
      }
    }, 3000);
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);
    return () => this.off(event, callback);
  }

  off(event, callback) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).delete(callback);
    }
  }

  _emit(event, data) {
    if (this.listeners.has(event)) {
      for (const cb of this.listeners.get(event)) {
        try {
          cb(data);
        } catch (e) {
          console.error(`Error in listener for ${event}:`, e);
        }
      }
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  // --- Convenience Command Methods ---

  sendMouseMove(x, y) {
    return this.send({ type: 'mouse_move', x, y });
  }

  sendMouseRelative(dx, dy) {
    return this.send({ type: 'mouse_move', relative: true, dx, dy });
  }

  sendMouseClick(button = 'left') {
    return this.send({ type: 'mouse_click', button });
  }

  sendMouseDoubleClick(button = 'left') {
    return this.send({ type: 'mouse_double_click', button });
  }

  sendMouseDown(button = 'left') {
    return this.send({ type: 'mouse_down', button });
  }

  sendMouseUp(button = 'left') {
    return this.send({ type: 'mouse_up', button });
  }

  sendMouseDrag(x, y) {
    return this.send({ type: 'mouse_drag', x, y });
  }

  sendScroll(delta) {
    return this.send({ type: 'scroll', delta });
  }

  sendKey(key) {
    return this.send({ type: 'key', key });
  }

  sendHotkey(keys) {
    return this.send({ type: 'hotkey', keys });
  }

  sendTypeText(text) {
    return this.send({ type: 'type_text', text });
  }

  sendWindowAction(action) {
    return this.send({ type: 'window_action', action });
  }

  requestFrame() {
    return this.send({ type: 'request_frame' });
  }

  sendFrameAck() {
    return this.send({ type: 'frame_ack' });
  }

  disconnect() {
    this.shouldReconnect = false;
    this._stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.close(1000, 'User disconnected');
      } catch (e) {
        // ignore
      }
      this.ws = null;
    }
    this.isConnected = false;
  }
}

export const wsService = new WebSocketService();
