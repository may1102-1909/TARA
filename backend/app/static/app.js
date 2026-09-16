/**
 * TARA Web IDE Client Application
 * AI Developer Environment & Autonomous Architecture Assistant
 */

const PRESETS = {
  cache: `# PRD: High-Performance In-Memory Cache Microservice

## Overview
A lightweight, in-memory caching microservice written in standard Python 3.11+.

## Functional Requirements
1. Key-value store supporting string keys and arbitrary JSON payloads.
2. Configurable TTL (time-to-live) per key with automated background expiration.
3. Thread-safe operations for concurrent reads and writes.
4. Health check and cache metrics endpoint.

## Non-Functional Requirements
- Minimal external dependencies; favor Python standard library.
- Strict input validation to prevent injection or corruption.
`,
  auth: `# PRD: Authentication & Token Validation Service

## Overview
A modular Python authentication microservice for issuing and verifying signed tokens.

## Requirements
1. Payload hashing and secure credential verification.
2. Token generation with claims, expiration, and role validation.
3. In-memory sliding window rate-limiter per client identifier.
4. Standardized error envelopes and security audit logging.
`,
  webhook: `# PRD: Reliable Webhook Dispatcher Service

## Overview
An asynchronous webhook dispatcher with exponential backoff and payload signing.

## Requirements
1. Receive outgoing event payloads and dispatch to subscriber endpoints.
2. HMAC-SHA256 signature calculation in request headers.
3. Retry queue with max retry limits and backoff jitter.
4. Dead-letter queue tracking for permanently failed dispatches.
`
};

class TaraIDE {
  constructor() {
    this.sessionId = "tara-" + Math.random().toString(36).substring(2, 10);
    this.currentSession = null;
    this.editor = null;
    this.activeFile = "main.py";
    this.activeAgentFilter = "all";
    this.activePersona = "antigravity";
    this.allLogs = [];
    this.socket = null;
    this.securitySocket = null;
    this.streamSocket = null;
    this.latestPatchedDiff = null;
    this.activeBotMsgBody = null;

    this.initElements();
    this.initMonaco();
    this.initTaraWebSocket();
    this.initTaraStreamWebSocket();
    this.initSecurityWebSocket();
    this.bindEvents();
    this.applyPreset("cache");
    this.updateSessionBadge();
  }

  initElements() {
    // Top & Header
    this.sessionBadgeText = document.getElementById("session-id-text");
    this.btnDownloadZip = document.getElementById("btn-download-zip");

    // Dock & Panels
    this.primarySidebar = document.getElementById("primary-sidebar");
    this.copilotPanel = document.getElementById("copilot-panel");
    this.consoleDrawer = document.getElementById("console-drawer");

    // Dock Buttons
    this.dockBtnSpec = document.getElementById("dock-btn-spec");
    this.dockBtnFiles = document.getElementById("dock-btn-files");
    this.dockBtnEditor = document.getElementById("dock-btn-editor");
    this.dockBtnDiff = document.getElementById("dock-btn-diff");
    this.dockBtnAudit = document.getElementById("dock-btn-audit");
    this.dockBtnTerminal = document.getElementById("dock-btn-terminal");
    this.dockBtnCopilotToggle = document.getElementById("dock-btn-copilot-toggle");
    this.dockFilesCount = document.getElementById("dock-files-count");

    // Sidebar Spec & Files
    this.prdTextarea = document.getElementById("prd-input-textarea");
    this.prdCharCounter = document.getElementById("prd-char-counter");
    this.presetSelect = document.getElementById("preset-select");
    this.btnStartPipeline = document.getElementById("btn-start-pipeline");
    this.dropZone = document.getElementById("drop-zone");
    this.fileUploadInput = document.getElementById("file-upload-input");
    this.fileTreeContainer = document.getElementById("file-tree-container");
    this.filesCountBadge = document.getElementById("files-count-badge");
    this.filesTagTotal = document.getElementById("files-tag-total");

    // Canvas Stage
    this.activeFilenamePill = document.getElementById("active-filename-pill");
    this.stageStatusText = document.getElementById("stage-status-text");
    this.btnRunCode = document.getElementById("btn-run-code");
    this.btnRunStrixScan = document.getElementById("btn-run-strix-scan");
    this.consoleLogStream = document.getElementById("console-log-stream");
    this.btnToggleConsole = document.getElementById("btn-toggle-console");

    // Monaco Diff elements
    this.diffFileSelector = document.getElementById("diff-file-selector");
    this.diffStageButtons = document.querySelectorAll(".diff-stage-btn");
    this.btnToggleDiffInline = document.getElementById("btn-toggle-diff-inline");
    this.btnAcceptPatch = document.getElementById("btn-accept-patch");
    this.diffContainerPrimary = document.getElementById("monaco-diff-primary");
    this.diffContainerSecondary = document.getElementById("monaco-diff-secondary");
    this.activeDiffStage = "dev-qa";
    this.diffRenderSideBySide = true;
    this.diffEditorPrimary = null;
    this.diffEditorSecondary = null;

    // Audit view
    this.auditContentContainer = document.getElementById("audit-content-container");

    // Right AI Copilot
    this.copilotChatStream = document.getElementById("copilot-chat-stream");
    this.copilotPromptInput = document.getElementById("copilot-prompt-input");
    this.copilotTargetDisplay = document.getElementById("copilot-target-display");
    this.btnSendCopilot = document.getElementById("btn-send-copilot");
    this.btnClearCopilot = document.getElementById("btn-clear-copilot");
    this.btnCloseCopilot = document.getElementById("btn-close-copilot");
    this.copilotChips = document.querySelectorAll(".copilot-chip");
    this.personaChips = document.querySelectorAll(".persona-chip");

    // Modal elements (Approval Gate)
    this.approvalModal = document.getElementById("approval-gate-modal");
    this.modalVerdictText = document.getElementById("modal-verdict-text");
    this.modalMarketText = document.getElementById("modal-market-text");
    this.modalGapsList = document.getElementById("modal-gaps-list");
    this.modalFlawsList = document.getElementById("modal-flaws-list");
    this.modalRecommendationText = document.getElementById("modal-recommendation-text");
    this.modalRevisionPill = document.getElementById("modal-revision-pill");
    this.feedbackNotesInput = document.getElementById("feedback-notes-input");
    this.btnGateApprove = document.getElementById("btn-gate-approve");
    this.btnGateRequestChanges = document.getElementById("btn-gate-request-changes");
    this.btnGateReject = document.getElementById("btn-gate-reject");
  }

