import React, { useState } from 'react';
import { wsService } from '../services/websocket';

export default function Toolbar({
  activeMode,
  onModeChange,
  onToggleKeyboard,
  isKeyboardOpen,
  onDisconnect,
  isConnected,
  deviceName,
  onToggleAIAgent,
}) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showWinActions, setShowWinActions] = useState(false);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().then(() => {
        setIsFullscreen(true);
      }).catch((err) => {
        console.error('Fullscreen request error:', err);
      });
    } else {
      document.exitFullscreen().then(() => {
        setIsFullscreen(false);
      }).catch((err) => {
        console.error('Fullscreen exit error:', err);
      });
    }
  };

  const handleWindowAction = (action) => {
    wsService.sendWindowAction(action);
    setShowWinActions(false);
  };

  return (
    <div className="toolbar-container">
      {/* Top status bar */}
      <div className="status-bar">
        <div className="status-indicator">
          <span className={`status-dot ${isConnected ? 'online' : 'offline'}`}></span>
          <span className="device-name">{deviceName || 'Windows PC'}</span>
        </div>
        <div className="status-actions">
          <button
            className={`tool-icon-btn ${isFullscreen ? 'active' : ''}`}
            onClick={toggleFullscreen}
            title="Toggle Fullscreen"
          >
            {isFullscreen ? '⤢' : '⛶'}
          </button>
          <button
            className="tool-icon-btn disconnect"
            onClick={onDisconnect}
            title="Disconnect"
          >
            Disconnect
          </button>
        </div>
      </div>

      {/* Main control navigation bar */}
      <div className="main-nav-bar">
        {/* Mode Selector */}
        <div className="mode-toggle">
          <button
            className={`mode-btn ${activeMode === 'direct' ? 'selected' : ''}`}
            onClick={() => onModeChange('direct')}
          >
            Direct Touch
          </button>
          <button
            className={`mode-btn ${activeMode === 'touchpad' ? 'selected' : ''}`}
            onClick={() => onModeChange('touchpad')}
          >
            Touchpad
          </button>
        </div>

        {/* Windows Actions Menu */}
        <div className="win-actions-wrapper">
          <button
            className={`nav-btn ${showWinActions ? 'active' : ''}`}
            onClick={() => setShowWinActions(!showWinActions)}
          >
            Window
          </button>
          {showWinActions && (
            <div className="win-actions-dropdown">
              <button onClick={() => handleWindowAction('minimize')}>Minimize</button>
              <button onClick={() => handleWindowAction('maximize')}>Maximize</button>
              <button onClick={() => handleWindowAction('restore')}>Restore</button>
            </div>
          )}
        </div>

        {/* Keyboard button */}
        <button
          className={`nav-btn keyboard-btn ${isKeyboardOpen ? 'active' : ''}`}
          onClick={onToggleKeyboard}
        >
          Keyboard
        </button>

        {/* AI Agent button */}
        <button
          className="nav-btn ai-agent-btn"
          onClick={onToggleAIAgent}
          style={{ background: 'linear-gradient(135deg, #0284c7, #38bdf8)', color: '#fff', fontWeight: 'bold' }}
        >
          🤖 AI Agent
        </button>
      </div>
    </div>
  );
}
