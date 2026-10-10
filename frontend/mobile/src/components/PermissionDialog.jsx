import React, { useState, useEffect } from 'react';
import './PermissionDialog.css';

export default function PermissionDialog({ confirmation, onRespond }) {
  if (!confirmation) return null;

  const { confirmation_id, target, targets, remaining_seconds } = confirmation;
  const [timeLeft, setTimeLeft] = useState(remaining_seconds || 60);

  useEffect(() => {
    setTimeLeft(remaining_seconds || 60);
  }, [remaining_seconds, confirmation_id]);

  useEffect(() => {
    if (timeLeft <= 0) {
      onRespond(confirmation_id, 'cancel');
      return;
    }
    const timer = setInterval(() => {
      setTimeLeft((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [timeLeft, confirmation_id, onRespond]);

  const appList = targets && targets.length > 1 ? targets : [target || 'Desktop Application'];

  return (
    <div className="perm-dialog-backdrop" onClick={(e) => e.stopPropagation()}>
      <div className="perm-dialog-card">
        <div className="perm-dialog-header">
          <span className="perm-icon">⚠️</span>
          <h3>Application Close Permission</h3>
        </div>

        <div className="perm-dialog-body">
          <p className="perm-subtext">The AI Agent wants to close:</p>
          
          <div className="perm-target-box">
            {appList.length === 1 ? (
              <div className="perm-target-single">{appList[0]}</div>
            ) : (
              <ul className="perm-target-list">
                {appList.map((app, idx) => (
                  <li key={idx}>• {app}</li>
                ))}
              </ul>
            )}
          </div>

          <p className="perm-question">Do you want to allow this?</p>
          
          <div className="perm-timer">
            Request expires in <span className="timer-sec">{timeLeft}s</span>
          </div>
        </div>

        <div className="perm-dialog-actions">
          <button
            type="button"
            className="perm-btn perm-btn-allow"
            onClick={() => onRespond(confirmation_id, 'allow')}
          >
            Allow Close
          </button>
          <button
            type="button"
            className="perm-btn perm-btn-cancel"
            onClick={() => onRespond(confirmation_id, 'cancel')}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
