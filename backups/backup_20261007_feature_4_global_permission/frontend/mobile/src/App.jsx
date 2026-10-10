import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import { wsService } from './services/websocket';
import RemoteScreen from './components/RemoteScreen';
import Touchpad from './components/Touchpad';
import Keyboard from './components/Keyboard';
import Toolbar from './components/Toolbar';
import AIAgentPanel from './components/AIAgentPanel';

import PermissionDialog from './components/PermissionDialog';

// Application States
const STATE = {
  CONNECTING: 'CONNECTING',
  PAIRING: 'PAIRING',
  CONNECTED: 'CONNECTED',
  DISCONNECTED: 'DISCONNECTED',
};

export default function App() {
  const [appState, setAppState] = useState(STATE.PAIRING);
  const [pairingCode, setPairingCode] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [remoteInfo, setRemoteInfo] = useState(null);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [diagData, setDiagData] = useState(null);
  const [pendingConfirmation, setPendingConfirmation] = useState(null);

  // Active interaction mode: 'direct' (direct screen tap) or 'touchpad'
  const [activeMode, setActiveMode] = useState('direct');
  const [isKeyboardOpen, setIsKeyboardOpen] = useState(false);
  const [isAIAgentOpen, setIsAIAgentOpen] = useState(false);
  const [sensitivity, setSensitivity] = useState(1.0);

  // Poll pending confirmations as fallback
  useEffect(() => {
    const checkPending = async () => {
      try {
        const res = await fetch('/api/agent/confirmations/pending');
        if (res.ok) {
          const data = await res.json();
          if (data.confirmations && data.confirmations.length > 0) {
            setPendingConfirmation(data.confirmations[0]);
          } else {
            setPendingConfirmation(null);
          }
        }
      } catch (e) {
        // quiet
      }
    };
    checkPending();
    const interval = setInterval(checkPending, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleConfirmationRespond = async (confirmationId, action) => {
    setPendingConfirmation(null);
    try {
      if (wsService.isConnected) {
        wsService.send({
          type: 'close_confirmation_response',
          confirmation_id: confirmationId,
          action: action,
        });
      }
      await fetch(`/api/agent/confirmations/${confirmationId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
    } catch (e) {
      console.warn('Confirmation response error:', e);
    }
  };

  // Fetch host info
  const fetchInfo = useCallback(async () => {
    try {
      const res = await fetch('/remote/info');
      if (res.ok) {
        const data = await res.json();
        setRemoteInfo(data);
      }
    } catch (e) {
      console.warn('Could not fetch /remote/info:', e);
    }
  }, []);

  const runDiagnostics = async () => {
    setShowDiagnostics(true);
    setDiagData({ status: 'checking...' });
    try {
      const healthRes = await fetch('/health');
      const healthOk = healthRes.ok;
      const diagRes = await fetch('/remote/diagnostics');
      const diagJson = diagRes.ok ? await diagRes.json() : null;

      setDiagData({
        http: healthOk ? 'Reachable ✓' : 'Failed ✕',
        diagnostics: diagJson || { server: 'offline' },
        ws: wsService.isConnected ? 'Connected ✓' : 'Disconnected ✕',
      });
    } catch (e) {
      setDiagData({
        http: 'Failed ✕ (Check Wi-Fi / Firewall)',
        diagnostics: { error: e.message },
        ws: 'Disconnected ✕',
      });
    }
  };

  useEffect(() => {
    fetchInfo();

    // Setup WebSocket listeners
    const unsubStatus = wsService.on('status', (msg) => {
      if (msg.status === 'connected') {
        setAppState(STATE.CONNECTED);
        setErrorMessage('');
      }
    });

    const unsubError = wsService.on('error', (err) => {
      if (err.message) {
        setErrorMessage(err.message);
      }
    });

    const unsubClose = wsService.on('close', (event) => {
      setAppState(STATE.DISCONNECTED);
      if (event.code === 1008) {
        sessionStorage.removeItem('desktop_remote_token');
        setErrorMessage('Session expired or invalidated. Please pair again.');
        setAppState(STATE.PAIRING);
      }
    });

    const unsubGate = wsService.on('close_confirmation_request', (msg) => {
      if (msg.data) {
        setPendingConfirmation(msg.data);
      }
    });

    // Check existing session token
    const savedToken = sessionStorage.getItem('desktop_remote_token');
    if (savedToken) {
      setAppState(STATE.CONNECTING);
      wsService.connect(savedToken);
    }

    return () => {
      unsubStatus();
      unsubError();
      unsubClose();
      unsubGate();
      wsService.disconnect();
    };
  }, [fetchInfo]);

  // Handle Pairing Form Submission
  const handlePairSubmit = async (e) => {
    e.preventDefault();
    const cleanCode = pairingCode.trim();
    if (!cleanCode) return;

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const res = await fetch('/remote/pair', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: cleanCode }),
      });

      const data = await res.json();

      if (!res.ok) {
        setErrorMessage(data.detail || 'Pairing failed. Please verify code.');
        setIsSubmitting(false);
        return;
      }

      if (data.success && data.session_token) {
        sessionStorage.setItem('desktop_remote_token', data.session_token);
        setAppState(STATE.CONNECTING);
        wsService.connect(data.session_token);
      }
    } catch (err) {
      setErrorMessage('Network error connecting to desktop. Ensure Wi-Fi match or check Firewall.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Disconnect
  const handleDisconnect = () => {
    wsService.disconnect();
    sessionStorage.removeItem('desktop_remote_token');
    setAppState(STATE.DISCONNECTED);
  };

  // Handle Reconnect
  const handleReconnect = () => {
    const savedToken = sessionStorage.getItem('desktop_remote_token');
    if (savedToken) {
      setAppState(STATE.CONNECTING);
      wsService.connect(savedToken);
    } else {
      setAppState(STATE.PAIRING);
    }
  };

  return (
    <div className="app-container">
      {/* STATE A: CONNECTING */}
      {appState === STATE.CONNECTING && (
        <div className="center-screen">
          <div className="auth-card">
            <div className="spinner"></div>
            <h2>Connecting to Desktop...</h2>
            <p>Establishing secure WebSocket session</p>
          </div>
        </div>
      )}

      {/* STATE B: PAIRING */}
      {appState === STATE.PAIRING && (
        <div className="center-screen">
          <div className="auth-card">
            <div className="device-badge">
              💻 {remoteInfo?.name || 'Windows Laptop'}
            </div>
            <h2>Connect to your Windows PC</h2>
            <p>Enter the 6-digit pairing code shown in your laptop terminal.</p>

            {errorMessage && (
              <div className="error-message">
                <p>{errorMessage}</p>
                <button
                  type="button"
                  className="diag-link-btn"
                  onClick={runDiagnostics}
                >
                  Run Diagnostics
                </button>
              </div>
            )}

            <form onSubmit={handlePairSubmit} className="pairing-form">
              <input
                type="text"
                pattern="[0-9]*"
                inputMode="numeric"
                maxLength={6}
                placeholder="••••••"
                value={pairingCode}
                onChange={(e) => setPairingCode(e.target.value.replace(/\D/g, ''))}
                className="pairing-input"
                autoFocus
              />
              <button
                type="submit"
                className="primary-btn"
                disabled={isSubmitting || pairingCode.length < 4}
              >
                {isSubmitting ? 'Verifying...' : 'Connect'}
              </button>
            </form>

            <button
              type="button"
              className="secondary-btn small-text"
              onClick={runDiagnostics}
            >
              🔍 Connection Test & Diagnostics
            </button>
          </div>
        </div>
      )}

      {/* STATE C: CONNECTED */}
      {appState === STATE.CONNECTED && (
        <div className="connected-view">
          <Toolbar
            activeMode={activeMode}
            onModeChange={setActiveMode}
            onToggleKeyboard={() => setIsKeyboardOpen(!isKeyboardOpen)}
            isKeyboardOpen={isKeyboardOpen}
            onToggleAIAgent={() => setIsAIAgentOpen(!isAIAgentOpen)}
            onDisconnect={handleDisconnect}
            isConnected={true}
            deviceName={remoteInfo?.name}
          />

          <RemoteScreen
            activeMode={activeMode}
            isConnected={true}
          />

          {activeMode === 'touchpad' && (
            <Touchpad
              sensitivity={sensitivity}
              onSensitivityChange={setSensitivity}
            />
          )}

          <Keyboard
            isOpen={isKeyboardOpen}
            onClose={() => setIsKeyboardOpen(false)}
          />

          <AIAgentPanel
            isOpen={isAIAgentOpen}
            onClose={() => setIsAIAgentOpen(false)}
          />
        </div>
      )}

      {/* STATE D: DISCONNECTED */}
      {appState === STATE.DISCONNECTED && (
        <div className="center-screen">
          <div className="auth-card">
            <h2>Desktop disconnected</h2>
            <p>The connection to your Windows laptop was closed.</p>
            {errorMessage && <div className="error-message">{errorMessage}</div>}
            <button className="primary-btn" onClick={handleReconnect}>
              Reconnect
            </button>
            <button
              className="secondary-btn"
              onClick={() => {
                sessionStorage.removeItem('desktop_remote_token');
                setPairingCode('');
                setAppState(STATE.PAIRING);
              }}
            >
              Pair with new code
            </button>
          </div>
        </div>
      )}

      {/* DIAGNOSTICS MODAL */}
      {showDiagnostics && (
        <div className="diag-modal-backdrop" onClick={() => setShowDiagnostics(false)}>
          <div className="diag-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Network & Connection Diagnostics</h3>
            <div className="diag-content">
              <pre>{JSON.stringify(diagData, null, 2)}</pre>
              <h4>Troubleshooting Guide:</h4>
              <ul>
                <li>Ensure phone and laptop are on the <b>same Wi-Fi</b> network.</li>
                <li>Verify Windows Firewall allows <b>TCP Port 8000</b> on Private Networks.</li>
                <li>Check router for <b>AP / Client Isolation</b> (disable if enabled).</li>
                <li>Turn off phone VPN or Cellular Data fallback if interfering with LAN.</li>
              </ul>
            </div>
            <button className="primary-btn" onClick={() => setShowDiagnostics(false)}>
              Close
            </button>
          </div>
        </div>
      )}

      {/* GLOBAL CLOSE PERMISSION MODAL */}
      <PermissionDialog
        confirmation={pendingConfirmation}
        onRespond={handleConfirmationRespond}
      />
    </div>
  );
}