  initMonaco() {
    const container = document.getElementById("monaco-editor-container");
    const fallback = document.getElementById("fallback-editor-container");
    const diffContainerPrimary = document.getElementById("monaco-diff-primary");
    const diffContainerSecondary = document.getElementById("monaco-diff-secondary");

    if (window.require) {
      window.require.config({ paths: { vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs" } });
      window.require(["vs/editor/editor.main"], () => {
        // Main Code Editor
        this.editor = monaco.editor.create(container, {
          value: "# TARA Autonomous AI Developer Environment\n# Awaiting PRD input or Antigravity prompt to inspect & generate code...",
          language: "python",
          theme: "vs-dark",
          fontSize: 13,
          fontFamily: "'JetBrains Mono', monospace",
          minimap: { enabled: false },
          automaticLayout: true,
          scrollBeyondLastLine: false,
          padding: { top: 12, bottom: 12 },
          readOnly: false,
        });

        // Live Code Editing sync
        this.editor.onDidChangeModelContent(() => {
          if (this.activeFile && this.currentSession) {
            const updated = this.editor.getValue();
            if (!this.currentSession.security_patches) this.currentSession.security_patches = {};
            this.currentSession.security_patches[this.activeFile] = updated;
            if (this.currentSession.qa_refactored_files) this.currentSession.qa_refactored_files[this.activeFile] = updated;
            if (this.currentSession.dev_code_files) this.currentSession.dev_code_files[this.activeFile] = updated;
          }
        });

        // Native Monaco Diff Editors
        if (diffContainerPrimary && monaco.editor.createDiffEditor) {
          this.diffEditorPrimary = monaco.editor.createDiffEditor(diffContainerPrimary, {
            enableSplitViewResizing: true,
            renderSideBySide: this.diffRenderSideBySide,
            readOnly: true,
            theme: "vs-dark",
            automaticLayout: true,
            fontSize: 12,
            fontFamily: "'JetBrains Mono', monospace",
            scrollBeyondLastLine: false,
            originalEditable: false,
          });
        }

        if (diffContainerSecondary && monaco.editor.createDiffEditor) {
          this.diffEditorSecondary = monaco.editor.createDiffEditor(diffContainerSecondary, {
            enableSplitViewResizing: true,
            renderSideBySide: this.diffRenderSideBySide,
            readOnly: true,
            theme: "vs-dark",
            automaticLayout: true,
            fontSize: 12,
            fontFamily: "'JetBrains Mono', monospace",
            scrollBeyondLastLine: false,
            originalEditable: false,
          });
        }
      });
    } else {
      container.style.display = "none";
      fallback.style.display = "block";
    }
  }

  initTaraWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host || "127.0.0.1:8000";
    const wsUrl = `${protocol}//${host}/ws/tara`;

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.appendLog("ANTIGRAVITY", "Connected to TARA Antigravity WebSocket stream (/ws/tara)");
      };

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleTaraSocketMessage(data);
        } catch (e) {
          console.error("Failed to parse WebSocket message:", e);
        }
      };

      this.socket.onerror = (err) => {
        console.warn("TARA WebSocket notice:", err);
      };

