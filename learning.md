# TARA Project Learning Guide

> **Welcome!** This document explains in simple, plain English what **TARA** is, what has been built so far, why each part exists, and how everything works together. This file will be continuously updated as new features are added.

---

## 1. What is TARA?

**TARA** stands for **Tech-Architecture & Automated Review Assistant**.

Think of TARA as an **autonomous software consultancy firm in a box**. Normally, when you want to build a software project, you need:
1. A **CEO / Product Evaluator** to review your product ideas and tell you if they make sense or have missing requirements.
2. A **Software Developer** to write real, modular code.
3. A **Quality Assurance (QA) Engineer** to inspect the code for bugs, errors, and bad practices.
4. A **Security Officer** to scan the code for security holes (like SQL injection or data leaks) and patch them.

TARA automates this entire team using **AI agents** powered by **Google Gemini** and orchestrates them using **LangGraph**.

---

## 2. The Big Picture: How It Works

Here is the journey of your project requirements document (PRD) from start to finish:

```
+-------------------------------------------------------------------+
|                        Your Product Idea (PRD)                    |
+-------------------------------------------------------------------+
                                  |
                                  v
                   [Step 1: CEO / VC Evaluator]
        Analyzes feasibility, feature gaps, and structural flaws.
                                  |
                                  v
                   [Step 2: Human Approval Gate]
            You decide: Approve, Request Changes, or Reject.
                                  |
                   (If approved, continue below)
                                  |
                                  v
                    [Step 3: Software Developer]
              Writes complete, multi-file Python code.
                                  |
                                  v
                     [Step 4: QA Quality Engineer]
          Inspects code for bugs, edge cases, and code smells.
                                  |
                                  v
                     [Step 5: Security Officer]
       Scans for OWASP security risks and creates security patches.
                                  |
                                  v
                     [Final Downloadable Package]
              A ready-to-run, hardened ZIP package!
```

---

## 3. What Has Been Built So Far (And Why)

### Step 1: Environment & Libraries
- **What was done:** Verified and installed `google-genai` (version 2.18.1) and `pydantic` (version 2.13.4).
- **Why:** 
  - `google-genai` is the official Google SDK to communicate with Gemini models.
  - `pydantic` ensures that the AI answers strictly in structured formats (like JSON with exact fields) instead of messy unstructured text.

---

### Step 2: The CEO Agent (`backend/app/agents/ceo.py`)
- **What it does:**
  - Reads your Product Requirements Document (PRD).
  - Uses `gemini-2.5-flash` to evaluate the PRD for market viability, missing features, and architectural flaws.
  - Returns a structured critique (`Verdict`: APPROVED, NEEDS_REVISION, or REJECTED).
  - Also includes a built-in offline fallback if no API key is set, so testing never crashes.
- **Why we built it:** Before writing code, you need to know if the product requirements are clear and complete. If requirements are bad, the generated code will also be bad.

---

### Step 3: The Developer Agent (`backend/app/agents/developer.py`)
- **What it does:**
  - Takes the approved PRD (and any notes you gave).
  - Uses `gemini-2.5-pro` to write full, functional, multi-file Python code (like `main.py`, `models.py`, `utils.py`, etc.).
  - Returns a structured `DeveloperCodeOutput` containing a list of `GeneratedFile` objects (each having a `path` and `content`).
- **Why we built it:** To dynamically write real code without relying on static templates or dummy placeholder text.

---

### Step 4: The QA Quality Engineer Agent (`backend/app/agents/qa.py`)
- **What it does:**
  - Takes all the Python code written by the Developer Agent.
  - Uses `gemini-2.5-pro` to inspect the code for bugs, missing error handling, and code smells.
  - Generates a `QAReport` containing a pass/fail verdict, an overview summary, and a list of `QAIssue` items with suggested refactorings.
- **Why we built it:** Even good developers make mistakes. Having an AI acting as a dedicated QA reviewer catches bugs and logic flaws early.

---

### Step 5: The Security Officer Agent (`backend/app/agents/security.py`)
- **What it does:**
  - Performs a Static Application Security Testing (SAST) review on the codebase.
  - Uses `gemini-2.5-pro` to scan for OWASP Top 10 vulnerabilities (such as SQL injection, input validation errors, and bad logging).
  - Produces a `SecurityReport` with detected `Vulnerability` items and concrete security patches to harden the code.
- **Why we built it:** Security must never be an afterthought. Automated scanning ensures the generated application is safe before it is packaged or deployed.

---

