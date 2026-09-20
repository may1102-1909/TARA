import React, { useState, useEffect, useRef, useCallback } from 'react';
import './PreviewFrame.css';

/**
 * PreviewFrame — React Live App Preview Split Panel Component
 * Inspired by Davis AI Agent Platform UI design
 *
 * @param {Object} props
 * @param {string} props.url - Target preview URL (e.g. 'http://localhost:3000' or '/preview')
 * @param {Object} props.files - Virtual workspace files dictionary { [path]: content }
 * @param {string} props.activeFile - Currently active/target file
 * @param {Function} props.onFixError - Callback when user clicks '✨ Ask TARA to Fix Error'
 * @param {string} props.status - 'ready' | 'syncing' | 'executing'
 * @param {string} props.wsUrl - Optional explicit WebSocket URL for preview sync
 */
export default function PreviewFrame({
  url = 'http://localhost:3000',
  files = {},
  activeFile = 'index.html',
  onFixError = () => {},
  status: initialStatus = 'ready',
  wsUrl = null,
}) {
  const [device, setDevice] = useState('desktop'); // 'desktop' | 'tablet' | 'mobile'
  const [currentUrl, setCurrentUrl] = useState(url);
  const [status, setStatus] = useState(initialStatus);
  const [consoleOpen, setConsoleOpen] = useState(false);
  const [logs, setLogs] = useState([]);
  const [activeFilter, setActiveFilter] = useState('all');
  const [errorData, setErrorData] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [workspaceFiles, setWorkspaceFiles] = useState(files);
  const [currentActiveFile, setCurrentActiveFile] = useState(activeFile);

  const iframeRef = useRef(null);
  const lastScrollY = useRef(0);
  const socketRef = useRef(null);
  const consoleStreamRef = useRef(null);

  // Sync props to state if provided
  useEffect(() => {
    if (files && Object.keys(files).length > 0) {
      setWorkspaceFiles(files);
    }
  }, [files]);

  useEffect(() => {
    if (activeFile) {
      setCurrentActiveFile(activeFile);
    }
  }, [activeFile]);

  useEffect(() => {
    if (initialStatus) {
      setStatus(initialStatus);
    }
  }, [initialStatus]);

  // Helper to add log entries
  const addLog = useCallback((level, message, timeStr = null) => {
    const time = timeStr || new Date().toLocaleTimeString([], { hour12: false });
    setLogs((prev) => [...prev.slice(-300), { level, message, time }]);
  }, []);

  // Connect to WebSocket (/ws/preview) for real-time hot-reload payloads
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || '127.0.0.1:8000';
    const targetWs = wsUrl || `${protocol}//${host}/ws/preview`;

    try {
      const socket = new WebSocket(targetWs);
      socketRef.current = socket;

      socket.onopen = () => {
        addLog('info', 'Connected to Live Preview hot-reload WebSocket (/ws/preview)');
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'HOT_RELOAD') {
            setStatus('syncing');
            if (data.files) setWorkspaceFiles(data.files);
            if (data.target_file) setCurrentActiveFile(data.target_file);
            if (data.url) setCurrentUrl(data.url);
            setTimeout(() => setStatus('ready'), 350);
          } else if (data.type === 'STATUS_CHANGED' && data.status) {
            setStatus(data.status);
          }
        } catch (e) {
          console.error('Preview WebSocket message parsing error:', e);
        }
      };

      socket.onclose = () => {
        addLog('warn', 'Preview WebSocket disconnected. Reconnecting in 3s...');
      };
    } catch (err) {
      console.warn('Failed to initialize Preview WebSocket:', err);
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [wsUrl, addLog]);

  // Listen for postMessage from Sandboxed Iframe (bridge script)
  useEffect(() => {
    const handleMessage = (event) => {
      const data = event.data;
      if (!data || typeof data !== 'object') return;

      if (data.type === 'PREVIEW_CONSOLE_LOG') {
        addLog(data.level || 'info', data.message, data.time);
      } else if (data.type === 'PREVIEW_RUNTIME_ERROR') {
        setErrorData(data);
        setStatus('executing');
        addLog('error', `[Runtime Error] ${data.message} (${data.lineno || 1}:${data.colno || 1})`);
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [addLog]);

  // Auto-scroll console stream to bottom when logs update
  useEffect(() => {
    if (consoleStreamRef.current) {
      consoleStreamRef.current.scrollTop = consoleStreamRef.current.scrollHeight;
    }
  }, [logs, consoleOpen]);

  // Synthesize HTML bundle and perform virtual hot reload with scroll restoration
  const synthesizeAndReload = useCallback(() => {
    if (!iframeRef.current) return;

    // 1. Preserve scroll position
    try {
      if (iframeRef.current.contentWindow) {
        lastScrollY.current = iframeRef.current.contentWindow.scrollY || 0;
      }
    } catch (e) {
      lastScrollY.current = 0;
    }

    // 2. Injected bridge script for console interception & error boundary
    const bridgeScript = `
      <script>
        (function() {
          const _log = console.log, _warn = console.warn, _error = console.error, _info = console.info;
          function send(level, args) {
            try {
              const formatted = Array.from(args).map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ');
              window.parent.postMessage({ type: 'PREVIEW_CONSOLE_LOG', level, message: formatted, time: new Date().toLocaleTimeString([], { hour12: false }) }, '*');
            } catch(e) {}
          }
          console.log = function(...a) { _log(...a); send('info', a); };
          console.info = function(...a) { _info(...a); send('info', a); };
          console.warn = function(...a) { _warn(...a); send('warn', a); };
          console.error = function(...a) { _error(...a); send('error', a); };
          window.onerror = function(message, source, lineno, colno, error) {
            window.parent.postMessage({
              type: 'PREVIEW_RUNTIME_ERROR',
              message: String(message),
              source: String(source || ''),
              lineno: lineno || 1,
              colno: colno || 1,
              stack: error && error.stack ? String(error.stack) : ''
            }, '*');
            return false;
          };
          window.onunhandledrejection = function(event) {
            window.parent.postMessage({
              type: 'PREVIEW_RUNTIME_ERROR',
              message: 'Unhandled Rejection: ' + (event.reason ? (event.reason.message || String(event.reason)) : 'Promise rejected'),
              stack: event.reason && event.reason.stack ? String(event.reason.stack) : ''
            }, '*');
          };
        })();
      <\\/script>
    `;

    let html = '';
    const activeContent = workspaceFiles[currentActiveFile] || '';

    if (workspaceFiles['index.html']) {
      html = workspaceFiles['index.html'];
      if (workspaceFiles['style.css'] && !html.includes('<style>')) {
        html = html.replace('</head>', `<style>${workspaceFiles['style.css']}</style></head>`);
      }
      if (workspaceFiles['script.js'] && !html.includes(workspaceFiles['script.js'])) {
        html = html.replace('</body>', `<script>${workspaceFiles['script.js']}<\\/script></body>`);
      }
      html = html.includes('<head>') ? html.replace('<head>', `<head>${bridgeScript}`) : `${bridgeScript}${html}`;
    } else if (currentActiveFile.endsWith('.html') && activeContent) {
      html = activeContent.includes('<head>') ? activeContent.replace('<head>', `<head>${bridgeScript}`) : `${bridgeScript}${activeContent}`;
    } else {
      // Microservice / Python test harness
      html = `
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <title>TARA Live App Preview</title>
          ${bridgeScript}
          <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
              font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, sans-serif;
              background: #09090B;
              color: #F4F4F5;
              padding: 24px;
              min-height: 100vh;
              display: flex;
              flex-direction: column;
              gap: 16px;
            }
            .hero-card {
              background: #121215;
              border: 1px solid #27272A;
              border-radius: 12px;
              padding: 20px;
              display: flex;
              flex-direction: column;
              gap: 8px;
            }
            .hero-badge {
              display: inline-flex;
              align-items: center;
              gap: 6px;
              background: rgba(34, 197, 94, 0.1);
              color: #22C55E;
              border: 1px solid rgba(34, 197, 94, 0.2);
              font-size: 0.72rem;
              font-weight: 600;
              padding: 3px 8px;
              border-radius: 9999px;
              width: fit-content;
            }
            h1 { font-size: 1.25rem; font-weight: 600; color: #FFFFFF; }
            p { font-size: 0.82rem; color: #A1A1AA; line-height: 1.5; }
            .endpoint-grid { display: flex; flex-direction: column; gap: 10px; }
            .endpoint-row {
              background: #18181B;
              border: 1px solid #27272A;
              border-radius: 8px;
              padding: 12px 14px;
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 10px;
            }
            .ep-method {
              font-family: monospace;
              font-size: 0.75rem;
              font-weight: 700;
              color: #22C55E;
              background: rgba(34, 197, 94, 0.1);
              padding: 2px 6px;
              border-radius: 4px;
            }
            .ep-path { font-family: monospace; font-size: 0.8rem; color: #FFFFFF; flex: 1; }
            .btn-test {
              background: #FFFFFF;
              color: #09090B;
              border: none;
              font-size: 0.72rem;
              font-weight: 600;
              padding: 4px 10px;
              border-radius: 6px;
              cursor: pointer;
            }
            .response-box {
              background: #09090B;
              border: 1px solid #27272A;
              border-radius: 8px;
              padding: 12px;
              font-family: monospace;
              font-size: 0.75rem;
              color: #22C55E;
              min-height: 70px;
              max-height: 180px;
              overflow-y: auto;
              white-space: pre-wrap;
            }
          </style>
        </head>
        <body>
          <div class="hero-card">
            <span class="hero-badge">● SERVICE ACTIVE</span>
            <h1>TARA Microservice Preview</h1>
            <p>Live interactive test harness for <strong>${currentActiveFile}</strong>.</p>
          </div>
          <div class="endpoint-grid">
            <div class="endpoint-row">
              <span class="ep-method">GET</span>
              <span class="ep-path">/health</span>
              <button class="btn-test" onclick="testEndpoint('/health')">Execute</button>
            </div>
            <div class="endpoint-row">
              <span class="ep-method">GET</span>
              <span class="ep-path">/api/preview/status</span>
              <button class="btn-test" onclick="testEndpoint('/api/preview/status')">Execute</button>
            </div>
          </div>
          <div style="margin-top:4px;">
            <span style="font-size:0.68rem; text-transform:uppercase; color:#71717A; font-weight:600;">Live Response Output</span>
            <div class="response-box" id="resp-output">// Click 'Execute' to dispatch local request...</div>
          </div>
          <script>
            async function testEndpoint(endpoint) {
              const out = document.getElementById('resp-output');
              out.textContent = "Dispatching to " + endpoint + "...";
              try {
                const res = await fetch(endpoint);
                const data = await res.json();
                out.textContent = JSON.stringify(data, null, 2);
                console.log("Response from " + endpoint + ":", data);
              } catch(err) {
                out.textContent = "Error: " + err.message;
                console.error("Request failed: " + err.message);
              }
            }
          <\\/script>
        </body>
        </html>
      `;
    }

    // 3. Inject into iframe
    iframeRef.current.srcdoc = html;

    // 4. Restore scroll after load
    iframeRef.current.onload = () => {
      try {
        if (iframeRef.current?.contentWindow && lastScrollY.current > 0) {
          iframeRef.current.contentWindow.scrollTo(0, lastScrollY.current);
        }
      } catch (e) {}
    };
  }, [workspaceFiles, currentActiveFile]);

  // Re-render when files or activeFile changes
  useEffect(() => {
    synthesizeAndReload();
  }, [synthesizeAndReload]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setStatus('syncing');
    synthesizeAndReload();
    setTimeout(() => {
      setIsRefreshing(false);
      setStatus('ready');
    }, 450);
  };

  const handleOpenNewTab = () => {
    if (!iframeRef.current?.srcdoc) return;
    const blob = new Blob([iframeRef.current.srcdoc], { type: 'text/html' });
    const blobUrl = URL.createObjectURL(blob);
    window.open(blobUrl, '_blank');
  };

  const handleAskFix = () => {
    if (!errorData) return;
    const prompt = `Fix preview runtime error: "${errorData.message}" in ${errorData.source || currentActiveFile} at line ${errorData.lineno || 1}. Stack: ${errorData.stack || ''}`;
    setErrorData(null);
    setStatus('ready');
    onFixError(prompt, errorData);
  };

  const getStatusLabel = () => {
    switch (status) {
      case 'syncing':
        return '● Syncing';
      case 'executing':
        return '○ Executing';
      case 'ready':
      default:
        return '● Ready';
    }
  };

  const filteredLogs = activeFilter === 'all'
    ? logs
    : logs.filter((l) => l.level === activeFilter);

  const errorCount = logs.filter((l) => l.level === 'error').length;

  return (
    <div className="preview-card" id="tara-preview-card">
      {/* ── Top Header Bar (Davis UI Style) ── */}
      <div className="preview-header">
        <div className="preview-header-left">
          <div className="preview-url-box">
            <span className="preview-url-icon">
              <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </span>
            <input
              type="text"
              className="preview-url-input"
              value={currentUrl}
              onChange={(e) => setCurrentUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRefresh();
              }}
              spellCheck={false}
              title="Preview Target URL"
            />
          </div>

          <div className={`preview-status-badge ${status}`}>
            <span className="preview-status-dot" />
            <span>{getStatusLabel()}</span>
          </div>
        </div>

        <div className="preview-header-right">
          {/* Device Viewport Toggle Buttons */}
          <div className="preview-viewport-toggle">
            <button
              className={`viewport-btn ${device === 'desktop' ? 'active' : ''}`}
              onClick={() => setDevice('desktop')}
              title="Desktop (100%)"
            >
              <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="1.8" fill="none">
                <rect x="2" y="3" width="20" height="14" rx="2" />
                <line x1="8" y1="21" x2="16" y2="21" />
                <line x1="12" y1="17" x2="12" y2="21" />
              </svg>
              <span>100%</span>
            </button>
            <button
              className={`viewport-btn ${device === 'tablet' ? 'active' : ''}`}
              onClick={() => setDevice('tablet')}
              title="Tablet (768px)"
            >
              <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="1.8" fill="none">
                <rect x="4" y="2" width="16" height="20" rx="2" />
                <line x1="12" y1="18" x2="12.01" y2="18" />
              </svg>
              <span>768px</span>
            </button>
            <button
              className={`viewport-btn ${device === 'mobile' ? 'active' : ''}`}
              onClick={() => setDevice('mobile')}
              title="Mobile (375px)"
            >
              <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="1.8" fill="none">
                <rect x="5" y="2" width="14" height="20" rx="2" />
                <line x1="12" y1="18" x2="12.01" y2="18" />
              </svg>
              <span>375px</span>
            </button>
          </div>

          {/* Refresh Button */}
          <button
            className={`preview-action-btn ${isRefreshing ? 'spin' : ''}`}
            onClick={handleRefresh}
            title="Hot Reload Preview"
          >
            <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          </button>

          {/* Open in New Tab Button */}
          <button
            className="preview-action-btn"
            onClick={handleOpenNewTab}
            title="Open Preview in New Tab"
          >
            <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
          </button>

          {/* Toggle Console Drawer Button */}
          <button
            className="preview-action-btn console-toggle-btn"
            onClick={() => setConsoleOpen(!consoleOpen)}
            title="Toggle Console Drawer"
          >
            <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none">
              <polyline points="4 17 10 11 4 5" />
              <line x1="12" y1="19" x2="20" y2="19" />
            </svg>
            {errorCount > 0 && <span className="console-badge-count visible">{errorCount}</span>}
          </button>
        </div>
      </div>

      {/* ── Sandboxed Preview Stage ── */}
      <div className="preview-stage" id="pv-stage">
        <div className="preview-frame-wrapper" data-device={device}>
          <iframe
            ref={iframeRef}
            className="preview-iframe"
            sandbox="allow-scripts allow-same-origin allow-modals allow-forms"
            title="TARA Sandboxed Live Preview"
          />
        </div>

        {/* ── Dark-mode Error Boundary Alert Card Overlay ── */}
        {errorData && (
          <div className="preview-error-overlay active" id="pv-error-overlay">
            <div className="preview-error-card">
              <div className="preview-error-header">
                <div className="preview-error-title-row">
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <span>Application Runtime Error</span>
                </div>
                <button
                  className="preview-error-close"
                  onClick={() => setErrorData(null)}
                  title="Close"
                >
                  ✕
                </button>
              </div>
              <div className="preview-error-body">
                <div className="preview-error-msg">{errorData.message}</div>
                <div className="preview-error-location">
                  {errorData.source || currentActiveFile} (Line {errorData.lineno || 1}, Col {errorData.colno || 1})
                </div>
                <div className="preview-error-stack">
                  {errorData.stack || 'No stack trace available.'}
                </div>
              </div>
              <div className="preview-error-footer">
                <button
                  className="btn-dismiss-error"
                  onClick={() => {
                    setErrorData(null);
                    setStatus('ready');
                  }}
                >
                  Dismiss
                </button>
                <button className="btn-fix-error" onClick={handleAskFix}>
                  <span>✨ Ask TARA to Fix Error</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Collapsible Preview Console Logs Drawer ── */}
      <div className={`preview-console-drawer ${consoleOpen ? '' : 'collapsed'}`}>
        <div className="preview-console-bar">
          <div className="preview-console-title">
            <span>Console</span>
            <div className="preview-console-filters">
              {['all', 'info', 'warn', 'error'].map((filter) => (
                <button
                  key={filter}
                  className={`console-filter-btn ${activeFilter === filter ? 'active' : ''}`}
                  onClick={() => setActiveFilter(filter)}
                >
                  {filter === 'all' ? 'All' : filter === 'info' ? 'Logs' : filter === 'warn' ? 'Warnings' : 'Errors'}
                </button>
              ))}
            </div>
          </div>
          <div className="preview-console-actions">
            <button
              className="preview-action-btn"
              onClick={() => setLogs([])}
              title="Clear Console"
            >
              ✕
            </button>
            <button
              className="preview-action-btn"
              onClick={() => setConsoleOpen(false)}
              title="Collapse Console"
            >
              ⎯
            </button>
          </div>
        </div>
        <div className="preview-console-stream" ref={consoleStreamRef}>
          {filteredLogs.length === 0 ? (
            <div className="preview-log-entry info">
              <span className="preview-log-time">[{new Date().toLocaleTimeString([], { hour12: false })}]</span>
              <span className="preview-log-tag">[INIT]</span>
              <span>No console messages logged yet.</span>
            </div>
          ) : (
            filteredLogs.map((log, index) => (
              <div key={index} className={`preview-log-entry ${log.level}`}>
                <span className="preview-log-time">[{log.time}]</span>
                <span className="preview-log-tag">[{log.level.toUpperCase()}]</span>
                <span>{log.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
