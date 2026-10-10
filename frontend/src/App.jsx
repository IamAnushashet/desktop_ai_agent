import React, { useState, useEffect } from 'react';
import './App.css';
import PermissionDialog from './components/PermissionDialog';

export default function App() {
  const [taskInput, setTaskInput] = useState('');
  const [activeTask, setActiveTask] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [history, setHistory] = useState([]);
  const [health, setHealth] = useState(null);
  const [pendingConfirmation, setPendingConfirmation] = useState(null);

  useEffect(() => {
    checkHealth();
    fetchHistory();
  }, []);

  const checkHealth = async () => {
    try {
      const res = await fetch('/api/agent/health');
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch (e) {
      setHealth({ success: false, message: 'Could not connect to backend health endpoint.' });
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch('/api/agent/history');
      if (res.ok) {
        const data = await res.json();
        setHistory(data.reverse());
      }
    } catch (e) {
      console.warn('History error:', e);
    }
  };

  // Poll task status and pending confirmations
  useEffect(() => {
    const timer = setInterval(async () => {
      // Check active task status
      if (activeTask && (activeTask.status === 'running' || activeTask.status === 'planning' || activeTask.status === 'executing' || activeTask.status === 'pending_confirmation')) {
        try {
          const res = await fetch(`/api/agent/status/${activeTask.task_id}`);
          if (res.ok) {
            const data = await res.json();
            setActiveTask(data);
            if (data.pending_confirmation) {
              setPendingConfirmation(data.pending_confirmation);
            }
          }
        } catch (e) {}
      }

      // Check pending confirmations
      try {
        const confRes = await fetch('/api/agent/confirmations/pending');
        if (confRes.ok) {
          const confData = await confRes.json();
          if (confData.confirmations && confData.confirmations.length > 0) {
            setPendingConfirmation(confData.confirmations[0]);
          } else {
            setPendingConfirmation(null);
          }
        }
      } catch (e) {}
    }, 1000);

    return () => clearInterval(timer);
  }, [activeTask]);

  const handleRunTask = async (e) => {
    if (e) e.preventDefault();
    const clean = taskInput.trim();
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
        fetchHistory();
      }
    } catch (err) {
      alert('Error starting task.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRespondConfirmation = async (confirmationId, action) => {
    setPendingConfirmation(null);
    try {
      await fetch(`/api/agent/confirmations/${confirmationId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
    } catch (e) {
      console.warn('Respond error:', e);
    }
  };

  return (
    <div className="laptop-app">
      <header className="laptop-header">
        <div className="logo-title">
          <span className="sparkle-icon">🤖</span>
          <h1>Desktop AI Agent Control Hub</h1>
        </div>
        {health && (
          <div className={`health-badge ${health.success ? 'badge-green' : 'badge-red'}`}>
            {health.success ? `🟢 ${health.model || 'NVIDIA Model Ready'}` : '🔴 Model Offline'}
          </div>
        )}
      </header>

      <main className="laptop-main">
        <section className="input-card">
          <h2>Task Orchestrator</h2>
          <form onSubmit={handleRunTask} className="task-form">
            <input
              type="text"
              className="task-input"
              placeholder="Enter task instruction (e.g. Open Word, create report, and close Word)..."
              value={taskInput}
              onChange={(e) => setTaskInput(e.target.value)}
            />
            <button type="submit" className="task-submit-btn" disabled={isSubmitting || !taskInput.trim()}>
              {isSubmitting ? 'Starting...' : 'Execute Task'}
            </button>
          </form>
        </section>

        {activeTask && (
          <section className={`active-task-card status-${activeTask.status}`}>
            <div className="card-top">
              <h3>🎯 Task: {activeTask.task_description}</h3>
              <span className={`status-pill pill-${activeTask.status}`}>
                {activeTask.status.toUpperCase()}
              </span>
            </div>

            {activeTask.final_result && (
              <div className="summary-box">
                <b>Result:</b> {activeTask.final_result}
              </div>
            )}

            {activeTask.execution_log && activeTask.execution_log.length > 0 && (
              <div className="logs-box">
                <h4>Execution Logs:</h4>
                <ul>
                  {activeTask.execution_log.map((log, i) => (
                    <li key={i}>
                      <span className="log-step">Step {log.step || i + 1}:</span>{' '}
                      <span className="log-tool">{log.tool || log.node}</span> - {log.result || log.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        {history.length > 0 && (
          <section className="history-section">
            <h3>Recent Execution History</h3>
            <div className="history-grid">
              {history.slice(0, 6).map((item) => (
                <div key={item.task_id} className="history-card" onClick={() => setActiveTask(item)}>
                  <div className="h-desc">{item.task_description}</div>
                  <div className="h-status">{item.status}</div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>

      <PermissionDialog
        confirmation={pendingConfirmation}
        onRespond={handleRespondConfirmation}
      />
    </div>
  );
}
