"""FastAPI application entry point for Desktop AI Agent Remote Control."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.config.settings import settings
from backend.remote.qr import generate_qr_base64
from backend.remote.server import handle_remote_websocket
from backend.remote.session import session_manager
from backend.security.authentication import auth_manager
from backend.utils.logger import logger
from backend.utils.network import get_local_ip, get_all_lan_ips
from backend.api.routes.chat import router as chat_router


# Pydantic schemas for REST endpoints
class PairRequest(BaseModel):
    code: str


class PairResponse(BaseModel):
    success: bool
    session_token: str
    message: str = "Pairing successful"


class InfoResponse(BaseModel):
    name: str
    ip: str
    port: int
    status: str
    has_active_controller: bool
    code_expires_in: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown actions."""
    lan_ip = get_local_ip()
    all_ips = get_all_lan_ips()
    initial_code = auth_manager.get_or_create_active_code()
    desktop_qr_url = f"http://{lan_ip}:{settings.PORT}/pairing"

    formatted_ips = ", ".join(all_ips) if all_ips else lan_ip

    # Formatted terminal startup banner
    banner = f"""
======================================================================
               DESKTOP AI AGENT REMOTE CONTROL
======================================================================
  Device Name   : {settings.DEVICE_NAME}
  LAN Address   : http://{lan_ip}:{settings.PORT}
  Active LANs   : {formatted_ips}
  
  QR PAIRING    : Open {desktop_qr_url} on this PC
                  or scan the generated QR code.
  
  PAIRING CODE  : {initial_code}  (Valid for {settings.PAIRING_CODE_EXPIRY}s)
======================================================================
  LAN ONLY: Phone and laptop must be connected to the same local Wi-Fi.
======================================================================
"""
    print(banner, flush=True)
    logger.info(f"[STARTUP] Server started on {lan_ip}:{settings.PORT}. Pairing code: {initial_code}")

    yield

    logger.info("Desktop AI Agent shutting down.")


app = FastAPI(
    title="Desktop AI Agent Remote Control",
    description="Control Windows Laptop from Mobile Browser",
    version="1.0.0",
    lifespan=lifespan,
)

# GZip compression middleware for fast static file serving over mobile Wi-Fi
app.add_middleware(GZipMiddleware, minimum_size=500)

# Enable CORS for mobile development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount AI Agent Router
app.include_router(chat_router, prefix="/api/agent", tags=["AI Agent"])


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming HTTP connections with client IP and User-Agent."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    if not request.url.path.startswith("/assets"):
        logger.info(f"[HTTP] {request.method} {request.url.path} from IP: {client_ip} | User-Agent: {user_agent}")
    response = await call_next(request)
    return response


@app.get("/health")
def health_check():
    """System health check endpoint."""
    return {"status": "ok"}


@app.get("/remote/diagnostics")
def get_diagnostics():
    """Return non-sensitive system diagnostics for troubleshooting."""
    lan_ip = get_local_ip()
    all_ips = get_all_lan_ips()
    return {
        "server": "online",
        "host": settings.HOST,
        "port": settings.PORT,
        "lan_ip": lan_ip,
        "all_lan_ips": all_ips,
        "websocket": "/ws/remote",
    }


@app.get("/remote/info", response_model=InfoResponse)
def get_remote_info():
    """Return non-sensitive connection and pairing information."""
    lan_ip = get_local_ip()
    active = session_manager.is_controller_connected()
    rem_sec = auth_manager.get_remaining_seconds()

    return InfoResponse(
        name=settings.DEVICE_NAME,
        ip=lan_ip,
        port=settings.PORT,
        status="controller_connected" if active else "waiting_for_pairing",
        has_active_controller=active,
        code_expires_in=rem_sec,
    )


