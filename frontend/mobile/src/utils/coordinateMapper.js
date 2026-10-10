/**
 * Coordinate mapping utility to convert mobile touch coordinates to Windows normalized coordinates.
 * Accurately handles letterboxing / pillarboxing when aspect ratios differ.
 */

export function mapTouchToNormalized(touchClientX, touchClientY, containerRect, frameWidth, frameHeight) {
  if (!containerRect || !frameWidth || !frameHeight) {
    return { valid: false, x: 0, y: 0 };
  }

  const containerW = containerRect.width;
  const containerH = containerRect.height;
  if (containerW <= 0 || containerH <= 0) {
    return { valid: false, x: 0, y: 0 };
  }

  // Calculate actual rendered rectangle of the frame inside the container (object-fit: contain)
  const frameAspect = frameWidth / frameHeight;
  const containerAspect = containerW / containerH;

  let renderW, renderH, renderX, renderY;

  if (containerAspect > frameAspect) {
    // Container is wider than frame -> pillarboxing (bars on left/right)
    renderH = containerH;
    renderW = containerH * frameAspect;
    renderY = 0;
    renderX = (containerW - renderW) / 2;
  } else {
    // Container is taller than frame -> letterboxing (bars on top/bottom)
    renderW = containerW;
    renderH = containerW / frameAspect;
    renderX = 0;
    renderY = (containerH - renderH) / 2;
  }

  // Position relative to container
  const touchRelX = touchClientX - containerRect.left;
  const touchRelY = touchClientY - containerRect.top;

  // Position relative to rendered desktop frame
  const frameRelX = touchRelX - renderX;
  const frameRelY = touchRelY - renderY;

  // Check if tap fell inside rendered area (allow a small margin for edge taps)
  if (frameRelX < -5 || frameRelX > renderW + 5 || frameRelY < -5 || frameRelY > renderH + 5) {
    return { valid: false, x: 0, y: 0 };
  }

  // Normalize between 0.0 and 1.0
  const normX = Math.max(0.0, Math.min(1.0, frameRelX / renderW));
  const normY = Math.max(0.0, Math.min(1.0, frameRelY / renderH));

  return {
    valid: true,
    x: Number(normX.toFixed(4)),
    y: Number(normY.toFixed(4)),
  };
}
