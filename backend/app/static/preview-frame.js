/**
 * TARA Live App Preview Frame Component (Davis AI Agent Platform Style)
 * Sandboxed iframe engine, virtual hot-reloading, interactive console drawer,
 * device viewports, and dark-mode error boundary alert overlay.
 */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.PreviewFrameComponent = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  class PreviewFrameComponent {
    constructor(containerSelector, options = {}) {
      this.container = typeof containerSelector === "string"
        ? document.querySelector(containerSelector)
        : containerSelector;

      if (!this.container) {
        console.warn(`PreviewFrame: container "${containerSelector}" not found.`);
        return;
      }

      this.options = Object.assign({
        defaultUrl: "http://localhost:3000",
        defaultDevice: "desktop",
        onFixError: null,
        onStatusChange: null,
        onLog: null,
      }, options);

      this.currentDevice = this.options.defaultDevice;
      this.currentUrl = this.options.defaultUrl;
      this.status = "ready"; // 'ready' | 'syncing' | 'executing'
      this.logs = [];
      this.activeLogFilter = "all";
      this.lastScrollY = 0;
      this.currentFiles = {};
      this.activeFile = "index.html";
      this.currentError = null;
      this.socket = null;

      this.renderSkeleton();
      this.initElements();
      this.bindEvents();
      this.initPreviewWebSocket();
      this.renderInitialPreview();
    }

    renderSkeleton() {
      this.container.innerHTML = `
        <div class="preview-card" id="tara-preview-card">
          <!-- Top Header Bar (Davis UI Style) -->
          <div class="preview-header">
            <div class="preview-header-left">
              <div class="preview-url-box">
                <span class="preview-url-icon">
                  <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                </span>
                <input type="text" class="preview-url-input" id="pv-url-input" value="${this.currentUrl}" spellcheck="false" title="Preview Address" />
              </div>
              <div class="preview-status-badge ready" id="pv-status-badge">
                <span class="preview-status-dot"></span>
                <span id="pv-status-text">● Ready</span>
              </div>
            </div>

            <div class="preview-header-right">
              <!-- Device Viewport Toggle Buttons -->
              <div class="preview-viewport-toggle">
                <button class="viewport-btn active" data-device="desktop" id="pv-btn-desktop" title="Desktop (100%)">
                  <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="1.8" fill="none"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                  <span>100%</span>
                </button>
                <button class="viewport-btn" data-device="tablet" id="pv-btn-tablet" title="Tablet (768px)">
                  <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="1.8" fill="none"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
                  <span>768px</span>
                </button>
                <button class="viewport-btn" data-device="mobile" id="pv-btn-mobile" title="Mobile (375px)">
                  <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="1.8" fill="none"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
                  <span>375px</span>
                </button>
              </div>

              <!-- Action Buttons -->
              <button class="preview-action-btn" id="pv-btn-refresh" title="Hot Reload Preview">
                <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
              </button>
              <button class="preview-action-btn" id="pv-btn-newtab" title="Open Preview in New Tab">
                <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </button>
              <button class="preview-action-btn console-toggle-btn" id="pv-btn-toggle-console" title="Toggle Console Drawer">
                <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
                <span class="console-badge-count" id="pv-console-badge">0</span>
              </button>
            </div>
          </div>

          <!-- Preview Stage / Canvas -->
          <div class="preview-stage" id="pv-stage">
            <div class="preview-frame-wrapper" id="pv-frame-wrapper" data-device="desktop">
              <iframe
                id="tara-live-iframe"
                class="preview-iframe"
                sandbox="allow-scripts allow-same-origin allow-modals allow-forms"
                title="TARA Sandboxed Live Preview"
              ></iframe>
            </div>

            <!-- Dark-mode Error Boundary Alert Card Overlay -->
            <div class="preview-error-overlay" id="pv-error-overlay">
              <div class="preview-error-card">
                <div class="preview-error-header">
                  <div class="preview-error-title-row">
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    <span>Application Runtime Error</span>
                  </div>
                  <button class="preview-error-close" id="pv-btn-close-error">✕</button>
                </div>
                <div class="preview-error-body">
                  <div class="preview-error-msg" id="pv-error-msg">Uncaught TypeError: Cannot read properties of undefined</div>
                  <div class="preview-error-location" id="pv-error-location">src / App.jsx:42:12</div>
                  <div class="preview-error-stack" id="pv-error-stack">Stack trace loading...</div>
                </div>
                <div class="preview-error-footer">
                  <button class="btn-dismiss-error" id="pv-btn-dismiss-error">Dismiss</button>
                  <button class="btn-fix-error" id="pv-btn-ask-fix">
                    <span>✨ Ask TARA to Fix Error</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Collapsible Preview Console Logs Drawer -->
          <div class="preview-console-drawer collapsed" id="pv-console-drawer">
            <div class="preview-console-bar">
              <div class="preview-console-title">
                <span>Console</span>
                <div class="preview-console-filters">
                  <button class="console-filter-btn active" data-filter="all">All</button>
                  <button class="console-filter-btn" data-filter="info">Logs</button>
                  <button class="console-filter-btn" data-filter="warn">Warnings</button>
                  <button class="console-filter-btn" data-filter="error">Errors</button>
                </div>
              </div>
              <div class="preview-console-actions">
                <button class="preview-action-btn" id="pv-btn-clear-console" title="Clear Console">✕</button>
                <button class="preview-action-btn" id="pv-btn-collapse-console" title="Collapse Console">⎯</button>
              </div>
            </div>
            <div class="preview-console-stream" id="pv-console-stream">
              <div class="preview-log-entry info">
                <span class="preview-log-time">[00:00]</span>
                <span class="preview-log-tag">[INIT]</span>
                <span>Live sandboxed preview engine attached.</span>
              </div>
            </div>
          </div>
        </div>
      `;
    }

    initElements() {
      this.iframe = document.getElementById("tara-live-iframe");
      this.frameWrapper = document.getElementById("pv-frame-wrapper");
      this.urlInput = document.getElementById("pv-url-input");
      this.statusBadge = document.getElementById("pv-status-badge");
      this.statusText = document.getElementById("pv-status-text");
      this.btnDesktop = document.getElementById("pv-btn-desktop");
      this.btnTablet = document.getElementById("pv-btn-tablet");
      this.btnMobile = document.getElementById("pv-btn-mobile");
      this.btnRefresh = document.getElementById("pv-btn-refresh");
      this.btnNewTab = document.getElementById("pv-btn-newtab");
      this.btnToggleConsole = document.getElementById("pv-btn-toggle-console");
      this.consoleBadge = document.getElementById("pv-console-badge");
      this.consoleDrawer = document.getElementById("pv-console-drawer");
      this.consoleStream = document.getElementById("pv-console-stream");
      this.btnClearConsole = document.getElementById("pv-btn-clear-console");
      this.btnCollapseConsole = document.getElementById("pv-btn-collapse-console");
      this.errorOverlay = document.getElementById("pv-error-overlay");
      this.errorMsg = document.getElementById("pv-error-msg");
      this.errorLocation = document.getElementById("pv-error-location");
      this.errorStack = document.getElementById("pv-error-stack");
      this.btnAskFix = document.getElementById("pv-btn-ask-fix");
      this.btnDismissError = document.getElementById("pv-btn-dismiss-error");
      this.btnCloseError = document.getElementById("pv-btn-close-error");
    }

    bindEvents() {
      // Viewport Switcher
      [this.btnDesktop, this.btnTablet, this.btnMobile].forEach(btn => {
        if (!btn) return;
        btn.addEventListener("click", () => {
          const device = btn.dataset.device;
          this.setDevice(device);
        });
      });

      // Refresh Button
      if (this.btnRefresh) {
        this.btnRefresh.addEventListener("click", () => {
          this.btnRefresh.classList.add("spin");
          this.setStatus("syncing", "Syncing");
          this.hotReload();
          setTimeout(() => {
            this.btnRefresh.classList.remove("spin");
            this.setStatus("ready", "Ready");
          }, 450);
        });
      }

      // Open in New Tab
      if (this.btnNewTab) {
        this.btnNewTab.addEventListener("click", () => {
          this.openInNewTab();
        });
      }

      // URL bar Enter key navigation
      if (this.urlInput) {
        this.urlInput.addEventListener("keydown", (e) => {
          if (e.key === "Enter") {
            this.currentUrl = this.urlInput.value.trim() || "http://localhost:3000";
            this.hotReload();
          }
        });
      }

      // Toggle Console Drawer
      if (this.btnToggleConsole) {
        this.btnToggleConsole.addEventListener("click", () => {
          this.toggleConsole();
        });
      }
      if (this.btnCollapseConsole) {
        this.btnCollapseConsole.addEventListener("click", () => {
          this.toggleConsole(false);
        });
      }
      if (this.btnClearConsole) {
        this.btnClearConsole.addEventListener("click", () => {
          this.clearConsole();
        });
      }

      // Console Filter Buttons
      const filterBtns = this.container.querySelectorAll(".console-filter-btn");
      filterBtns.forEach(btn => {
        btn.addEventListener("click", () => {
          filterBtns.forEach(b => b.classList.remove("active"));
          btn.classList.add("active");
          this.activeLogFilter = btn.dataset.filter || "all";
          this.renderLogs();
        });
      });

      // Error overlay actions
      if (this.btnDismissError) {
        this.btnDismissError.addEventListener("click", () => {
          this.hideErrorOverlay();
        });
      }
      if (this.btnCloseError) {
        this.btnCloseError.addEventListener("click", () => {
          this.hideErrorOverlay();
        });
      }
      if (this.btnAskFix) {
        this.btnAskFix.addEventListener("click", () => {
          this.triggerAskFix();
        });
      }

      // Listen for postMessage from Sandboxed iframe
      window.addEventListener("message", (event) => {
        const data = event.data;
        if (!data || typeof data !== "object") return;

        if (data.type === "PREVIEW_CONSOLE_LOG") {
          this.appendLog(data.level || "info", data.message, data.time);
        } else if (data.type === "PREVIEW_RUNTIME_ERROR") {
          this.showErrorOverlay(data);
          this.appendLog("error", `[Runtime Error] ${data.message} (${data.lineno}:${data.colno})`);
        }
      });
    }

    setDevice(device) {
      this.currentDevice = device;
      [this.btnDesktop, this.btnTablet, this.btnMobile].forEach(btn => {
        if (!btn) return;
        btn.classList.toggle("active", btn.dataset.device === device);
      });
      if (this.frameWrapper) {
        this.frameWrapper.dataset.device = device;
      }
    }

    setStatus(status, label) {
      this.status = status;
      if (this.statusBadge) {
        this.statusBadge.className = `preview-status-badge ${status}`;
      }
      if (this.statusText) {
        let displayLabel = label;
        if (!displayLabel) {
          if (status === "syncing") displayLabel = "● Syncing";
          else if (status === "ready") displayLabel = "● Ready";
          else if (status === "executing") displayLabel = "○ Executing";
          else displayLabel = status.charAt(0).toUpperCase() + status.slice(1);
        }
        this.statusText.textContent = displayLabel;
      }
      if (typeof this.options.onStatusChange === "function") {
        this.options.onStatusChange(status, label);
      }
    }

    toggleConsole(show) {
      if (!this.consoleDrawer) return;
      const isCollapsed = this.consoleDrawer.classList.contains("collapsed");
      const shouldShow = show !== undefined ? show : isCollapsed;
      if (shouldShow) {
        this.consoleDrawer.classList.remove("collapsed");
      } else {
        this.consoleDrawer.classList.add("collapsed");
      }
    }

    appendLog(level, message, timeStr = null) {
      const time = timeStr || new Date().toLocaleTimeString([], { hour12: false });
      const logEntry = { level, message, time };
      this.logs.push(logEntry);
      if (this.logs.length > 300) this.logs.shift();

      this.renderLogs();

      // Update badge if error or warn
      const errorCount = this.logs.filter(l => l.level === "error").length;
      if (this.consoleBadge) {
        if (errorCount > 0) {
          this.consoleBadge.textContent = errorCount;
          this.consoleBadge.classList.add("visible");
        } else {
          this.consoleBadge.classList.remove("visible");
        }
      }

      if (typeof this.options.onLog === "function") {
        this.options.onLog(logEntry);
      }
    }

    clearConsole() {
      this.logs = [];
      if (this.consoleStream) {
        this.consoleStream.innerHTML = "";
      }
      if (this.consoleBadge) {
        this.consoleBadge.classList.remove("visible");
      }
    }

    renderLogs() {
      if (!this.consoleStream) return;
      const filtered = this.activeLogFilter === "all"
        ? this.logs
        : this.logs.filter(l => l.level === this.activeLogFilter);

      this.consoleStream.innerHTML = filtered.map(log => `
        <div class="preview-log-entry ${log.level}">
          <span class="preview-log-time">[${this.escapeHtml(log.time)}]</span>
          <span class="preview-log-tag">[${log.level.toUpperCase()}]</span>
          <span>${this.escapeHtml(log.message)}</span>
        </div>
      `).join("");

      this.consoleStream.scrollTop = this.consoleStream.scrollHeight;
    }

    showErrorOverlay(errData) {
      this.currentError = errData;
      if (this.errorMsg) {
        this.errorMsg.textContent = errData.message || "An uncaught runtime error occurred in preview.";
      }
      if (this.errorLocation) {
        const file = errData.source || this.activeFile || "App.js";
        this.errorLocation.textContent = `${file} (Line ${errData.lineno || 1}, Col ${errData.colno || 1})`;
      }
      if (this.errorStack) {
        this.errorStack.textContent = errData.stack || errData.message || "No stack trace available.";
      }
      if (this.errorOverlay) {
        this.errorOverlay.classList.add("active");
      }
      this.setStatus("executing", "Error");
    }

    hideErrorOverlay() {
      this.currentError = null;
      if (this.errorOverlay) {
        this.errorOverlay.classList.remove("active");
      }
      this.setStatus("ready", "Ready");
    }

    triggerAskFix() {
      if (!this.currentError) return;
      const prompt = `Fix preview runtime error: "${this.currentError.message}" in ${this.currentError.source || this.activeFile || "main.py"} at line ${this.currentError.lineno || 1}. Stack: ${this.currentError.stack || ""}`;
      this.hideErrorOverlay();
      if (typeof this.options.onFixError === "function") {
        this.options.onFixError(prompt, this.currentError);
      }
    }

    initPreviewWebSocket() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host || "127.0.0.1:8000";
      const wsUrl = `${protocol}//${host}/ws/preview`;

      try {
        this.socket = new WebSocket(wsUrl);
        this.socket.onopen = () => {
          this.appendLog("info", "Connected to Live Preview hot-reload WebSocket (/ws/preview)");
        };

        this.socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "HOT_RELOAD") {
              this.setStatus("syncing", "Syncing");
              if (data.files) this.currentFiles = data.files;
              if (data.target_file) this.activeFile = data.target_file;
              this.hotReload();
              setTimeout(() => this.setStatus("ready", "Ready"), 350);
            }
          } catch (e) {
            console.error("Preview socket parse error:", e);
          }
        };

        this.socket.onclose = () => {
          setTimeout(() => this.initPreviewWebSocket(), 3000);
        };
      } catch (err) {
        console.warn("Live preview WebSocket init failed:", err);
      }
    }

    setFiles(files, activeFile = null) {
      if (files) this.currentFiles = files;
      if (activeFile) this.activeFile = activeFile;
      this.hotReload();
    }

    updateFile(filename, content) {
      this.currentFiles[filename] = content;
      this.activeFile = filename;
      this.hotReload();
    }

    /**
     * Virtual Hot Reload Engine with scroll preservation and injected bridge
     */
    hotReload() {
      if (!this.iframe) return;

      // 1. Preserve scroll position
      try {
        if (this.iframe.contentWindow) {
          this.lastScrollY = this.iframe.contentWindow.scrollY || 0;
        }
      } catch (e) {
        this.lastScrollY = 0;
      }

      // 2. Synthesize complete sandboxed document
      const htmlContent = this.synthesizeBundle();

      // 3. Inject into iframe
      this.iframe.srcdoc = htmlContent;

      // 4. Restore scroll after load
      this.iframe.onload = () => {
        try {
          if (this.iframe.contentWindow && this.lastScrollY > 0) {
            this.iframe.contentWindow.scrollTo(0, this.lastScrollY);
          }
        } catch (e) {}
      };
    }

    synthesizeBundle() {
      const files = this.currentFiles || {};
      const activeContent = files[this.activeFile] || "";

      // Injected bridge script for console interception & error boundary
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
        <\/script>
      `;

      // Check if user project provides an index.html or web files
      if (files["index.html"]) {
        let html = files["index.html"];
        // Inject CSS if style.css exists
        if (files["style.css"] && !html.includes("<style>")) {
          html = html.replace("</head>", `<style>${files["style.css"]}</style></head>`);
        }
        // Inject JS if script.js or app.js exists
        if (files["script.js"] && !html.includes(files["script.js"])) {
          html = html.replace("</body>", `<script>${files["script.js"]}<\/script></body>`);
        }
        if (html.includes("<head>")) {
          return html.replace("<head>", `<head>${bridgeScript}`);
        }
        return `${bridgeScript}${html}`;
      }

      // Check if viewing an HTML file directly
      if (this.activeFile.endsWith(".html") && activeContent) {
        if (activeContent.includes("<head>")) {
          return activeContent.replace("<head>", `<head>${bridgeScript}`);
        }
        return `${bridgeScript}${activeContent}`;
      }

      // If project has Python / FastAPI or backend microservice: Render interactive Live API Runner Page
      return this.renderMockApiRunner(files, bridgeScript);
    }

    renderMockApiRunner(files, bridgeScript) {
      const activeFile = this.activeFile || "main.py";
      const code = files[activeFile] || "";
      const isPython = activeFile.endsWith(".py");

      return `
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
            .endpoint-grid {
              display: flex;
              flex-direction: column;
              gap: 10px;
            }
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
            .ep-path {
              font-family: monospace;
              font-size: 0.8rem;
              color: #FFFFFF;
              flex: 1;
            }
            .btn-test {
              background: #FFFFFF;
              color: #09090B;
              border: none;
              font-size: 0.72rem;
              font-weight: 600;
              padding: 4px 10px;
              border-radius: 6px;
              cursor: pointer;
              transition: opacity 150ms ease;
            }
            .btn-test:hover { opacity: 0.9; }
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
            <p>Live interactive test harness for <strong>${this.escapeHtml(activeFile)}</strong>. Requests dispatched directly to local runtime on <code>http://127.0.0.1:8000</code>.</p>
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
            <div class="endpoint-row">
              <span class="ep-method">POST</span>
              <span class="ep-path">/api/tara/edit (Mock Test)</span>
              <button class="btn-test" onclick="testEndpoint('/api/tara/status')">Execute</button>
            </div>
          </div>

          <div style="margin-top:4px;">
            <span style="font-size:0.68rem; text-transform:uppercase; color:#71717A; font-weight:600; letter-spacing:0.04em;">Live Response Output</span>
            <div class="response-box" id="resp-output">// Click 'Execute' above to test local endpoints...</div>
          </div>

          <script>
            console.log("Interactive Live Preview initialized for " + ${JSON.stringify(activeFile)});
            async function testEndpoint(endpoint) {
              const out = document.getElementById('resp-output');
              out.textContent = "Dispatching request to " + endpoint + "...";
              console.log("Testing endpoint: " + endpoint);
              try {
                const res = await fetch(endpoint);
                const data = await res.json();
                out.textContent = JSON.stringify(data, null, 2);
                console.log("Response received from " + endpoint + ":", data);
              } catch(err) {
                out.textContent = "Error: " + err.message;
                console.error("Endpoint request failed: " + err.message);
              }
            }
          <\/script>
        </body>
        </html>
      `;
    }

    renderInitialPreview() {
      this.hotReload();
    }

    openInNewTab() {
      const html = this.synthesizeBundle();
      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    }

    escapeHtml(str) {
      if (!str) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }
  }

  return PreviewFrameComponent;
});