### Step 6: Direct Multi-Agent Pipeline (`backend/app/graph/builder.py`)
- **What it does:**
  - Uses **LangGraph** (`StateGraph`) to wire the four agents into a simple, direct pipeline:
    `ceo` -> `developer` -> `qa` -> `security` -> `END`.
  - Compiles the pipeline so it can be called with a single command or endpoint.
- **Why we built it:** To have a clear, fast, automatic execution pipeline that runs all 4 agents end-to-end without stopping for human intervention when needed.

---

### Step 7: Shared State Memory (`backend/app/graph/state.py`)
- **What it does:**
  - Defines `AgentState` using Python typing.
  - This is the "shared memory board" where every agent reads the current status and writes its results (PRD text, CEO critique, generated code, QA report, security report, and audit logs).
- **Why we built it:** Without a shared memory board, agents cannot pass their work to the next agent in line.

---

### Step 8: FastAPI Server & Endpoints (`backend/app/main.py` & `backend/app/api/sessions.py`)
- **What it does:**
  - Exposes REST API endpoints and WebSockets:
    - `POST /api/sessions/graph/run`: Runs the direct 4-agent graph from start to finish.
    - `POST /api/sessions/start`: Starts a session with the Human Approval Gate.
    - `POST /api/sessions/{session_id}/decide`: Submits your decision (Approve / Request Changes / Reject).
    - `GET /api/sessions/{session_id}/download`: Packages the hardened code into a downloadable ZIP file.
    - `WS /api/sessions/{session_id}/stream`: Streams real-time live logs to the browser.
    - `GET /health`: Checks if the server is alive.
    - `GET /docs`: Interactive Swagger documentation.
- **Why we built it:** Allows the frontend Web IDE, command line scripts, and external tools to interact with TARA easily over HTTP.

---

### Step 9: Web IDE Frontend (`backend/app/static/`)
- **What it does:**
  - A browser-based IDE featuring Monaco Editor (the same editor engine used in VS Code).
  - Displays real-time progress steps, agent critiques, code files, and security reports with a sleek dark theme.
- **Why we built it:** To provide an intuitive, visual interface for developers and stakeholders to watch the AI team work.

---

### Step 10: Hosted Locally on Server
- **What it does:**
  - Running on `http://127.0.0.1:8000/`.
  - Web IDE accessible at: `http://127.0.0.1:8000/`
  - Swagger API docs accessible at: `http://127.0.0.1:8000/docs`
- **Why we built it:** So you can test and use TARA directly from your browser right now on your machine.

---

## 4. Ongoing Work & Changelog

### Step 11: Real Sandboxed Execution & Dynamic SAST (Docker, E2B & Ephemeral Sandbox)
- **What was done:**
  - Built `backend/app/sandbox/runner.py` providing a 3-tier isolated execution environment (`E2BSandbox`, `DockerSandbox`, `LocalEphemeralSandbox`).
  - Completely replaced mock string matching in `backend/app/agents/security.py` with real dynamic static analysis tools: `bandit` (runs `bandit -r . -f json` and parses JSON), `flake8`, and Python `ast` syntax validation.
  - Added live code execution in the Web IDE via `POST /api/sessions/{session_id}/run`, a **"▶️ Run in Sandbox"** button in the editor toolbar, and an interactive **Sandbox Terminal** tab in the browser.
- **Why we built it:** 
  - To fulfill PRD requirements FR-18 through FR-20 (sandboxed execution).
  - To catch real security vulnerabilities (like shell injection, insecure imports, hardcoded secrets) with industrial-strength SAST tools instead of artificial string matches.
  - To let developers test and run their generated Python code immediately in the browser inside an isolated sandbox!

---

### Step 12: Tier 1 E2B Cloud MicroVM Sandbox Setup
- **What was done:**
  - Configured `E2B_API_KEY` in root and backend `.env` files.
  - Installed and pinned `e2b-code-interpreter>=2.10.0` in `backend/requirements.txt`.
  - Updated `backend/app/sandbox/runner.py` to use `Sandbox.create()`, automatic installation of SAST tools (`bandit`, `flake8`) on the cloud microVM, and graceful error handling for `CommandExitException`.
  - Verified live command execution and dynamic Bandit SAST running directly in cloud-isolated E2B MicroVMs.
- **Why we built it:**
  - Provides genuine cloud-isolated hardware virtualization for running untrusted user code and security scans without any danger to the host computer.

---

