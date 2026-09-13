/**
 * TARA Web IDE Client Application
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
    this.allLogs = [];
    this.socket = null;

    this.initElements();
    this.initMonaco();
    this.bindEvents();
    this.applyPreset("cache");
    this.updateSessionBadge();
  }

  initElements() {
    this.prdTextarea = document.getElementById("prd-input-textarea");
    this.presetSelect = document.getElementById("preset-select");
    this.btnStartPipeline = document.getElementById("btn-start-pipeline");
    this.btnDownloadZip = document.getElementById("btn-download-zip");
    this.fileTreeContainer = document.getElementById("file-tree-container");
    this.filesCountBadge = document.getElementById("files-count-badge");
    this.sessionBadgeText = document.getElementById("session-id-text");
    this.stageStatusText = document.getElementById("stage-status-text");
    this.activeFilenamePill = document.getElementById("active-filename-pill");
    this.consoleLogStream = document.getElementById("console-log-stream");
    this.dropZone = document.getElementById("drop-zone");
    this.fileUploadInput = document.getElementById("file-upload-input");

    // Modal elements
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

    // Diff elements
    this.diffFileSelector = document.getElementById("diff-file-selector");
    this.diffDevBox = document.getElementById("diff-dev-box");
    this.diffQaBox = document.getElementById("diff-qa-box");
    this.diffSecBox = document.getElementById("diff-sec-box");

    // Audit view
    this.auditContentContainer = document.getElementById("audit-content-container");
  }

  initMonaco() {
    const container = document.getElementById("monaco-editor-container");
    const fallback = document.getElementById("fallback-editor-container");

    if (window.require) {
      window.require.config({ paths: { vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs" } });
      window.require(["vs/editor/editor.main"], () => {
        this.editor = monaco.editor.create(container, {
          value: "# TARA Autonomous Code Engine\n# Awaiting PRD input to generate Python artifacts...",
          language: "python",
          theme: "vs-dark",
          fontSize: 13,
          fontFamily: "'JetBrains Mono', monospace",
          minimap: { enabled: false },
          automaticLayout: true,
          scrollBeyondLastLine: false,
          padding: { top: 12, bottom: 12 },
        });
      });
    } else {
      container.style.display = "none";
      fallback.style.display = "block";
    }
  }

  bindEvents() {
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

    // Diff file selector change
    this.diffFileSelector.addEventListener("change", (e) => this.renderDiff(e.target.value));

    // Approval gate actions
    this.btnGateApprove.addEventListener("click", () => this.submitDecision("approve"));
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

  applyPreset(presetKey) {
    if (PRESETS[presetKey]) {
      this.prdTextarea.value = PRESETS[presetKey];
    }
  }

  handleFileSelect(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      this.prdTextarea.value = e.target.result;
      this.appendLog("SYSTEM", `Loaded document: ${file.name} (${file.size} bytes)`);
    };
    reader.readAsText(file);
  }

  updateSessionBadge() {
    this.sessionBadgeText.textContent = `Session: ${this.sessionId}`;
  }

  setStepperStep(stepKey) {
    const steps = ["spec", "ceo", "gate", "build", "security", "package"];
    const targetIdx = steps.indexOf(stepKey);
    steps.forEach((key, idx) => {
      const el = document.querySelector(`.step-item[data-step="${key}"]`);
      if (!el) return;
      el.classList.remove("active", "completed");
      if (idx < targetIdx) el.classList.add("completed");
      else if (idx === targetIdx) el.classList.add("active");
    });
  }

  appendLog(agent, message, timestamp = null) {
    const time = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
    this.allLogs.push({ agent, message, timestamp: time });
    this.renderLogs();
  }

  renderLogs() {
    this.consoleLogStream.innerHTML = "";
    const filtered = this.activeAgentFilter === "all"
      ? this.allLogs
      : this.allLogs.filter((l) => l.agent.toLowerCase() === this.activeAgentFilter.toLowerCase());

    filtered.forEach((log) => {
      const div = document.createElement("div");
      div.className = `log-line ${log.agent}`;
      div.innerHTML = `
        <span class="timestamp">[${log.timestamp}]</span>
        <span class="badge-agent">[${log.agent}]</span>
        <span class="log-msg">${this.escapeHtml(log.message)}</span>
      `;
      this.consoleLogStream.appendChild(div);
    });
    this.consoleLogStream.scrollTop = this.consoleLogStream.scrollHeight;
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.innerText = text;
    return div.innerHTML;
  }

  async startPipeline() {
    const prdText = this.prdTextarea.value.trim();
    if (!prdText) {
      alert("Please provide PRD content before launching.");
      return;
    }

    this.btnStartPipeline.disabled = true;
    this.btnStartPipeline.innerHTML = `<span class="btn-icon">⏳</span><span>Analyzing PRD...</span>`;
    this.setStepperStep("ceo");
    this.stageStatusText.textContent = "CEO Evaluating PRD...";

    this.appendLog("SYSTEM", `Starting pipeline run for session: ${this.sessionId}`);

    try {
      const res = await fetch("/api/sessions/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: this.sessionId,
          prd_text: prdText,
          prd_filename: "PRD.md"
        })
      });

      if (!res.ok) throw new Error(await res.text());
      const snapshot = await res.json();
      this.handleSessionUpdate(snapshot);

      // Connect WebSocket for streaming updates
      this.initWebSocket();
    } catch (err) {
      this.appendLog("SYSTEM", `Error starting session: ${err.message}`);
      alert("Failed to start session: " + err.message);
      this.btnStartPipeline.disabled = false;
      this.btnStartPipeline.innerHTML = `<span class="btn-icon">⚡</span><span>Launch Consultancy Pipeline</span>`;
    }
  }

  initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/api/sessions/${this.sessionId}/stream`;
    this.socket = new WebSocket(wsUrl);

    this.socket.onopen = () => {
      this.appendLog("SYSTEM", "Live telemetry stream established.");
    };

    this.socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.data && payload.data.logs) {
          payload.data.logs.forEach((l) => this.appendLog(l.agent, l.message, l.timestamp));
        }
      } catch (e) {}
    };
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
      this.btnStartPipeline.disabled = false;
      this.btnStartPipeline.innerHTML = `<span class="btn-icon">⚡</span><span>Run New Iteration</span>`;
      this.renderArtifacts(snapshot);
    } else if (snapshot.user_action === "reject") {
      this.closeApprovalModal();
      this.stageStatusText.textContent = "Workflow Rejected by Stakeholder";
      this.appendLog("HITL", "Pipeline halted per human decision.");
      this.btnStartPipeline.disabled = false;
      this.btnStartPipeline.innerHTML = `<span class="btn-icon">⚡</span><span>Restart Pipeline</span>`;
    }
  }

  openApprovalModal(critique, revisionCount = 0) {
    this.modalVerdictText.textContent = (critique.verdict || "VIABLE").toUpperCase();
    this.modalMarketText.textContent = critique.market_viability || "Sound product market fit.";
    this.modalRecommendationText.textContent = critique.recommendation || "Recommended to proceed.";
    this.modalRevisionPill.textContent = `Revision Round #${revisionCount}`;
    this.feedbackNotesInput.value = "";

    // Gaps
    this.modalGapsList.innerHTML = "";
    (critique.feature_gaps || []).forEach((gap) => {
      const li = document.createElement("li");
      li.textContent = gap;
      this.modalGapsList.appendChild(li);
    });

    // Flaws
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
    this.appendLog("HITL", `Submitting decision: ${action.toUpperCase()}` + (notes ? ` (${notes})` : ""));
    this.stageStatusText.textContent = `Resuming: ${action.toUpperCase()}...`;

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
    }
  }

  renderArtifacts(snapshot) {
    const finalFiles = snapshot.security_patches || snapshot.qa_refactored_files || snapshot.dev_code_files || {};
    const fileNames = Object.keys(finalFiles);

    // Switch to file explorer tab
    const filesTab = document.querySelector('.sidebar-tab[data-panel="files-panel"]');
    if (filesTab) filesTab.click();

    // Populate file explorer
    this.fileTreeContainer.innerHTML = "";
    this.filesCountBadge.textContent = fileNames.length;

    fileNames.forEach((fname, idx) => {
      const item = document.createElement("div");
      item.className = `file-tree-item ${fname === this.activeFile ? "active" : ""}`;
      item.innerHTML = `
        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        <span>${fname}</span>
      `;
      item.addEventListener("click", () => this.selectFile(fname, finalFiles[fname]));
      this.fileTreeContainer.appendChild(item);

      if (idx === 0) this.selectFile(fname, finalFiles[fname]);
    });

    // Populate Diff Selector
    this.diffFileSelector.innerHTML = "";
    fileNames.forEach((fname) => {
      const opt = document.createElement("option");
      opt.value = fname;
      opt.textContent = fname;
      this.diffFileSelector.appendChild(opt);
    });
    if (fileNames.length) this.renderDiff(fileNames[0]);

    // Populate Audit Summary
    this.renderAuditReport(snapshot.audit_summary, snapshot.security_findings);
  }

  selectFile(filename, content) {
    this.activeFile = filename;
    this.activeFilenamePill.textContent = filename;

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
    if (!this.currentSession) return;
    const devCode = (this.currentSession.dev_code_files && this.currentSession.dev_code_files[filename]) || "// No original dev draft";
    const qaCode = (this.currentSession.qa_refactored_files && this.currentSession.qa_refactored_files[filename]) || "// No QA refactor";
    const secCode = (this.currentSession.security_patches && this.currentSession.security_patches[filename]) || "// No security patch";

    this.diffDevBox.querySelector("code").textContent = devCode;
    this.diffQaBox.querySelector("code").textContent = qaCode;
    this.diffSecBox.querySelector("code").textContent = secCode;
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