      this.socket.onclose = () => {
        setTimeout(() => {
          if (!this.socket || this.socket.readyState === WebSocket.CLOSED) {
            this.initTaraWebSocket();
          }
        }, 5000);
      };
    } catch (e) {
      console.warn("Could not establish WebSocket to /ws/tara:", e);
    }
  }

  handleTaraSocketMessage(data) {
    if (!data || !data.type) return;

    switch (data.type) {
      case "init":
        this.appendLog("ANTIGRAVITY", `Runtime connected. Workspace: ${data.workspace || "active root"}`);
        break;

      case "status":
        if (data.status === "processing_prompt") {
          this.stageStatusText.textContent = "Agent Executing...";
        } else if (data.status === "agent_ready") {
          this.stageStatusText.textContent = "Agent Ready";
        }
        break;

      case "thought":
        this.appendLog("ANTIGRAVITY", `💭 Thinking: ${data.content}`);
        if (this.activeBotMsgBody) {
          let thoughtBox = this.activeBotMsgBody.querySelector(".thought-box");
          if (!thoughtBox) {
            thoughtBox = document.createElement("div");
            thoughtBox.className = "thought-box";
            thoughtBox.innerHTML = `<span class="thought-title">💭 Thinking Process</span><div class="thought-content"></div>`;
            this.activeBotMsgBody.insertBefore(thoughtBox, this.activeBotMsgBody.firstChild);
          }
          const content = thoughtBox.querySelector(".thought-content");
          if (content) content.textContent = data.content;
        }
        break;

      case "tool_call":
        const name = data.data?.name || "tool";
        const args = JSON.stringify(data.data?.args || {});
        this.appendLog("ANTIGRAVITY", `🔧 Tool Invocation: ${name}(${args})`);
        if (this.activeBotMsgBody) {
          const toolBadge = document.createElement("div");
          toolBadge.className = "tool-badge-pill";
          toolBadge.innerHTML = `<span>🔧</span><code>${name}</code>`;
          this.activeBotMsgBody.appendChild(toolBadge);
          this.scrollCopilotToBottom();
        }
        break;

      case "token":
        if (this.activeBotMsgBody) {
          let tokenSpan = this.activeBotMsgBody.querySelector(".bot-token-text");
          if (!tokenSpan) {
            tokenSpan = document.createElement("p");
            tokenSpan.className = "bot-token-text";
            this.activeBotMsgBody.appendChild(tokenSpan);
          }
          tokenSpan.textContent += data.content;
          this.scrollCopilotToBottom();
        }
        break;

      case "diff_stream_start":
        this.appendLog("ANTIGRAVITY", `📝 Streaming live diff for ${data.filename} (+${data.additions}, -${data.deletions})`);
        break;

      case "diff_line":
        this.appendLog("ANTIGRAVITY", `  ${data.line}`);
        break;

      case "file_diff":
        if (data.diff && this.diffEditorPrimary && window.monaco) {
          const diff = data.diff;
          const lang = diff.filename && diff.filename.endsWith(".py") ? "python" : "plaintext";
          this.diffEditorPrimary.setModel({
            original: monaco.editor.createModel(diff.original || "", lang),
            modified: monaco.editor.createModel(diff.modified || "", lang),
          });
          this.appendLog("ANTIGRAVITY", `✅ Loaded live diff into Monaco Editor for ${diff.filename}`);
          this.layoutDiffEditors();

          // Offer quick diff button inside copilot stream
          if (this.activeBotMsgBody) {
            const diffNotice = document.createElement("div");
            diffNotice.className = "copilot-diff-notice";
            diffNotice.innerHTML = `
              <div style="display:flex; align-items:center; justify-content:space-between; background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.3); padding:8px 10px; border-radius:6px; margin-top:6px;">
                <span style="color:#34d399; font-size:0.75rem;">✨ Diffs produced for <strong>${diff.filename}</strong> (+${diff.additions}, -${diff.deletions})</span>
                <button class="btn btn-sm btn-sandbox" style="padding:2px 8px; font-size:0.7rem;" onclick="document.getElementById('tab-diff-view').click();">View Diff ➔</button>
              </div>
            `;
            this.activeBotMsgBody.appendChild(diffNotice);
            this.scrollCopilotToBottom();
          }
        }
        break;

      case "diff_stream_end":
        this.appendLog("ANTIGRAVITY", `✨ Completed diff stream for ${data.filename}`);
        break;

      case "complete":
        this.appendLog("ANTIGRAVITY", `🎉 Agent task finished successfully.`);
        this.stageStatusText.textContent = "Agent Finished";
        if (this.activeBotMsgBody) {
          this.activeBotMsgBody = null;
        }
        break;

      case "error":
        this.appendLog("ANTIGRAVITY", `❌ Agent execution error: ${data.error}`);
        this.stageStatusText.textContent = "Agent Error";
        if (this.activeBotMsgBody) {
          const errP = document.createElement("p");
          errP.style.color = "var(--accent-rose)";
          errP.textContent = `❌ ${data.error}`;
          this.activeBotMsgBody.appendChild(errP);
          this.activeBotMsgBody = null;
        }
        break;
    }
  }

  initTaraStreamWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host || "127.0.0.1:8000";
    const wsUrl = `${protocol}//${host}/ws/tara/stream`;

    try {
      this.streamSocket = new WebSocket(wsUrl);

      this.streamSocket.onopen = () => {
        this.appendLog("ANTIGRAVITY", "⚡ Connected to TARA Token-by-Token Stream (/ws/tara/stream)");
      };

      this.streamSocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleTaraStreamMessage(data);
        } catch (e) {
          console.error("Failed to parse stream WebSocket message:", e);
        }
      };

      this.streamSocket.onerror = (err) => {
        console.warn("TARA Stream WebSocket notice:", err);
      };

      this.streamSocket.onclose = () => {
        setTimeout(() => {
          if (!this.streamSocket || this.streamSocket.readyState === WebSocket.CLOSED) {
            this.initTaraStreamWebSocket();
          }
        }, 5000);
      };
    } catch (e) {
      console.warn("Could not establish WebSocket to /ws/tara/stream:", e);
    }
  }

  handleTaraStreamMessage(data) {
    if (!data || !data.type) return;

    switch (data.type) {
      case "STREAM_INIT":
        this.appendLog("ANTIGRAVITY", `🚀 ${data.message}`);
        break;

      case "STREAM_START":
        this.appendLog("ANTIGRAVITY", `⚡ Token generation started for ${data.file_path || "main.py"}`);
        if (this.stageStatusText) {
          this.stageStatusText.textContent = "TARA Streaming Live...";
        }
        if (this.activeFilenamePill) {
          this.activeFilenamePill.textContent = data.file_path || "main.py";
        }
        this.activeFile = data.file_path || "main.py";

        // Ensure Editor tab is active so the user sees live character typing
        const editorTab = document.getElementById("tab-editor-view");
        if (editorTab && !editorTab.classList.contains("active")) {
          editorTab.click();
        }

        // Prepare editor buffer for clean incoming stream
        if (this.editor) {
          this.editor.setValue("");
        }
        break;

      case "CODE_DELTA":
        if (this.editor && window.monaco && data.delta) {
          const model = this.editor.getModel();
          if (model) {
            const lineCount = model.getLineCount();
            const maxCol = model.getLineMaxColumn(lineCount);
            const range = new monaco.Range(lineCount, maxCol, lineCount, maxCol);

            // Apply live character edits directly into the buffer
            this.editor.executeEdits("tara-stream", [{
              range: range,
              text: data.delta,
              forceMoveMarkers: true,
            }]);

            // Auto-scroll the Monaco viewport to track TARA's live cursor
            this.editor.revealLine(model.getLineCount());
          }
        }
        break;

      case "STREAM_END":
        this.appendLog("ANTIGRAVITY", `✅ Token streaming completed for ${data.file_path || "main.py"}`);
        if (this.stageStatusText) {
          this.stageStatusText.textContent = "Live Stream Finished";
        }
        // Cache code to current session state
        if (this.editor && this.activeFile && this.currentSession) {
          const val = this.editor.getValue();
          if (!this.currentSession.dev_code_files) this.currentSession.dev_code_files = {};
          this.currentSession.dev_code_files[this.activeFile] = val;
        }
        break;

      case "ERROR":
        this.appendLog("ANTIGRAVITY", `❌ Stream error: ${data.message}`);
        if (this.stageStatusText) {
          this.stageStatusText.textContent = "Stream Error";
        }
        break;
    }
  }

  sendTaraStreamPrompt(prompt, targetFile = null, workspace = null) {
    if (!prompt) return;

    this.appendCopilotUserMessage(prompt);
    this.activeBotMsgBody = this.createCopilotBotMessage();

    if (!this.streamSocket || this.streamSocket.readyState !== WebSocket.OPEN) {
      this.appendLog("ANTIGRAVITY", "⚠️ Stream WebSocket reconnecting...");
      this.initTaraStreamWebSocket();
      setTimeout(() => this.sendTaraStreamPrompt(prompt, targetFile, workspace), 1000);
      return;
    }

    this.streamSocket.send(JSON.stringify({
      prompt: prompt,
      file_path: targetFile || this.activeFile || "main.py",
      workspace: workspace || null,
    }));
    this.appendLog("ANTIGRAVITY", `📡 Live stream prompt dispatched: "${prompt}"`);
  }

  sendTaraPrompt(prompt, targetFile = null, workspace = null) {
    if (!prompt) return;

    // Append user message to Copilot stream
    this.appendCopilotUserMessage(prompt);

    // Create bot response container
    this.activeBotMsgBody = this.createCopilotBotMessage();

    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.appendLog("ANTIGRAVITY", "⚠️ WebSocket reconnecting...");
      this.initTaraWebSocket();
      setTimeout(() => this.sendTaraPrompt(prompt, targetFile, workspace), 1000);
      return;
    }

    this.socket.send(JSON.stringify({
      prompt,
      target_file: targetFile || this.activeFile,
      workspace: workspace || null
    }));
    this.appendLog("ANTIGRAVITY", `🚀 Prompt dispatched: "${prompt}"`);
  }

  initSecurityWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host || "127.0.0.1:8000";
    const wsUrl = `${protocol}//${host}/ws/security`;

    try {
      this.securitySocket = new WebSocket(wsUrl);

      this.securitySocket.onopen = () => {
        this.appendLog("SECURITY", "Connected to Security Agent & Strix WebSocket stream (/ws/security)");
      };

      this.securitySocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleSecuritySocketMessage(data);
        } catch (e) {
          console.error("Failed to parse security WebSocket message:", e);
        }
      };

      this.securitySocket.onerror = (err) => {
        console.warn("Security WebSocket notice:", err);
      };

      this.securitySocket.onclose = () => {
        setTimeout(() => {
          if (!this.securitySocket || this.securitySocket.readyState === WebSocket.CLOSED) {
            this.initSecurityWebSocket();
          }
        }, 5000);
      };
    } catch (e) {
      console.warn("Could not establish WebSocket to /ws/security:", e);
    }
  }

  handleSecuritySocketMessage(data) {
    if (!data || !data.type) return;

    switch (data.type) {
      case "init":
        this.appendLog("SECURITY", `Stream initialized with tools: ${(data.tools || []).join(", ")}`);
        break;

      case "e2b_status":
        this.appendLog(data.tool || "SECURITY", data.message);
        if (this.stageStatusText) {
          this.stageStatusText.textContent = data.message;
        }
        break;

      case "status":
        this.appendLog("SECURITY", data.message);
        if (this.stageStatusText) {
          this.stageStatusText.textContent = data.message;
        }
        break;

      case "scan_complete":
        this.appendLog("SECURITY", `Security scan finished. Total findings: ${data.total_findings} (Tier: ${data.tier})`);
        break;

      case "diff_stream_start":
        this.appendLog("SECURITY", `📝 Streaming patched diff for ${data.filename} (+${data.additions}, -${data.deletions})`);
        break;

      case "diff_line":
        this.appendLog("SECURITY", `  ${data.line}`);
        break;

      case "file_diff":
        if (data.diff && this.diffEditorPrimary && window.monaco) {
          const diff = data.diff;
          const lang = diff.filename && diff.filename.endsWith(".py") ? "python" : "plaintext";
          this.latestPatchedDiff = diff;

          // Render inline or side-by-side diff in Monaco createDiffEditor
          this.diffEditorPrimary.setModel({
            original: monaco.editor.createModel(diff.original || "", lang),
            modified: monaco.editor.createModel(diff.modified || "", lang),
          });
          this.diffEditorPrimary.updateOptions({ renderSideBySide: this.diffRenderSideBySide });
          this.appendLog("SECURITY", `✅ Monaco DiffEditor updated with secure patched code for ${diff.filename}`);
          this.layoutDiffEditors();

          // Automatically switch to Diff View
          const tabDiff = document.getElementById("tab-diff-view");
          if (tabDiff) tabDiff.click();

          // Show Accept Patch button
          if (this.btnAcceptPatch) {
            this.btnAcceptPatch.style.display = "inline-flex";
            this.btnAcceptPatch.disabled = false;
            this.btnAcceptPatch.innerHTML = `<span>✓ Accept Patch (${diff.filename})</span>`;
          }

          // Cache patch into current session
          if (!this.currentSession) this.currentSession = {};
          if (!this.currentSession.security_patches) this.currentSession.security_patches = {};
          this.currentSession.security_patches[diff.filename] = diff.modified;
        }
        break;

      case "complete":
        this.appendLog("SECURITY", `🎉 Security pipeline finished. Patches and diffs ready for review.`);
        if (this.stageStatusText) this.stageStatusText.textContent = "Security Hardening Complete";
        if (this.btnRunStrixScan) {
          this.btnRunStrixScan.disabled = false;
          this.btnRunStrixScan.innerHTML = `<span class="btn-icon">🛡️</span><span>Strix Scan</span>`;
        }
        if (data.data) {
          if (data.data.patched_files && this.currentSession) {
            this.currentSession.security_patches = data.data.patched_files;
          }
          if (data.data.findings) {
            this.renderAuditReport(
              {
                timeline: [
                  { phase: "Flake8 Linter", status: "Completed" },
                  { phase: "Bandit AST SAST", status: "Completed" },
                  { phase: "Strix Autonomous Penetration Testing", status: "Completed" },
                  { phase: "ChatGoogleGenerativeAI Hardening", status: "Patches Applied" }
                ],
                key_decisions: [
                  "Executed triple-layer dynamic security scan (Flake8 + Bandit + Strix).",
                  "Synthesized hardened code patches using ChatGoogleGenerativeAI.",
                  "Generated inline side-by-side Monaco diffs."
                ],
                unresolved_risks: ["Maintain active E2B sandbox verification in CI/CD pipeline."]
              },
              data.data.findings
            );
          }
        }
        break;

      case "error":
        this.appendLog("SECURITY", `❌ Security scan error: ${data.error}`);
        if (this.btnRunStrixScan) {
          this.btnRunStrixScan.disabled = false;
          this.btnRunStrixScan.innerHTML = `<span class="btn-icon">🛡️</span><span>Strix Scan</span>`;
        }
        break;
    }
  }

  runStrixScan() {
    if (this.btnRunStrixScan) {
      this.btnRunStrixScan.disabled = true;
      this.btnRunStrixScan.innerHTML = `<span class="btn-icon">⏳</span><span>Scanning (Strix/Bandit)...</span>`;
    }

    // Switch to Security log tab and open drawer
    this.consoleDrawer.classList.remove("collapsed");
    document.querySelectorAll(".console-tab").forEach((t) => t.classList.remove("active"));
    const secTab = Array.from(document.querySelectorAll(".console-tab")).find((t) => t.dataset.agent === "Security");
    if (secTab) {
      secTab.classList.add("active");
      this.activeAgentFilter = "Security";
      this.renderLogs();
    }

    this.appendLog("SECURITY", "🚀 Triggering triple-layer security scan (Flake8 + Bandit + Strix)...");

    // Gather active files to scan
    const filesToScan = {};
    if (this.currentSession && this.currentSession.qa_refactored_files) {
      Object.assign(filesToScan, this.currentSession.qa_refactored_files);
    } else if (this.currentSession && this.currentSession.dev_code_files) {
      Object.assign(filesToScan, this.currentSession.dev_code_files);
    }
    if (this.editor && this.activeFile) {
      filesToScan[this.activeFile] = this.editor.getValue();
    }

    // Attempt streaming over WebSocket first
    if (this.securitySocket && this.securitySocket.readyState === WebSocket.OPEN) {
      this.securitySocket.send(JSON.stringify({
        action: "scan",
        files: filesToScan,
        session_id: this.sessionId,
      }));
    } else {
      // Reconnect and send or fallback to REST endpoint
      fetch("/api/security/strix-scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          files: filesToScan,
          session_id: this.sessionId,
        }),
      })
        .then((res) => res.json())
        .then((data) => {
          this.appendLog("SECURITY", `Scan complete via API. Found ${data.findings_count} findings.`);
          if (data.patched_files && Object.keys(data.patched_files).length) {
            const firstFile = Object.keys(data.patched_files)[0];
            const orig = filesToScan[firstFile] || "";
            const patched = data.patched_files[firstFile];
            if (this.diffEditorPrimary && window.monaco) {
              this.diffEditorPrimary.setModel({
                original: monaco.editor.createModel(orig, "python"),
                modified: monaco.editor.createModel(patched, "python"),
              });
              document.getElementById("tab-diff-view").click();
            }
          }
        })
        .catch((err) => {
          this.appendLog("SECURITY", `API fallback error: ${err.message}`);
        })
        .finally(() => {
          if (this.btnRunStrixScan) {
            this.btnRunStrixScan.disabled = false;
            this.btnRunStrixScan.innerHTML = `<span class="btn-icon">🛡️</span><span>Strix Scan</span>`;
          }
        });
    }
  }

  async applySecurityPatch() {
    if (!this.latestPatchedDiff) {
      alert("No active security patch to apply.");
      return;
    }

    const { filename, modified } = this.latestPatchedDiff;
    if (!filename || !modified) return;

    if (this.btnAcceptPatch) {
      this.btnAcceptPatch.disabled = true;
      this.btnAcceptPatch.innerHTML = `<span>⏳ Applying Patch...</span>`;
    }

    try {
      const res = await fetch("/api/security/apply-patch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_path: filename,
          patched_code: modified,
          session_id: this.sessionId,
        }),
      });

      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      this.appendLog("SECURITY", `✅ Applied security patch to workspace: ${filename}`);

      // Update active editor if viewing the same file
      if (this.activeFile === filename && this.editor) {
        this.editor.setValue(modified);
      }

      if (this.btnAcceptPatch) {
        this.btnAcceptPatch.innerHTML = `<span>✓ Patch Applied to Workspace</span>`;
        setTimeout(() => {
          if (this.btnAcceptPatch) this.btnAcceptPatch.style.display = "none";
        }, 3000);
      }
    } catch (err) {
      alert("Error applying patch: " + err.message);
      this.appendLog("SECURITY", `❌ Patch application error: ${err.message}`);
      if (this.btnAcceptPatch) {
        this.btnAcceptPatch.disabled = false;
        this.btnAcceptPatch.innerHTML = `<span>✓ Accept Patch (${filename})</span>`;
      }
    }
  }

  appendCopilotUserMessage(text) {
    const msg = document.createElement("div");
    msg.className = "copilot-msg user";
    msg.innerHTML = `
      <div class="msg-avatar">👤</div>
      <div class="msg-body">${this.escapeHtml(text)}</div>
    `;
    this.copilotChatStream.appendChild(msg);
    this.scrollCopilotToBottom();
  }

  createCopilotBotMessage() {
    const msg = document.createElement("div");
    msg.className = "copilot-msg bot";
    const body = document.createElement("div");
    body.className = "msg-body";
    body.innerHTML = `<span style="font-size:0.75rem; color:var(--text-muted); font-style:italic;">Processing request...</span>`;

    msg.innerHTML = `<div class="msg-avatar">⚡</div>`;
    msg.appendChild(body);
    this.copilotChatStream.appendChild(msg);
    this.scrollCopilotToBottom();
    return body;
  }

  scrollCopilotToBottom() {
    if (this.copilotChatStream) {
      this.copilotChatStream.scrollTop = this.copilotChatStream.scrollHeight;
    }
  }

  escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  bindEvents() {
    // 1. Activity Dock item switching
    this.dockBtnSpec.addEventListener("click", () => {
      this.setDockActive(this.dockBtnSpec);
      this.ensureSidebarOpen();
      document.getElementById("tab-btn-spec").click();
    });

    this.dockBtnFiles.addEventListener("click", () => {
      this.setDockActive(this.dockBtnFiles);
      this.ensureSidebarOpen();
      document.getElementById("tab-btn-files").click();
    });

    this.dockBtnEditor.addEventListener("click", () => {
      this.setDockActive(this.dockBtnEditor);
      document.getElementById("tab-editor-view").click();
    });

    this.dockBtnDiff.addEventListener("click", () => {
      this.setDockActive(this.dockBtnDiff);
      document.getElementById("tab-diff-view").click();
    });

    this.dockBtnAudit.addEventListener("click", () => {
      this.setDockActive(this.dockBtnAudit);
      document.getElementById("tab-audit-view").click();
    });

    this.dockBtnTerminal.addEventListener("click", () => {
      this.setDockActive(this.dockBtnTerminal);
      this.consoleDrawer.classList.remove("collapsed");
      const termTab = document.getElementById("tab-terminal");
      if (termTab) termTab.click();
    });

    // Copilot Toggle
    this.dockBtnCopilotToggle.addEventListener("click", () => {
      this.copilotPanel.classList.toggle("collapsed");
      if (!this.copilotPanel.classList.contains("collapsed")) {
        this.dockBtnCopilotToggle.classList.add("active-accent");
        if (this.editor) this.editor.layout();
      } else {
        this.dockBtnCopilotToggle.classList.remove("active-accent");
        if (this.editor) this.editor.layout();
      }
    });

    if (this.btnCloseCopilot) {
      this.btnCloseCopilot.addEventListener("click", () => {
        this.copilotPanel.classList.add("collapsed");
        this.dockBtnCopilotToggle.classList.remove("active-accent");
        if (this.editor) this.editor.layout();
      });
    }

    if (this.btnClearCopilot) {
      this.btnClearCopilot.addEventListener("click", () => {
        this.copilotChatStream.innerHTML = `
          <div class="copilot-msg bot">
            <div class="msg-avatar">⚡</div>
            <div class="msg-body">
              <p>Chat cleared. Ready for your next instruction!</p>
            </div>
          </div>
        `;
      });
    }

    // Toggle Console Drawer
    if (this.btnToggleConsole) {
      this.btnToggleConsole.addEventListener("click", () => {
        this.consoleDrawer.classList.toggle("collapsed");
        this.btnToggleConsole.textContent = this.consoleDrawer.classList.contains("collapsed") ? "□" : "⎯";
        if (this.editor) this.editor.layout();
      });
    }

    // Quick Prompt Chips
    this.copilotChips.forEach((chip) => {
      chip.addEventListener("click", () => {
        const prompt = chip.dataset.prompt;
        if (prompt) {
          this.copilotPromptInput.value = prompt;
          this.sendCurrentCopilotPrompt();
        }
      });
    });

    // Persona Chips
    this.personaChips.forEach((pChip) => {
      pChip.addEventListener("click", () => {
        this.personaChips.forEach((c) => c.classList.remove("active"));
        pChip.classList.add("active");
        this.activePersona = pChip.dataset.persona;
        this.appendLog("SYSTEM", `Active Copilot Persona set to: ${pChip.textContent.trim()}`);
      });
    });

    // Copilot Send Button & Enter key
    this.btnSendCopilot.addEventListener("click", () => this.sendCurrentCopilotPrompt());
    this.copilotPromptInput.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" && !e.shiftKey) || (e.key === "Enter" && (e.ctrlKey || e.metaKey))) {
        e.preventDefault();
        this.sendCurrentCopilotPrompt();
      }
    });

    // Character Counter on PRD Textarea
    this.prdTextarea.addEventListener("input", () => {
      const len = this.prdTextarea.value.length;
      if (this.prdCharCounter) {
        this.prdCharCounter.textContent = `${len.toLocaleString()} chars`;
      }
    });

    // Preset dropdown
    this.presetSelect.addEventListener("change", (e) => this.applyPreset(e.target.value));

    // Drag & drop file upload
    this.dropZone.addEventListener("click", () => this.fileUploadInput.click());
    this.fileUploadInput.addEventListener("change", (e) => this.handleFileSelect(e.target.files[0]));
    this.dropZone.addEventListener("dragover", (e) => { e.preventDefault(); this.dropZone.style.borderColor = "var(--accent-purple)"; });
    this.dropZone.addEventListener("dragleave", () => { this.dropZone.style.borderColor = ""; });
    this.dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      this.dropZone.style.borderColor = "";
      if (e.dataTransfer.files.length) this.handleFileSelect(e.dataTransfer.files[0]);
    });

    // Start pipeline
    this.btnStartPipeline.addEventListener("click", () => this.startPipeline());

    // Sidebar tab switching
    document.querySelectorAll(".sidebar-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".sidebar-tab").forEach((t) => t.classList.remove("active"));
        document.querySelectorAll(".sidebar-content").forEach((c) => c.classList.remove("active"));
        tab.classList.add("active");
        document.getElementById(tab.dataset.panel).classList.add("active");
      });
    });

    // Stage tab switching (Editor, Diff, Audit)
    document.querySelectorAll(".stage-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".stage-tab").forEach((t) => t.classList.remove("active"));
        document.querySelectorAll(".stage-content").forEach((c) => c.classList.remove("active"));
        tab.classList.add("active");
        document.getElementById(tab.dataset.view).classList.add("active");
        if (tab.dataset.view === "editor-view" && this.editor) {
          this.editor.layout();
        } else if (tab.dataset.view === "diff-view") {
          setTimeout(() => this.layoutDiffEditors(), 50);
        }
      });
    });

    // Console agent filter tabs
    document.querySelectorAll(".console-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".console-tab").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        this.activeAgentFilter = tab.dataset.agent;
        this.renderLogs();
      });
    });

    // Clear console
    document.getElementById("btn-clear-console").addEventListener("click", () => {
      this.allLogs = [];
      this.renderLogs();
    });

    // Download ZIP
    this.btnDownloadZip.addEventListener("click", () => {
      if (this.sessionId) {
        window.location.href = `/api/sessions/${this.sessionId}/download`;
      }
    });

    // Run Code in Sandbox
    if (this.btnRunCode) {
      this.btnRunCode.addEventListener("click", () => this.runSandboxedCode());
    }

    // Run Strix Autonomous Security Penetration Test
    if (this.btnRunStrixScan) {
      this.btnRunStrixScan.addEventListener("click", () => this.runStrixScan());
    }

    // Accept and Apply Security Patch to Workspace
    if (this.btnAcceptPatch) {
      this.btnAcceptPatch.addEventListener("click", () => this.applySecurityPatch());
    }

    // Diff stage selection
    this.diffStageButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        this.diffStageButtons.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        this.activeDiffStage = btn.dataset.stage;
        if (this.diffFileSelector && this.diffFileSelector.value) {
          this.renderDiff(this.diffFileSelector.value);
        }
      });
    });

    // Toggle Side-by-Side / Inline Diff
    if (this.btnToggleDiffInline) {
      this.btnToggleDiffInline.addEventListener("click", () => {
        this.diffRenderSideBySide = !this.diffRenderSideBySide;
        this.btnToggleDiffInline.classList.toggle("active", !this.diffRenderSideBySide);
        this.btnToggleDiffInline.querySelector("span").textContent = this.diffRenderSideBySide ? "Toggle Inline Diff" : "Toggle Split Diff";
        if (this.diffEditorPrimary) {
          this.diffEditorPrimary.updateOptions({ renderSideBySide: this.diffRenderSideBySide });
        }
        if (this.diffEditorSecondary) {
          this.diffEditorSecondary.updateOptions({ renderSideBySide: this.diffRenderSideBySide });
        }
      });
    }

    // Diff file selector change
    if (this.diffFileSelector) {
      this.diffFileSelector.addEventListener("change", (e) => this.renderDiff(e.target.value));
    }

    // Approval gate actions
    this.btnGateApprove.addEventListener("click", () => {
      const notes = this.feedbackNotesInput.value.trim();
      this.submitDecision("approve", notes);
    });
    this.btnGateRequestChanges.addEventListener("click", () => {
      const notes = this.feedbackNotesInput.value.trim();
      if (!notes) {
        alert("Please provide feedback notes explaining what changes are requested.");
        this.feedbackNotesInput.focus();
        return;
      }
      this.submitDecision("request_changes", notes);
    });
    this.btnGateReject.addEventListener("click", () => {
      if (confirm("Are you sure you want to reject this spec? The pipeline will terminate with no code generated.")) {
        this.submitDecision("reject");
      }
    });
  }

  sendCurrentCopilotPrompt() {
    const prompt = this.copilotPromptInput.value.trim();
    if (!prompt) return;
    this.copilotPromptInput.value = "";
    if (this.activePersona === "live-stream" || prompt.startsWith("/stream") || prompt.startsWith("/live")) {
      const cleanPrompt = prompt.replace(/^\/(stream|live)\s*/i, "");
      this.sendTaraStreamPrompt(cleanPrompt || prompt, this.activeFile);
    } else {
      this.sendTaraPrompt(prompt, this.activeFile);
    }
  }

  setDockActive(dockBtn) {
    document.querySelectorAll(".dock-item").forEach((btn) => {
      if (btn.id !== "dock-btn-copilot-toggle") {
        btn.classList.remove("active");
      }
    });
    dockBtn.classList.add("active");
  }

  ensureSidebarOpen() {
    if (this.primarySidebar.classList.contains("collapsed")) {
      this.primarySidebar.classList.remove("collapsed");
      if (this.editor) this.editor.layout();
    }
  }

  applyPreset(presetKey) {
    if (PRESETS[presetKey]) {
      this.prdTextarea.value = PRESETS[presetKey];
      if (this.prdCharCounter) {
        this.prdCharCounter.textContent = `${this.prdTextarea.value.length.toLocaleString()} chars`;
      }
    }
  }

  async handleFileSelect(file) {
    if (!file) return;

    const isPdf = file.name.toLowerCase().endsWith(".pdf");
    const dropZoneHint = this.dropZone.querySelector(".upload-hint");
    const originalHint = dropZoneHint ? dropZoneHint.innerHTML : "";

    if (dropZoneHint) {
      dropZoneHint.innerHTML = `<span style="color: var(--accent-cyan);">⏳ Parsing ${file.name}...</span>`;
    }

    try {
      if (isPdf) {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch("/api/sessions/upload", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(errData.detail || "Failed to parse PDF document.");
        }

        const data = await res.json();
        this.prdTextarea.value = data.extracted_text;
        if (this.prdCharCounter) this.prdCharCounter.textContent = `${data.extracted_text.length.toLocaleString()} chars`;
        this.appendLog("SYSTEM", `📄 Extracted ${data.page_count} page(s) from PDF "${data.filename}" (${data.char_count.toLocaleString()} characters)`);
      } else {
        const reader = new FileReader();
        reader.onload = (e) => {
          this.prdTextarea.value = e.target.result;
          if (this.prdCharCounter) this.prdCharCounter.textContent = `${e.target.result.length.toLocaleString()} chars`;
          this.appendLog("SYSTEM", `📄 Loaded document: ${file.name} (${file.size.toLocaleString()} bytes)`);
        };
        reader.readAsText(file);
      }
    } catch (err) {
      console.error("Upload error:", err);
      alert(`Error loading file: ${err.message}`);
      this.appendLog("SYSTEM", `❌ Failed to parse ${file.name}: ${err.message}`);
    } finally {
      if (dropZoneHint) {
        dropZoneHint.innerHTML = originalHint;
      }
    }
  }

  updateSessionBadge() {
    this.sessionBadgeText.textContent = `Session: ${this.sessionId}`;
  }

  appendLog(agent, message, timestamp = null) {
    const ts = timestamp || new Date().toLocaleTimeString();
    this.allLogs.push({ agent, message, timestamp: ts });
    this.renderLogs();
  }

  renderLogs() {
    this.consoleLogStream.innerHTML = "";
    const filtered = this.activeAgentFilter === "all"
      ? this.allLogs
      : this.allLogs.filter((l) => l.agent.toUpperCase() === this.activeAgentFilter.toUpperCase());

    filtered.forEach((log) => {
      const line = document.createElement("div");
      let cls = "info";
      const ag = log.agent.toUpperCase();
      if (ag === "CEO") cls = "hitl";
      else if (ag === "DEVELOPER") cls = "info";
      else if (ag === "QA") cls = "warn";
      else if (ag === "SECURITY") cls = "error";
      else if (ag === "ANTIGRAVITY") cls = "antigravity";
      else if (ag === "TERMINAL") cls = "terminal";

      line.className = `log-line ${cls}`;
      line.innerHTML = `
        <span class="timestamp">[${log.timestamp}] [${log.agent.toUpperCase()}]</span>
        <span class="log-msg">${this.escapeHtml(log.message)}</span>
      `;
      this.consoleLogStream.appendChild(line);
    });

    this.consoleLogStream.scrollTop = this.consoleLogStream.scrollHeight;
  }

  setStepperStep(step) {
    const steps = ["spec", "ceo", "gate", "build", "security", "package"];
    const targetIdx = steps.indexOf(step);

    document.querySelectorAll(".step-item").forEach((el, idx) => {
      el.classList.remove("active", "completed");
      if (idx < targetIdx) {
        el.classList.add("completed");
      } else if (idx === targetIdx) {
        el.classList.add("active");
      }
    });
  }

  async startPipeline() {
    const prdText = this.prdTextarea.value.trim();
    if (!prdText) {
      alert("Please paste or upload PRD specification text first.");
      return;
    }

    this.btnStartPipeline.disabled = true;
    this.btnStartPipeline.innerHTML = `<span class="btn-icon">⏳</span><span>Consultancy Pipeline Running...</span>`;
    this.setStepperStep("ceo");
    this.stageStatusText.textContent = "CEO Evaluating PRD Viability...";

    try {
      const payload = {
        session_id: this.sessionId,
        prd_text: prdText,
        prd_filename: "architecture_spec.md"
      };

      const res = await fetch("/api/sessions/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.text();
        throw new Error(err);
      }

      const snapshot = await res.json();
      this.handleSessionUpdate(snapshot);
    } catch (err) {
      alert("Pipeline error: " + err.message);
      this.appendLog("SYSTEM", `Pipeline initialization error: ${err.message}`);
      this.btnStartPipeline.disabled = false;
      this.btnStartPipeline.innerHTML = `<span class="btn-icon">⚡</span><span>Launch Multi-Agent Pipeline</span>`;
    }
  }

  handleSessionUpdate(snapshot) {
    this.currentSession = snapshot;

    // Sync logs
    if (snapshot.logs) {
      this.allLogs = [];
      snapshot.logs.forEach((l) => this.appendLog(l.agent, l.message, l.timestamp));
    }

    // HITL Gate check
    if (snapshot.status === "awaiting_approval" && snapshot.ceo_critique) {
      this.setStepperStep("gate");
      this.stageStatusText.textContent = "Awaiting Human-in-the-Loop Sign-off";
      this.openApprovalModal(snapshot.ceo_critique, snapshot.revision_count);
    } else if (snapshot.status === "completed") {
      this.closeApprovalModal();
      this.setStepperStep("package");
      this.stageStatusText.textContent = "Pipeline Completed & Packaged";
      this.btnDownloadZip.disabled = false;
      if (this.btnRunCode) this.btnRunCode.disabled = false;
      this.btnStartPipeline.disabled = false;
      this.btnStartPipeline.innerHTML = `<span class="btn-icon">⚡</span><span>Run New Iteration</span>`;
      this.renderArtifacts(snapshot, true);
    } else if (snapshot.user_action === "reject") {
      this.closeApprovalModal();
      this.stageStatusText.textContent = "Workflow Rejected by Stakeholder";
      this.appendLog("HITL", "Pipeline halted per human decision.");
      this.btnStartPipeline.disabled = false;
      this.btnStartPipeline.innerHTML = `<span class="btn-icon">⚡</span><span>Restart Pipeline</span>`;
    }
  }

  openApprovalModal(critique, revisionCount = 0) {
    const verdict = (critique.verdict || "VIABLE").toUpperCase();
    this.modalVerdictText.textContent = verdict;
    this.modalMarketText.textContent = critique.market_viability || "Sound product market fit.";
    this.modalRecommendationText.textContent = critique.recommendation || "Recommended to proceed.";
    this.modalRevisionPill.textContent = `Revision Round #${revisionCount}`;
    this.feedbackNotesInput.value = "";

    this.btnGateApprove.disabled = false;
    this.btnGateRequestChanges.disabled = false;
    this.btnGateReject.disabled = false;

    const hasFlaws = (critique.structural_flaws && critique.structural_flaws.length > 0) || (critique.feature_gaps && critique.feature_gaps.length > 0);
    if (verdict === "NEEDS_REVISION" || verdict === "REJECTED" || hasFlaws) {
      this.btnGateApprove.innerHTML = `<span>Approve & Build Code Anyway ➔</span>`;
    } else {
      this.btnGateApprove.innerHTML = `<span>Approve & Proceed to Build ➔</span>`;
    }

    // Gaps & Flaws
    this.modalGapsList.innerHTML = "";
    (critique.feature_gaps || []).forEach((gap) => {
      const li = document.createElement("li");
      li.textContent = gap;
      this.modalGapsList.appendChild(li);
    });

    this.modalFlawsList.innerHTML = "";
    (critique.structural_flaws || []).forEach((flaw) => {
      const li = document.createElement("li");
      li.textContent = flaw;
      this.modalFlawsList.appendChild(li);
    });

    this.approvalModal.classList.add("active");
  }

  closeApprovalModal() {
    this.approvalModal.classList.remove("active");
  }

  async submitDecision(action, notes = "") {
    this.closeApprovalModal();
    this.btnGateApprove.disabled = true;
    this.btnGateRequestChanges.disabled = true;
    this.btnGateReject.disabled = true;

    if (action === "approve") {
      this.setStepperStep("build");
      this.stageStatusText.textContent = "Approved! Generating full Python code for your PRD...";
      this.appendLog("HITL", `Human Approved: Proceeding to build code for PRD` + (notes ? ` with directives: "${notes}"` : ""));
      this.btnStartPipeline.disabled = true;
      this.btnStartPipeline.innerHTML = `<span class="btn-icon">⚙️</span><span>Agents Building Code...</span>`;
    } else if (action === "request_changes") {
      this.setStepperStep("ceo");
      this.stageStatusText.textContent = "Re-evaluating PRD with your feedback notes...";
      this.appendLog("HITL", `Requested revision loop with notes: ${notes}`);
      this.btnStartPipeline.disabled = true;
      this.btnStartPipeline.innerHTML = `<span class="btn-icon">🔄</span><span>Revising Spec...</span>`;
    } else {
      this.stageStatusText.textContent = "Workflow Rejected by Stakeholder";
      this.appendLog("HITL", "Pipeline halted per human decision.");
      this.btnStartPipeline.disabled = false;
      this.btnStartPipeline.innerHTML = `<span class="btn-icon">⚡</span><span>Restart Pipeline</span>`;
    }

    try {
      const res = await fetch(`/api/sessions/${this.sessionId}/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, notes })
      });

      if (!res.ok) throw new Error(await res.text());
      const updatedSnapshot = await res.json();
      this.handleSessionUpdate(updatedSnapshot);
    } catch (err) {
      alert("Failed to submit decision: " + err.message);
      this.appendLog("SYSTEM", `Decision submission error: ${err.message}`);
      this.btnStartPipeline.disabled = false;
      this.btnStartPipeline.innerHTML = `<span class="btn-icon">⚡</span><span>Launch Multi-Agent Pipeline</span>`;
    }
  }

  async runSandboxedCode() {
    if (!this.sessionId || !this.currentSession) return;

    this.btnRunCode.disabled = true;
    this.btnRunCode.innerHTML = `<span class="btn-icon">⏳</span><span>Executing...</span>`;

    // Switch to Terminal tab and open drawer
    this.consoleDrawer.classList.remove("collapsed");
    const terminalTab = document.getElementById("tab-terminal");
    if (terminalTab) terminalTab.click();

    const targetFile = this.activeFile || "main.py";
    this.appendLog("TERMINAL", `🚀 [Sandbox Execution] Running python ${targetFile} in isolated sandbox...`);

    try {
      const res = await fetch(`/api/sessions/${this.sessionId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entrypoint: targetFile })
      });

      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      const statusBadge = data.exit_code === 0 ? "SUCCESS (Code 0)" : `EXIT CODE (${data.exit_code})`;
      this.appendLog("TERMINAL", `[${data.sandbox_tier}] Process completed in ${data.duration_ms}ms with status: ${statusBadge}`);

      if (data.stdout) {
        this.appendLog("TERMINAL", `=== STDOUT ===\n${data.stdout.trim()}`);
      }
      if (data.stderr) {
        this.appendLog("TERMINAL", `=== STDERR ===\n${data.stderr.trim()}`);
      }
    } catch (err) {
      this.appendLog("TERMINAL", `❌ Sandbox execution error: ${err.message}`);
    } finally {
      this.btnRunCode.disabled = false;
      this.btnRunCode.innerHTML = `<span class="btn-icon">▶️</span><span>Run in Sandbox</span>`;
    }
  }

  layoutDiffEditors() {
    if (this.diffEditorPrimary) this.diffEditorPrimary.layout();
    if (this.diffEditorSecondary && this.activeDiffStage === "dual") {
      this.diffEditorSecondary.layout();
    }
  }

  renderArtifacts(snapshot, forceFirst = false) {
    const finalFiles = snapshot.security_patches || snapshot.qa_refactored_files || snapshot.dev_code_files || {};
    const fileNames = Object.keys(finalFiles);

    // Update count badges
    if (this.filesCountBadge) this.filesCountBadge.textContent = fileNames.length;
    if (this.dockFilesCount) this.dockFilesCount.textContent = fileNames.length;
    if (this.filesTagTotal) this.filesTagTotal.textContent = `${fileNames.length} files`;

    // Populate file explorer
    this.fileTreeContainer.innerHTML = "";

    fileNames.forEach((fname, idx) => {
      const item = document.createElement("div");
      item.className = `file-tree-item ${fname === this.activeFile ? "active" : ""}`;
      item.innerHTML = `
        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        <span>${fname}</span>
      `;
      item.addEventListener("click", () => this.selectFile(fname, finalFiles[fname]));
      this.fileTreeContainer.appendChild(item);

      if ((forceFirst && idx === 0) || (!this.activeFile && idx === 0)) {
        this.selectFile(fname, finalFiles[fname]);
      } else if (fname === this.activeFile) {
        this.selectFile(fname, finalFiles[fname]);
      }
    });

    // Populate Diff Selector
    if (this.diffFileSelector) {
      const prevVal = this.diffFileSelector.value;
      this.diffFileSelector.innerHTML = "";
      fileNames.forEach((fname) => {
        const opt = document.createElement("option");
        opt.value = fname;
        opt.textContent = fname;
        this.diffFileSelector.appendChild(opt);
      });

      if (fileNames.includes(prevVal)) {
        this.diffFileSelector.value = prevVal;
        this.renderDiff(prevVal);
      } else if (fileNames.length) {
        this.diffFileSelector.value = fileNames[0];
        this.renderDiff(fileNames[0]);
      }
    }

    // Populate Audit Summary
    if (snapshot.audit_summary) {
      this.renderAuditReport(snapshot.audit_summary, snapshot.security_findings);
    }
  }

  selectFile(filename, content) {
    this.activeFile = filename;
    this.activeFilenamePill.textContent = filename;
    if (this.copilotTargetDisplay) {
      this.copilotTargetDisplay.textContent = filename;
    }

    document.querySelectorAll(".file-tree-item").forEach((el) => {
      el.classList.toggle("active", el.innerText.trim() === filename);
    });

    if (this.editor) {
      this.editor.setValue(content || "");
    } else {
      const fallback = document.getElementById("fallback-code-content");
      if (fallback) fallback.textContent = content || "";
    }
  }

  renderDiff(filename) {
    if (!this.currentSession || !filename) return;

    const devCode = (this.currentSession.dev_code_files && this.currentSession.dev_code_files[filename]) || "// No developer draft available";
    const qaCode = (this.currentSession.qa_refactored_files && this.currentSession.qa_refactored_files[filename]) || devCode;
    const secCode = (this.currentSession.security_patches && this.currentSession.security_patches[filename]) || qaCode;

    if (!window.monaco || !this.diffEditorPrimary) {
      return;
    }

    const stage = this.activeDiffStage || "dev-qa";
    const secContainer = document.getElementById("monaco-diff-secondary");
    const primContainer = document.getElementById("monaco-diff-primary");

    if (stage === "dual") {
      if (secContainer) {
        secContainer.style.display = "block";
        secContainer.style.width = "50%";
      }
      if (primContainer) {
        primContainer.style.width = "50%";
      }

      this.diffEditorPrimary.setModel({
        original: monaco.editor.createModel(devCode, "python"),
        modified: monaco.editor.createModel(qaCode, "python"),
      });

      if (this.diffEditorSecondary) {
        this.diffEditorSecondary.setModel({
          original: monaco.editor.createModel(qaCode, "python"),
          modified: monaco.editor.createModel(secCode, "python"),
        });
      }
    } else {
      if (secContainer) {
        secContainer.style.display = "none";
      }
      if (primContainer) {
        primContainer.style.width = "100%";
      }

      let originalCode = devCode;
      let modifiedCode = qaCode;

      if (stage === "qa-sec") {
        originalCode = qaCode;
        modifiedCode = secCode;
      } else if (stage === "dev-sec") {
        originalCode = devCode;
        modifiedCode = secCode;
      }

      this.diffEditorPrimary.setModel({
        original: monaco.editor.createModel(originalCode, "python"),
        modified: monaco.editor.createModel(modifiedCode, "python"),
      });
    }

    setTimeout(() => this.layoutDiffEditors(), 40);
  }

  renderAuditReport(audit, findings = []) {
    if (!audit) return;
    let html = `
      <div class="audit-card">
        <h2>Release Audit & Governance Summary</h2>
        <p><strong>Session ID:</strong> <code>${this.sessionId}</code></p>
        <p><strong>Hardening Status:</strong> Verified and release package prepared.</p>

        <h3>1. Pipeline Execution Timeline</h3>
        <ul>
          ${(audit.timeline || []).map((t) => `<li><strong>${t.phase}:</strong> ${t.status}</li>`).join("")}
        </ul>

        <h3>2. Architecture & Design Standards</h3>
        <ul>
          ${(audit.key_decisions || []).map((d) => `<li>${d}</li>`).join("")}
        </ul>

        <h3>3. SAST Vulnerability Findings & Remediations</h3>
        <ul>
          ${(findings || []).map((f) => `
            <li>
              <strong>[${(f.severity || "medium").toUpperCase()}]</strong> ${f.category} (${f.file}:${f.line || 1})
              <br><small style="color:#94a3b8;">${f.description} → <em>${f.patch_applied || "Remediated"}</em></small>
            </li>
          `).join("")}
        </ul>

        <h3>4. Residual Risk Assessment</h3>
        <ul>
          ${(audit.unresolved_risks || []).map((r) => `<li>${r}</li>`).join("")}
        </ul>
      </div>
    `;
    this.auditContentContainer.innerHTML = html;
  }
}

// Instantiate on load
window.addEventListener("DOMContentLoaded", () => {
  window.taraApp = new TaraIDE();
});