### Step 13: PDF Parsing Support & Document Ingestion (FR-6)
- **What was done:**
  - Installed `pypdf>=4.0.0` to provide pure-Python, fast binary PDF text extraction without heavy native C dependencies.
  - Added endpoint `POST /api/sessions/upload` in `backend/app/api/sessions.py` to ingest `.pdf`, `.md`, and `.txt` files, extract structured page-by-page text, and return metadata (`filename`, `file_type`, `page_count`, `char_count`, `extracted_text`).
  - Integrated drag-and-drop and file selection in the Web IDE (`backend/app/static/app.js`), allowing users to drop PDF specifications into the browser and immediately populate the PRD editor.
- **Why we built it:**
  - Fulfills PRD requirement FR-6.
  - Allows engineers and product managers to drop existing architectural PDFs directly into TARA without needing to manually copy/paste or convert them to markdown first.

---

### Step 14: Interactive Monaco 3-Way Diff & Editor Live Editing
- **What was done:**
  - Replaced the three static text boxes in the diff viewer with Monaco's native `monaco.editor.createDiffEditor()`, providing red/green line-level visual diff highlighting and gutter markers.
  - Added interactive diff stage selection tabs: `1. Dev ➔ QA`, `2. QA ➔ Security`, `3. Dev ➔ Security (Full)`, and `❖ 3-Way Dual View` (side-by-side dual Monaco diff editors), plus a toggle button for side-by-side vs inline diff layout.
  - Added **Live File Updates**: Configured `backend/app/core/session_manager.py` to broadcast `node_update` WebSocket messages as each LangGraph agent completes, refreshing the Monaco file tree live without waiting for pipeline completion.
  - Added **Live Code Editing**: Enabled live editing in the main Monaco editor, synchronizing manual user edits into the session files so that "▶️ Run in Sandbox" immediately executes user-modified code.
  - Created `want.md` in the project root documenting user inputs, credentials, and customization preferences for future milestones.
- **Why we built it:**
  - To turn TARA into a full-fledged, real-time Web IDE where users can watch files appear live as AI engineers build them, inspect exact line-by-line diffs across pipeline stages, and make manual edits directly in the browser.

---

### Step 15: Persistent State (SqliteSaver) & Automated 24h TTL Cleanup (APScheduler)
- **What was done:**
  - Swapped out the in-memory `MemorySaver()` in `backend/app/core/session_manager.py` for persistent SQLite storage using `SqliteSaver` (from `langgraph-checkpoint-sqlite`) stored at `backend/storage/tara_sessions.db`.
  - Created a `session_metadata` SQLite table to track each session's status, PRD filename, creation timestamp, and last updated timestamp across server restarts.
  - Built an automated cleanup engine in `backend/app/core/cleanup.py` with `cleanup_expired_resources()` to purge expired checkpoints, delete old `.zip` release packages from `storage/packages/`, and remove orphaned temp sandbox directories older than 24 hours (86,400s).
  - Integrated `APScheduler` (`BackgroundScheduler`) to automatically run the TTL cleanup job every hour without blocking FastAPI's async event loop.
  - Registered FastAPI `lifespan(app)` in `backend/app/main.py` for clean scheduler startup and shutdown.
  - Added new REST endpoints in `backend/app/api/sessions.py`: `GET /api/sessions` (list active sessions), `POST /api/sessions/cleanup` (manual TTL cleanup trigger), and `DELETE /api/sessions/{session_id}`.
  - Added a full test suite `backend/tests/test_persistence_cleanup.py` proving state persistence across process restarts and automated TTL cleanup.
- **Why we built it:**
  - Fulfills PRD Section 6.1 requirements.
  - Guarantees zero data loss on server restarts, prevents disk bloat by purging old artifacts after 24 hours, and keeps the server lean and production-ready.

---

### Step 16: Google Antigravity SDK Integration (`google-antigravity`)
- **What was done:**
  - Installed `google-antigravity` (version `0.1.16`) and pinned `google-antigravity>=0.1.16` in `backend/requirements.txt`.
  - Built an adapter in `backend/app/agents/antigravity_agent.py` to configure and spawn Antigravity autonomous agents with built-in code read and write capabilities (`VIEW_FILE`, `CREATE_FILE`, `EDIT_FILE`, `LIST_DIR`, `FIND_FILE`).
  - Added unit test suite `backend/tests/test_antigravity_sdk.py` to verify SDK installation, agent configuration, and tool availability.
- **Why we built it:**
  - Enables TARA's agents to use Google Antigravity's official SDK directly to read, navigate, create, and edit code files programmatically.

---

