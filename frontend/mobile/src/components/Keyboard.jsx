import React, { useState, useRef } from 'react';
import { wsService } from '../services/websocket';

export default function Keyboard({ isOpen, onClose }) {
  const [typedText, setTypedText] = useState('');
  const [showFunctionKeys, setShowFunctionKeys] = useState(false);
  const inputRef = useRef(null);

  if (!isOpen) return null;

  // Send single key
  const handleKey = (keyName) => {
    wsService.sendKey(keyName);
  };

  // Send shortcut combination
  const handleHotkey = (combo) => {
    wsService.sendHotkey(combo);
  };

  // Send bulk typed text
  const handleSendText = (e) => {
    e.preventDefault();
    if (typedText.trim()) {
      wsService.sendTypeText(typedText);
      setTypedText('');
    }
  };

  // Live typing on mobile
  const handleInputChange = (e) => {
    const val = e.target.value;
    setTypedText(val);
  };

  const shortcuts = [
    { label: 'Ctrl+C', keys: ['ctrl', 'c'] },
    { label: 'Ctrl+V', keys: ['ctrl', 'v'] },
    { label: 'Ctrl+X', keys: ['ctrl', 'x'] },
    { label: 'Ctrl+A', keys: ['ctrl', 'a'] },
    { label: 'Ctrl+Z', keys: ['ctrl', 'z'] },
    { label: 'Ctrl+S', keys: ['ctrl', 's'] },
    { label: 'Alt+Tab', keys: ['alt', 'tab'] },
    { label: 'Alt+F4', keys: ['alt', 'f4'] },
    { label: 'Win+D', keys: ['win', 'd'] },
    { label: 'Win+E', keys: ['win', 'e'] },
  ];

  return (
    <div className="keyboard-drawer">
      <div className="keyboard-header">
        <span className="keyboard-title">Windows Keyboard</span>
        <button className="keyboard-close-btn" onClick={onClose}>✕</button>
      </div>

      {/* Direct text input form */}
      <form onSubmit={handleSendText} className="text-send-form">
        <input
          ref={inputRef}
          type="text"
          className="text-input"
          placeholder="Type text for Windows..."
          value={typedText}
          onChange={handleInputChange}
          autoFocus
        />
        <button type="submit" className="send-btn" disabled={!typedText}>
          Send
        </button>
      </form>

      {/* Quick shortcuts */}
      <div className="shortcuts-row">
        {shortcuts.map((sc) => (
          <button
            key={sc.label}
            className="key-pill"
            onClick={() => handleHotkey(sc.keys)}
          >
            {sc.label}
          </button>
        ))}
      </div>

      {/* Action and Navigation Keys */}
      <div className="keys-grid">
        <button className="ctrl-key" onClick={() => handleKey('escape')}>Esc</button>
        <button className="ctrl-key" onClick={() => handleKey('tab')}>Tab</button>
        <button className="ctrl-key" onClick={() => handleKey('backspace')}>⌫ Back</button>
        <button className="ctrl-key" onClick={() => handleKey('delete')}>Del</button>

        <button className="ctrl-key accent" onClick={() => handleKey('enter')}>↵ Enter</button>
        <button className="ctrl-key" onClick={() => handleKey('space')}>Space</button>
        <button className="ctrl-key" onClick={() => handleKey('win')}>⊞ Win</button>
        <button
          className="ctrl-key"
          onClick={() => setShowFunctionKeys(!showFunctionKeys)}
        >
          {showFunctionKeys ? 'Hide F1-12' : 'F1-F12'}
        </button>
      </div>

      {/* Function keys */}
      {showFunctionKeys && (
        <div className="function-keys-grid">
          {Array.from({ length: 12 }, (_, i) => `f${i + 1}`).map((fk) => (
            <button
              key={fk}
              className="key-pill small"
              onClick={() => handleKey(fk)}
            >
              {fk.toUpperCase()}
            </button>
          ))}
        </div>
      )}

      {/* Arrow keys pad */}
      <div className="arrow-keys-pad">
        <button className="arrow-key" onClick={() => handleKey('up')}>▲</button>
        <div className="arrow-horizontal">
          <button className="arrow-key" onClick={() => handleKey('left')}>◄</button>
          <button className="arrow-key" onClick={() => handleKey('down')}>▼</button>
          <button className="arrow-key" onClick={() => handleKey('right')}>►</button>
        </div>
      </div>
    </div>
  );
}
