# Desktop AI Agent - Feature 1: Mobile Remote Control

This module provides a lightweight, real-time, secure remote control interface allowing you to operate your Windows laptop from any mobile browser over your local Wi-Fi network.

---

## 🌟 Feature Overview

- **Automatic LAN QR Pairing**: Scan a generated QR code from your phone's camera to pair automatically without typing IPs, ports, or codes.
- **Mobile Web Interface**: Responsive, touch-friendly UI for mobile browsers (iOS Safari, Android Chrome). No native app installation required.
- **Real-Time Desktop Streaming**: Efficient desktop capture using `mss` compressed into high-speed JPEG streams with zero-copy change detection.
- **Direct Touch & Trackpad Modes**:
  - **Direct Touch**: Tap directly on the laptop screen image; coordinates dynamically map to Windows resolution with letterboxing/pillarboxing support.
  - **Touchpad Mode**: Virtual trackpad with relative cursor movement, left click, right click, 2-finger scroll, and sensitivity adjustments.
- **Comprehensive Control**:
  - **Mouse**: Move, left click, right click, double click, mouse down/up, drag, and vertical scroll.
  - **Keyboard**: Full virtual keyboard, function keys (F1-F12), navigation arrows, text typing, and shortcuts (`Ctrl+C`, `Ctrl+V`, `Alt+Tab`, `Win+D`, etc.).
  - **Window Controls**: Minimize, maximize, and restore active windows.
- **Security & Pairing**: Cryptographically secure 6-digit pairing code, 5-minute single-use expiration, single active controller enforcement, payload validation, and rate limiting.

---

## 🏗 System Architecture

```
 Mobile Camera / Browser (React / Vite SPA)
         │
         │ 1. Scan QR Code: http://<LAN-IP>:8000/pair?code=XXXXXX
         ▼
 FastAPI Backend (Python 3.11+) ──► AuthManager (Validates & Consumes Code)
         │
         │ 2. WebSocket /ws/remote?token=... (Instant Handshake)
         ▼
 Session & Security Layer ────────► SessionManager (Single Controller & Rate Limiter)
         │
         ├─── Stream Task ────────► ScreenCapture (MSS Desktop Grab + JPEG Compression)
         │                               │
         │                               ▼
         │                        JPEG Base64 Frames to Mobile
         │
         └─── Input Messages ─────► Protocol Validation (Pydantic Models)
                                         │
                                         ▼
                               ┌───────────────────────────┐
                               │ Python Controllers:       │
                               │ - MouseController         │
                               │ - KeyboardController      │
                               │ - WindowController        │
                               └───────────────────────────┘
                                         │
                                         ▼
                                    Windows OS
```

---

## 📋 Requirements

- **Operating System**: Windows 10 / Windows 11
- **Python**: Python 3.11+ (Python 3.11, 3.12, 3.13 supported)
- **Network**: Windows Laptop and Mobile Device connected to the same Wi-Fi network.

---

## 🚀 Quick Start Guide (Windows CMD)

### Step 1: Start the Remote Control Server
```cmd
start.bat
```
*or manually:*
```cmd
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Step 2: Open Desktop QR Display Page
When the backend starts, open `http://localhost:8000/pairing` on your laptop browser to display the QR code interface:
```text
======================================================================
               DESKTOP AI AGENT REMOTE CONTROL
======================================================================
  Device Name   : LAPTOP-MQRVJE6S
  LAN Address   : http://192.168.1.38:8000
  
  QR PAIRING    : Open http://192.168.1.38:8000/pairing on this PC
                  or scan the generated QR code in your browser.
  
  PAIRING CODE  : 634498  (Valid for 300s)
======================================================================
  LAN ONLY: Phone and laptop must be connected to the same local Wi-Fi.
======================================================================
```

### Step 3: Scan QR Code with Phone
1. Connect your phone to the same local Wi-Fi network.
2. Scan the QR code using your phone camera.
3. The mobile browser will automatically open `http://<LAN-IP>:8000/pair?code=XXXXXX`, authenticate, and open the remote desktop interface.

---

## 🔒 Security & Safety Features

1. **LAN-Only Scope**: Operates exclusively over your private Local Area Network. No WAN/Internet exposure, relay servers, or cloud tunnels.
2. **5-Minute Temporary Pairing Code**: Pairing codes expire after 300 seconds and auto-refresh without restarting the server.
3. **Single Active Controller**: Only one mobile device can control the laptop at a time to prevent conflicting inputs.
4. **No Shell Execution**: No arbitrary shell or PowerShell commands are permitted over WebSocket. All actions pass through strict controller interfaces.

---

## 🧪 Running Automated Tests

Run the test suite with Pytest:
```cmd
pytest backend/tests/test_remote.py
```