@app.get("/remote/qr")
def get_remote_qr():
    """Return current QR code Base64 payload, pairing URL, and countdown timer."""
    lan_ip = get_local_ip()
    all_ips = get_all_lan_ips()
    code = auth_manager.get_or_create_active_code()
    rem_sec = auth_manager.get_remaining_seconds()

    pairing_url = f"http://{lan_ip}:{settings.PORT}/pair?code={code}"
    qr_b64 = generate_qr_base64(pairing_url)

    return {
        "pairing_code": code,
        "pairing_url": pairing_url,
        "qr_base64": qr_b64,
        "expires_in": rem_sec,
        "lan_ip": lan_ip,
        "all_lan_ips": all_ips,
        "device_name": settings.DEVICE_NAME,
    }


@app.get("/pairing")
def desktop_pairing_page():
    """
    Desktop browser pairing page displaying the QR code, manual code, and countdown timer.
    """
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Desktop AI Agent - QR Pairing</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                       background: #090d16; color: #f8fafc; display: flex; align-items: center;
                       justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
                .card { background: #1e293b; border: 1px solid rgba(255,255,255,0.1); padding: 36px; border-radius: 24px; box-shadow: 0 12px 40px rgba(0,0,0,0.6); max-width: 440px; width: 100%; text-align: center; }
                .badge { display: inline-block; background: rgba(56,189,248,0.15); color: #38bdf8; border: 1px solid rgba(56,189,248,0.3); padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; margin-bottom: 12px; }
                h2 { margin: 8px 0 4px; font-size: 1.6rem; color: #ffffff; }
                p { color: #94a3b8; font-size: 0.95rem; margin: 4px 0 20px; line-height: 1.4; }
                .qr-container { background: #ffffff; padding: 16px; border-radius: 16px; display: inline-block; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
                .qr-container img { width: 220px; height: 220px; display: block; }
                .info-box { background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 16px; margin-top: 24px; text-align: left; }
                .info-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 0.9rem; }
                .info-label { color: #94a3b8; }
                .info-val { color: #f8fafc; font-weight: 600; }
                .code-display { font-family: monospace; font-size: 1.8rem; letter-spacing: 4px; color: #38bdf8; font-weight: bold; background: rgba(56,189,248,0.1); padding: 8px; border-radius: 8px; text-align: center; margin-top: 12px; }
                .timer { color: #f59e0b; font-weight: 600; }
                .footer-notice { margin-top: 20px; font-size: 0.8rem; color: #64748b; }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="badge">🔒 LAN ONLY PAIRING</div>
                <h2 id="device-name">Desktop AI Agent</h2>
                <p>Scan with your mobile camera to control this laptop</p>
                <div class="qr-container">
                    <img id="qr-img" src="" alt="Pairing QR Code">
                </div>
                <div class="info-box">
                    <div class="info-row">
                        <span class="info-label">LAN Address:</span>
                        <span class="info-val" id="lan-url">Loading...</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Expires in:</span>
                        <span class="info-val timer" id="timer">05:00</span>
                    </div>
                    <div class="info-label" style="margin-top:8px;">Manual Pairing Code:</div>
                    <div class="code-display" id="manual-code">------</div>
                </div>
                <div class="footer-notice">Ensure your phone is connected to the same Wi-Fi network.</div>
            </div>
            <script>
                async function updateQR() {
                    try {
                        const res = await fetch('/remote/qr');
                        if (res.ok) {
                            const data = await res.json();
                            document.getElementById('qr-img').src = data.qr_base64;
                            document.getElementById('lan-url').innerText = data.lan_ip + ':' + 8000;
                            document.getElementById('manual-code').innerText = data.pairing_code;
                            document.getElementById('device-name').innerText = data.device_name;
                            
                            const min = Math.floor(data.expires_in / 60);
                            const sec = data.expires_in % 60;
                            document.getElementById('timer').innerText = 
                                `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
                        }
                    } catch(e) {
                        console.warn('QR update error:', e);
                    }
                }
                updateQR();
                setInterval(updateQR, 2000);
            </script>
        </body>
        </html>
        """
    )


@app.get("/pair")
def pair_via_qr(request: Request, code: Optional[str] = Query(None)):
    """
    Automatic QR pairing endpoint.
    Mobile browser scans QR code and hits http://<LAN-IP>:8000/pair?code=XXXXXX.
    Verifies code, creates session, and redirects mobile browser to UI.
    """
    client_ip = request.client.host if request.client else "unknown"

    if not code:
        raise HTTPException(status_code=400, detail="Missing pairing code")

    success, result = auth_manager.verify_and_consume_code(code)
    if not success:
        logger.warning(f"[QR PAIR] Failed automatic QR pair attempt from {client_ip}: {result}")
        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pairing Failed</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                           background: #0f172a; color: #f8fafc; display: flex; align-items: center;
                           justify-content: center; height: 100vh; margin: 0; text-align: center; padding: 20px; }}
                    .card {{ background: #1e293b; padding: 32px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); max-width: 400px; }}
                    h2 {{ color: #ef4444; margin-top: 0; }}
                    p {{ color: #94a3b8; line-height: 1.5; }}
                    .btn {{ display: inline-block; background: #38bdf8; color: #0f172a; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 16px; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>Pairing Code Expired or Invalid</h2>
                    <p>{result or 'This QR code is no longer valid.'}</p>
                    <p>Please rescan the new QR code on your laptop screen or enter the manual code.</p>
                    <a href="/" class="btn">Enter Manual Code</a>
                </div>
            </body>
            </html>
            """,
            status_code=401,
        )

    session_token = result
    session_manager.register_session(session_token, client_ip)
    logger.info(f"[QR PAIR] Automatic QR pairing successful for {client_ip}")

    # Return HTML that stores session token in sessionStorage and redirects to mobile app
    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Authenticating...</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                       background: #0f172a; color: #f8fafc; display: flex; align-items: center;
                       justify-content: center; height: 100vh; margin: 0; text-align: center; padding: 20px; }}
                .card {{ background: #1e293b; padding: 32px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); max-width: 360px; }}
                h3 {{ color: #38bdf8; margin-top: 0; }}
                .spinner {{ border: 3px solid rgba(255,255,255,0.1); border-top-color: #38bdf8; border-radius: 50%; width: 32px; height: 32px; animation: spin 0.8s linear infinite; margin: 16px auto; }}
                @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="spinner"></div>
                <h3>Pairing Verified!</h3>
                <p>Connecting to {settings.DEVICE_NAME}...</p>
            </div>
            <script>
                sessionStorage.setItem('desktop_remote_token', '{session_token}');
                window.location.href = '/';
            </script>
        </body>
        </html>
        """
    )


@app.post("/remote/pair", response_model=PairResponse)
def pair_device(req: PairRequest, request: Request):
    """
    Authenticate mobile client with temporary pairing code.
    Returns session token on success.
    """
    client_ip = request.client.host if request.client else "unknown"
    success, result = auth_manager.verify_and_consume_code(req.code)

    if not success:
        logger.warning(f"Failed pairing attempt from {client_ip}: {result}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result or "Invalid pairing code",
        )

    session_token = result
    session_manager.register_session(session_token, client_ip)
    return PairResponse(success=True, session_token=session_token)


@app.websocket("/ws/remote")
async def websocket_remote_endpoint(websocket: WebSocket, token: str = Query(None)):
    """WebSocket endpoint for screen streaming and input automation."""
    await handle_remote_websocket(websocket, token=token)


# Serve Mobile Frontend static assets if built
DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "mobile" / "dist"

if DIST_DIR.exists() and (DIST_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Serve exact file if exists, else index.html for SPA
        file_path = DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(DIST_DIR / "index.html")
else:
    @app.get("/")
    def serve_fallback_ui():
        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Desktop AI Agent</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                           background: #0f172a; color: #f8fafc; display: flex; align-items: center;
                           justify-content: center; height: 100vh; margin: 0; text-align: center; padding: 20px; }
                    .card { background: #1e293b; padding: 32px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); max-width: 400px; }
                    h2 { margin-top: 0; color: #38bdf8; }
                    p { color: #94a3b8; line-height: 1.5; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>Desktop AI Agent</h2>
                    <p>Backend API is active.</p>
                    <p>Please build the frontend UI using <code>npm run build</code> in <code>frontend/mobile</code>.</p>
                </div>
            </body>
            </html>
            """
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=False)
