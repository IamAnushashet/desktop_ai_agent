import React, { useRef, useEffect, useState, useCallback } from 'react';
import { wsService } from '../services/websocket';
import { mapTouchToNormalized } from '../utils/coordinateMapper';

export default function RemoteScreen({ activeMode = 'direct', isConnected = false }) {
  const containerRef = useRef(null);
  const imgRef = useRef(null);
  const [hasFrame, setHasFrame] = useState(false);
  const [frameMeta, setFrameMeta] = useState({ width: 1920, height: 1080 });
  const frameMetaRef = useRef({ width: 1920, height: 1080 });
  const [fps, setFps] = useState(0);

  // Gesture tracking refs
  const touchStartRef = useRef(null);
  const lastTouchTimeRef = useRef(0);
  const longPressTimerRef = useRef(null);
  const isDraggingRef = useRef(false);
  const lastScrollYRef = useRef(0);
  const frameCountRef = useRef(0);
  const lastFpsCalcRef = useRef(Date.now());

  // Listen for screen frames from WebSocket
  useEffect(() => {
    const unsubScreen = wsService.on('screen', (msg) => {
      if (!hasFrame) {
        setHasFrame(true);
      }
      if (imgRef.current) {
        imgRef.current.src = `data:image/jpeg;base64,${msg.data}`;
      }
      wsService.sendFrameAck();

      const w = msg.orig_width || msg.width || 1920;
      const h = msg.orig_height || msg.height || 1080;
      if (w !== frameMetaRef.current.width || h !== frameMetaRef.current.height) {
        frameMetaRef.current = { width: w, height: h };
        setFrameMeta({ width: w, height: h });
      }

      // Calculate approximate received FPS
      frameCountRef.current += 1;
      const now = Date.now();
      if (now - lastFpsCalcRef.current >= 1000) {
        setFps(frameCountRef.current);
        frameCountRef.current = 0;
        lastFpsCalcRef.current = now;
      }
    });

    return () => {
      unsubScreen();
    };
  }, [hasFrame]);

  const getNormalizedPoint = useCallback((touch) => {
    if (!containerRef.current) return { valid: false };
    const rect = containerRef.current.getBoundingClientRect();
    return mapTouchToNormalized(
      touch.clientX,
      touch.clientY,
      rect,
      frameMetaRef.current.width,
      frameMetaRef.current.height
    );
  }, []);

  // Handle Touch Start
  const handleTouchStart = (e) => {
    if (activeMode !== 'direct') return;

    if (e.touches.length === 1) {
      const touch = e.touches[0];
      const norm = getNormalizedPoint(touch);
      if (!norm.valid) return;

      const now = Date.now();
      const timeDiff = now - lastTouchTimeRef.current;
      touchStartRef.current = {
        x: norm.x,
        y: norm.y,
        clientX: touch.clientX,
        clientY: touch.clientY,
        time: now,
      };

      // Check double-tap threshold (< 300ms)
      if (timeDiff < 300) {
        clearTimeout(longPressTimerRef.current);
        wsService.sendMouseMove(norm.x, norm.y);
        wsService.sendMouseDoubleClick('left');
        lastTouchTimeRef.current = 0;
        return;
      }
      lastTouchTimeRef.current = now;

      // Start long-press timer (450ms) for Right Click or Drag
      longPressTimerRef.current = setTimeout(() => {
        isDraggingRef.current = true;
        wsService.sendMouseMove(norm.x, norm.y);
        wsService.sendMouseClick('right');
      }, 450);

    } else if (e.touches.length === 2) {
      // Two-finger gesture start (scroll)
      clearTimeout(longPressTimerRef.current);
      lastScrollYRef.current = (e.touches[0].clientY + e.touches[1].clientY) / 2;
    }
  };

  // Handle Touch Move
  const handleTouchMove = (e) => {
    if (activeMode !== 'direct') return;

    if (e.touches.length === 1 && touchStartRef.current) {
      const touch = e.touches[0];
      const moveDist = Math.hypot(
        touch.clientX - touchStartRef.current.clientX,
        touch.clientY - touchStartRef.current.clientY
      );

      // If finger moved significantly (> 8px), cancel long press
      if (moveDist > 8) {
        clearTimeout(longPressTimerRef.current);
      }

      const norm = getNormalizedPoint(touch);
      if (!norm.valid) return;

      if (isDraggingRef.current) {
        wsService.sendMouseDrag(norm.x, norm.y);
      } else {
        wsService.sendMouseMove(norm.x, norm.y);
      }

    } else if (e.touches.length === 2) {
      // Two-finger scroll
      const currentScrollY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
      const deltaY = currentScrollY - lastScrollYRef.current;
      if (Math.abs(deltaY) > 5) {
        const scrollDelta = deltaY > 0 ? 1 : -1;
        wsService.sendScroll(scrollDelta);
        lastScrollYRef.current = currentScrollY;
      }
    }
  };

  // Handle Touch End
  const handleTouchEnd = (e) => {
    if (activeMode !== 'direct') return;
    clearTimeout(longPressTimerRef.current);

    if (e.touches.length === 0 && touchStartRef.current) {
      const touchDuration = Date.now() - touchStartRef.current.time;
      if (isDraggingRef.current) {
        wsService.sendMouseUp('left');
        isDraggingRef.current = false;
      } else if (touchDuration < 300) {
        wsService.sendMouseMove(touchStartRef.current.x, touchStartRef.current.y);
        wsService.sendMouseClick('left');
      }
      touchStartRef.current = null;
    }
  };

  return (
    <div
      ref={containerRef}
      className="remote-screen-container"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={handleTouchEnd}
    >
      <img
        ref={imgRef}
        alt="Desktop Display"
        className="desktop-stream-image"
        draggable={false}
        style={{ display: hasFrame ? 'block' : 'none' }}
      />
      {!hasFrame && (
        <div className="screen-placeholder">
          <div className="loader-pulse"></div>
          <p>{isConnected ? 'Waiting for desktop frame...' : 'Connecting...'}</p>
        </div>
      )}

      {/* Frame overlay HUD */}
      <div className="screen-hud">
        <span className="hud-badge">{frameMeta.width}×{frameMeta.height}</span>
        {fps > 0 && <span className="hud-badge">{fps} FPS</span>}
      </div>
    </div>
  );
}
