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
        sessionId: null,
        versionTag: "Live Sandbox",
        onFixError: null,
        onStatusChange: null,
        onLog: null,
      }, options);

      this.sessionId = this.options.sessionId || null;
      this.versionTag = this.options.versionTag || "Live Sandbox";
      this.routes = [];
      this.currentDevice = this.options.defaultDevice;
      this.currentUrl = this.options.defaultUrl;
      this.status = "ready"; // 'ready' | 'syncing' | 'executing'
      this.logs = [];
      this.activeLogFilter = "all";
      this.lastScrollY = 0;
      this.currentFiles = {};
      this.activeFile = "main.py";
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
              <div class="preview-version-pill" id="pv-version-pill" title="Active Code Version">${this.versionTag}</div>
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

          <!-- Quick Route Tester Bar (Discovered dynamically from runtime OpenAPI) -->
          <div class="preview-route-bar" id="pv-route-bar">
            <div class="preview-route-label">
              <svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2" fill="none"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              <span>Quick Test:</span>
            </div>
            <div class="preview-route-chips" id="pv-route-chips">
              <span class="preview-route-empty">Awaiting microservice build...</span>
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
      this.versionPill = document.getElementById("pv-version-pill");
      this.routeBar = document.getElementById("pv-route-bar");
      this.routeChips = document.getElementById("pv-route-chips");
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
              if (data.session_id) this.sessionId = data.session_id;
              if (data.version_tag) this.setVersion(data.version_tag);
              if (data.files) this.currentFiles = data.files;
              if (data.target_file) this.activeFile = data.target_file;
              if (data.routes && data.routes.length) this.renderRouteChips(data.routes);
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

    setSession(sessionId, versionTag = null) {
      this.sessionId = sessionId;
      if (versionTag) {
        this.setVersion(versionTag);
      }
      this.hotReload();
    }

    setVersion(tag) {
      this.versionTag = tag;
      if (this.versionPill) {
        this.versionPill.textContent = tag;
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
     * Real Sandboxed Live Preview with Reverse-Proxy Execution
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

      // 2. If no session exists, display awaiting build placeholder
      if (!this.sessionId) {
        this.iframe.removeAttribute("src");
        this.iframe.srcdoc = this.renderEmptyPlaceholder();
        return;
      }

      // 3. Reverse-proxy live sandbox routing
      const timestamp = Date.now();
      const proxyBase = `/api/preview/proxy/${this.sessionId}`;
      const hasUi = !!(this.currentFiles && this.currentFiles["index.html"]);

      // For pure APIs default to Swagger /docs; for web apps default to root /
      const targetUrl = hasUi
        ? `${proxyBase}/?t=${timestamp}`
        : `${proxyBase}/docs?t=${timestamp}`;

      this.currentUrl = hasUi ? `${proxyBase}/` : `${proxyBase}/docs`;
      if (this.urlInput) {
        this.urlInput.value = this.currentUrl;
      }

      this.iframe.removeAttribute("srcdoc");
      this.iframe.src = targetUrl;

      // 4. Restore scroll after load
      this.iframe.onload = () => {
        try {
          if (this.iframe.contentWindow && this.lastScrollY > 0) {
            this.iframe.contentWindow.scrollTo(0, this.lastScrollY);
          }
        } catch (e) {}
      };

      // 5. Query runtime OpenAPI route discovery
      this.fetchDiscoveredRoutes();
    }

    async fetchDiscoveredRoutes() {
      if (!this.sessionId) return;
      try {
        const res = await fetch(`/api/preview/routes/${this.sessionId}`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.version_tag) {
          this.setVersion(data.version_tag);
        }
        if (data.routes) {
          this.renderRouteChips(data.routes);
        }
      } catch (e) {
        console.debug("Failed fetching discovered routes:", e);
      }
    }

    renderRouteChips(routes) {
      if (!this.routeChips) return;
      this.routes = routes || [];
      if (!this.routes.length) {
        this.routeChips.innerHTML = '<span class="preview-route-empty">Auto-discovering live endpoints...</span>';
        return;
      }

      this.routeChips.innerHTML = this.routes.map(r => `
        <button class="route-test-chip ${r.method.toLowerCase()}" data-method="${r.method}" data-path="${r.path}" title="Quick Test ${r.method} ${r.path}">
          <span class="chip-method">${r.method}</span>
          <span class="chip-path">${this.escapeHtml(r.path)}</span>
        </button>
      `).join('');

      this.routeChips.querySelectorAll('.route-test-chip').forEach(btn => {
        btn.addEventListener('click', () => {
          const method = btn.dataset.method;
          const path = btn.dataset.path;
          this.executeQuickRouteTest(method, path);
        });
      });
    }

    async executeQuickRouteTest(method, rawPath) {
      if (!this.sessionId) return;
      this.setStatus("executing", "Testing");
      let targetPath = rawPath.replace('{key}', 'test-key').replace('{item_id}', '1');
      const url = `/api/preview/proxy/${this.sessionId}${targetPath}`;

      let body = null;
      const headers = {};
      if (["POST", "PUT", "PATCH"].includes(method)) {
        headers["Content-Type"] = "application/json";
        if (rawPath.includes("cache/set")) {
          body = JSON.stringify({ key: "test-key", value: "hello from TARA quick test", ttl: 60 });
        } else if (rawPath.includes("auth/token")) {
          body = JSON.stringify({ username: "developer", password: "tara_secure_pass", role: "admin" });
        } else if (rawPath.includes("auth/verify")) {
          body = JSON.stringify({ token: "test_token" });
        } else if (rawPath.includes("items")) {
          body = JSON.stringify({ name: "Quick Test Item", description: "Created via quick test button", payload: { active: true } });
        } else {
          body = JSON.stringify({ test: true });
        }
      }

      this.appendLog("info", `⚡ Quick Test: Sending ${method} ${targetPath}...`);
      if (this.consoleDrawer && this.consoleDrawer.classList.contains("collapsed")) {
        this.consoleDrawer.classList.remove("collapsed");
      }

      try {
        const res = await fetch(url, { method, headers, body });
        const statusText = `${res.status} ${res.statusText}`;
        let dataText = "";
        const contentType = res.headers.get("content-type") || "";
        if (contentType.includes("json")) {
          const json = await res.json();
          dataText = JSON.stringify(json, null, 2);
        } else {
          dataText = await res.text();
        }

        const logLvl = res.ok ? "info" : "warn";
        this.appendLog(logLvl, `[${statusText}] ${method} ${targetPath}\n${dataText.slice(0, 400)}`);
        this.setStatus("ready", "Ready");
      } catch (err) {
        this.appendLog("error", `Quick Test Failed (${method} ${targetPath}): ${err.message}`);
        this.setStatus("ready", "Error");
      }
    }

    renderEmptyPlaceholder() {
      return `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="UTF-8">
          <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
              font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, sans-serif;
              background: #09090B;
              color: #71717A;
              height: 100vh;
              display: flex;
              flex-direction: column;
              align-items: center;
              justify-content: center;
              text-align: center;
              padding: 24px;
              gap: 12px;
            }
            .icon-box {
              width: 44px;
              height: 44px;
              border-radius: 12px;
              background: #121215;
              border: 1px solid #27272A;
              display: flex;
              align-items: center;
              justify-content: center;
              color: #A1A1AA;
              margin-bottom: 4px;
            }
            h2 { font-size: 1.05rem; font-weight: 600; color: #E4E4E7; }
            p { font-size: 0.8rem; color: #71717A; max-width: 320px; line-height: 1.5; }
            .badge {
              display: inline-flex;
              align-items: center;
              gap: 6px;
              background: #18181B;
              border: 1px solid #27272A;
              color: #A1A1AA;
              font-size: 0.7rem;
              padding: 4px 10px;
              border-radius: 9999px;
              margin-top: 6px;
            }
          </style>
        </head>
        <body>
          <div class="icon-box">
            <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" stroke-width="1.8" fill="none"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
          </div>
          <h2>Live Sandbox Preview</h2>
          <p>Launch a pipeline to generate microservice code. TARA will execute the app in an isolated sandbox and stream interactive endpoints here.</p>
          <div class="badge">○ Awaiting Build Decision</div>
        </body>
        </html>
      `;
    }

    renderInitialPreview() {
      this.hotReload();
    }

    openInNewTab() {
      if (this.currentUrl && !this.currentUrl.startsWith("http://localhost:3000")) {
        window.open(this.currentUrl, "_blank");
      } else {
        const placeholder = this.renderEmptyPlaceholder();
        const blob = new Blob([placeholder], { type: "text/html" });
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank");
      }
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
