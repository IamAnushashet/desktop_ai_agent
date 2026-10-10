import React, { useState, useEffect } from 'react';
import './AIAgentPanel.css';

const PRESET_TASKS = [
  '🌐 Open Chrome',
  '🔍 Search for Python Tutorial on Chrome',
  '🔗 Open website github.com',
  '⌨️ Type Hello World into active window',
  '⏎ Press Enter',
  '📉 Minimize active window',
  '📈 Maximize active window',
];

export default function AIAgentPanel({ isOpen, onClose }) {
  const [taskInput, setTaskInput] = useState('');
  const [activeTask, setActiveTask] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [history, setHistory] = useState([]);
  const [healthStatus, setHealthStatus] = useState(null);

  // Check model health and fetch recent task history when panel opens
  useEffect(() => {
    if (isOpen) {
      checkHealth();
      fetchHistory();
    }
  }, [isOpen]);

  const checkHealth = async () => {
    try {
      const res = await fetch('/api/agent/health');
      if (res.ok) {
        const data = await res.json();
        setHealthStatus(data);
      }
    } catch (e) {
      setHealthStatus({ success: false, status: 'failed', message: 'Could not connect to health API' });
    }
  };

  // Poll status if task is running
  useEffect(() => {
    let interval = null;
    if (activeTask && (activeTask.status === 'running' || activeTask.status === 'planning' || activeTask.status === 'executing')) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`/api/agent/status/${activeTask.task_id}`);
          if (res.ok) {
            const updated = await res.json();
            setActiveTask(updated);
            if (updated.status === 'completed' || updated.status === 'failed') {
              fetchHistory();
            }
          }
        } catch (e) {
          console.warn('Task status check error:', e);
        }
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [activeTask]);

  const fetchHistory = async () => {
    try {
      const res = await fetch('/api/agent/history');
      if (res.ok) {
        const data = await res.json();
        setHistory(data.reverse());
      }
    } catch (e) {
      console.warn('Could not fetch task history:', e);
    }
  };

  const handleRunTask = async (taskText) => {
    const clean = (taskText || taskInput).trim();
    if (!clean || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const res = await fetch('/api/agent/task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: clean }),
      });

      if (res.ok) {
        const data = await res.json();
        setActiveTask(data);
        setTaskInput('');
      } else {
        alert('Failed to launch AI Task');
      }
    } catch (err) {
      console.error('Task launch error:', err);
      alert('Error launching AI Task');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="ai-modal-backdrop" onClick={onClose}>
      <div className="ai-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="ai-header">
          <div className="ai-title">
            <span className="ai-sparkle">🤖</span> NVIDIA AI Desktop Agent
          </div>
          <button className="ai-close-btn" onClick={onClose}>✕</button>
        </div>

        {/* MODEL HEALTH BAR */}
        {healthStatus && (
          <div className={`health-bar ${healthStatus.success ? 'health-ok' : 'health-err'}`}>
            <span>
              {healthStatus.success ? '🟢 NVIDIA Model Ready:' : '🔴 Model Error:'}{' '}
              <b>{healthStatus.model || 'NVIDIA'}</b> - {healthStatus.message}
            </span>
          </div>
        )}

        <div className="ai-input-section">
          <form onSubmit={(e) => { e.preventDefault(); handleRunTask(); }} className="ai-form">
            <input
              type="text"
              placeholder="e.g. Open Chrome and search for artificial intelligence..."
              value={taskInput}
              onChange={(e) => setTaskInput(e.target.value)}
              className="ai-input"
            />
            <button type="submit" className="ai-run-btn" disabled={isSubmitting || !taskInput.trim()}>
              {isSubmitting ? 'Starting...' : 'Run Task'}
            </button>
          </form>

          <div className="ai-presets">
            <span className="preset-label">Quick Prompts:</span>
            <div className="preset-chips">
              {PRESET_TASKS.map((preset, idx) => {
                const textOnly = preset.replace(/^[^\s]+\s*/, '');
                return (
                  <button
                    key={idx}
                    type="button"
                    className="chip-btn"
                    onClick={() => handleRunTask(textOnly)}
                  >
                    {preset}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* ACTIVE TASK EXECUTION CARD */}
        {activeTask && (
          <div className={`ai-active-card status-${activeTask.status}`}>
            <div className="active-card-header">
              <span className="task-name">🎯 Task: {activeTask.task_description}</span>
              <span className={`status-badge badge-${activeTask.status}`}>
                {activeTask.status === 'completed'
                  ? '✓ COMPLETED'
                  : activeTask.status === 'failed'
                  ? '✕ FAILED'
                  : `⏳ ${activeTask.status.toUpperCase()}`}
              </span>
            </div>

            {/* TASK SUMMARY & ERRORS */}
            {activeTask.status === 'failed' || activeTask.error ? (
              <div className="result-text error-box">
                <b>Failed:</b> {activeTask.error || activeTask.final_result || 'NVIDIA LLM task failed.'}
              </div>
            ) : activeTask.final_result ? (
              <div className="result-text">
                <b>Summary:</b> {activeTask.final_result}
              </div>
            ) : null}

            {activeTask.execution_log && activeTask.execution_log.length > 0 && (
              <div className="log-container">
                <div className="log-title">Execution Steps:</div>
                {activeTask.execution_log.map((log, i) => (
                  <div key={i} className="log-item">
                    <span className="log-step">Step {log.step || i+1}:</span>{' '}
                    <span className="log-tool">{log.tool || log.node}</span>{' '}
                    <span className="log-detail">{log.result || log.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* RECENT TASKS */}
        {history.length > 0 && (
          <div className="ai-history-section">
            <h4>Recent Tasks</h4>
            <div className="history-list">
              {history.slice(0, 5).map((item) => {
                const isFailed = item.status === 'failed' || (item.completed === false && Boolean(item.error));
                return (
                  <div key={item.task_id} className="history-item" onClick={() => setActiveTask(item)}>
                    <div className="history-desc">{item.task_description}</div>
                    <span className={`status-tag ${isFailed ? 'tag-failed' : 'tag-completed'}`}>
                      {isFailed ? 'Failed' : 'Completed'}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
