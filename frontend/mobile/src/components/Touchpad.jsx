import React, { useRef, useState } from 'react';
import { wsService } from '../services/websocket';

export default function Touchpad({ sensitivity = 1.0, onSensitivityChange }) {
  const padRef = useRef(null);
  const touchStartRef = useRef(null);
  const lastTouchTimeRef = useRef(0);
  const longPressTimerRef = useRef(null);
  const isDraggingRef = useRef(false);
  const lastPosRef = useRef({ x: 0, y: 0 });
  const twoFingerStartRef = useRef(0);

  const [activeButton, setActiveButton] = useState(null);

  const handleTouchStart = (e) => {
    e.preventDefault();
    const now = Date.now();

    if (e.touches.length === 1) {
      const touch = e.touches[0];
      lastPosRef.current = { x: touch.clientX, y: touch.clientY };
      touchStartRef.current = {
        clientX: touch.clientX,
        clientY: touch.clientY,
        time: now,
      };

      // Check double-tap -> double click
      if (now - lastTouchTimeRef.current < 280) {
        clearTimeout(longPressTimerRef.current);
        wsService.sendMouseDoubleClick('left');
        lastTouchTimeRef.current = 0;
        return;
      }
      lastTouchTimeRef.current = now;

      // Long press (450ms) -> Right Click
      longPressTimerRef.current = setTimeout(() => {
        wsService.sendMouseClick('right');
      }, 450);

    } else if (e.touches.length === 2) {
      clearTimeout(longPressTimerRef.current);
      twoFingerStartRef.current = (e.touches[0].clientY + e.touches[1].clientY) / 2;
    }
  };

  const handleTouchMove = (e) => {
    e.preventDefault();

    if (e.touches.length === 1 && touchStartRef.current) {
      const touch = e.touches[0];
      const dx = (touch.clientX - lastPosRef.current.x) * sensitivity;
      const dy = (touch.clientY - lastPosRef.current.y) * sensitivity;

      const totalDist = Math.hypot(
        touch.clientX - touchStartRef.current.clientX,
        touch.clientY - touchStartRef.current.clientY
      );
      if (totalDist > 6) {
        clearTimeout(longPressTimerRef.current);
      }

      if (Math.abs(dx) > 0.1 || Math.abs(dy) > 0.1) {
        wsService.sendMouseRelative(dx, dy);
      }

      lastPosRef.current = { x: touch.clientX, y: touch.clientY };

    } else if (e.touches.length === 2) {
      // Two finger scroll
      const currentY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
      const deltaY = currentY - twoFingerStartRef.current;
      if (Math.abs(deltaY) > 6) {
        const scrollDelta = deltaY > 0 ? 1 : -1;
        wsService.sendScroll(scrollDelta);
        twoFingerStartRef.current = currentY;
      }
    }
  };

  const handleTouchEnd = (e) => {
    e.preventDefault();
    clearTimeout(longPressTimerRef.current);

    if (e.touches.length === 0 && touchStartRef.current) {
      const duration = Date.now() - touchStartRef.current.time;
      const touch = e.changedTouches[0];
      const moveDist = Math.hypot(
        touch.clientX - touchStartRef.current.clientX,
        touch.clientY - touchStartRef.current.clientY
      );

      // Clean tap with minimal movement (< 8px)
      if (duration < 280 && moveDist < 8) {
        wsService.sendMouseClick('left');
      }

      touchStartRef.current = null;
    } else if (e.touches.length === 1 && e.changedTouches.length === 1) {
      // Two finger tap ended -> Right Click
      wsService.sendMouseClick('right');
    }
  };

  // Physical button helpers
  const handleLeftClick = () => {
    wsService.sendMouseClick('left');
    setActiveButton('left');
    setTimeout(() => setActiveButton(null), 150);
  };

  const handleRightClick = () => {
    wsService.sendMouseClick('right');
    setActiveButton('right');
    setTimeout(() => setActiveButton(null), 150);
  };

  return (
    <div className="touchpad-wrapper">
      <div
        ref={padRef}
        className="touchpad-surface"
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onTouchCancel={handleTouchEnd}
      >
        <div className="touchpad-hint">
          <span>Trackpad</span>
          <p>1-finger: move/tap • 2-finger: scroll/right-click</p>
        </div>
      </div>

      <div className="touchpad-controls">
        <button
          className={`trackpad-btn ${activeButton === 'left' ? 'active' : ''}`}
          onClick={handleLeftClick}
        >
          Left Click
        </button>
        <div className="sensitivity-selector">
          <label>Sens</label>
          <select
            value={sensitivity}
            onChange={(e) => onSensitivityChange && onSensitivityChange(parseFloat(e.target.value))}
          >
            <option value="0.75">0.75x</option>
            <option value="1.0">1.0x</option>
            <option value="1.5">1.5x</option>
            <option value="2.0">2.0x</option>
          </select>
        </div>
        <button
          className={`trackpad-btn ${activeButton === 'right' ? 'active' : ''}`}
          onClick={handleRightClick}
        >
          Right Click
        </button>
      </div>
    </div>
  );
}