## 4. Ongoing Work & Changelog

*(New updates will be logged here as we continue building)*

| Date | Component / File | What Was Done | Why |
|---|---|---|---|
| 2026-09-14 | `backend/requirements.txt` | Installed & verified `google-genai` and `pydantic` | Core libraries required for Gemini API calls & schema outputs. |
| 2026-09-14 | `backend/app/agents/ceo.py` | Added `Verdict`, `CEOCritique`, and `evaluate_prd` | CEO agent to evaluate PRD viability using Gemini 2.5 Flash. |
| 2026-09-14 | `backend/app/agents/developer.py` | Added `GeneratedFile`, `DeveloperCodeOutput`, and `generate_code_from_prd` | Developer agent to generate full Python code using Gemini 2.5 Pro. |
| 2026-09-14 | `backend/app/agents/qa.py` | Added `QAIssue`, `QAReport`, and `analyze_code_qa` | QA agent to inspect multi-file code for bugs and quality issues. |
| 2026-09-14 | `backend/app/agents/security.py` | Added `Vulnerability`, `SecurityReport`, and `analyze_code_security` | Security agent to perform SAST analysis and output patches. |
| 2026-09-14 | `backend/app/graph/builder.py` | Created sequential LangGraph pipeline (`ceo` -> `developer` -> `qa` -> `security`) | Direct multi-agent execution pipeline without HITL pause. |
| 2026-09-14 | `backend/app/api/sessions.py` | Added `POST /api/sessions/graph/run` endpoint | Allows running the sequential graph via HTTP API. |
| 2026-09-14 | `backend/app/main.py` | Hosted locally via Uvicorn on `http://127.0.0.1:8000` | Makes Web IDE and API accessible locally in real time. |
| 2026-09-14 | `backend/app/core/llm.py` & agents | Built automatic high-quota model failover chain | `gemini-3.6-flash` has a strict preview limit of 20 requests/day (`429 RESOURCE_EXHAUSTED`), while `gemini-2.5-flash` was deprecated for new users (`404 NOT_FOUND`). Added `call_gemini_with_fallback` defaulting to `gemini-3.5-flash` and `gemini-3.5-flash-lite` to guarantee abundant free tier quota and zero interruptions. |
| 2026-09-14 | `backend/app/sandbox/` & `security.py` | Built 3-Tier Sandbox Runner, real Bandit/Flake8/AST SAST, and Web IDE 'Run in Sandbox' | Replaced mock strings with real Bandit JSON parsing mapped to OWASP Top 10, isolated execution sandbox, and live terminal execution in the browser. |
| 2026-09-14 | `backend/app/sandbox/runner.py` & `.env` | Enabled Tier 1 E2B Cloud MicroVM Sandbox with user API key | Cloud hardware-level isolation for running untrusted code and SAST scans. |
| 2026-09-14 | `backend/app/api/sessions.py` & `app.js` | Built PDF parsing support & `POST /api/sessions/upload` endpoint | Fulfills FR-6 by allowing drag-and-drop ingestion of `.pdf`, `.md`, and `.txt` specifications. |
| 2026-09-14 | `frontend` & `session_manager.py` | Added Monaco Native 3-Way Diff, Live WS File Updates, and Live Editing | Native diff highlighting (Dev ➔ QA ➔ Sec), live file tree updates during streaming, and live editing. |
| 2026-09-14 | `backend/app/core/session_manager.py` | Integrated `SqliteSaver` persistent checkpointer & session metadata | Persists multi-agent workflow checkpoints in SQLite across server restarts. |
| 2026-09-14 | `backend/app/core/cleanup.py` & `main.py` | Added APScheduler 24h automated TTL cleanup job & FastAPI lifespan hook | Automatically purges expired session checkpoints, packages, and temp folders every 24h. |
| 2026-09-14 | `backend/tests/test_persistence_cleanup.py` | Added automated persistence, TTL cleanup, and API test suite | 100% test pass rate verifying SQLite restart durability and cleanup pruning. |
| 2026-09-15 | `backend/app/agents/antigravity_agent.py` & `requirements.txt` | Integrated `google-antigravity` SDK & file tool configuration | Enables agents to inspect, view, edit, and create code files via official Antigravity tools. |
| 2026-09-14 | `want.md` | Created project requirements document for user inputs | Lists upcoming credentials (GitHub PAT) and Web IDE preferences. |
| 2026-09-14 | `learning.md` | Maintained this comprehensive learning document | To explain everything built in simple English and log all future progress. |
