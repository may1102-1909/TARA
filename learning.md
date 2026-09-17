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
---

### Step 17: Antigravity SDK Autonomous Workspace Execution & Monaco Diff Streaming
- **What was done:**
  - **SDK Integration & Capabilities Configuration:** Configured the Google Antigravity Agent runtime (`google-antigravity` / `antigravity-sdk-python`) with built-in workspace capabilities (`READ_FILE`, `WRITE_FILE`, `LIST_DIR`) that map directly to Antigravity's `VIEW_FILE`, `CREATE_FILE`, `EDIT_FILE`, and `LIST_DIR` tools, targeting the local workspace root directory.
  - **Non-Blocking FastAPI Endpoints:** Created `POST /api/tara/edit` in `backend/app/routers/tara.py` which accepts user instructions, targets specific workspace files, and launches background agent tasks asynchronously (`asyncio.create_task`) without blocking the primary Uvicorn event loop. Added `GET /api/tara/jobs/{job_id}` for job status tracking and `GET /api/tara/status` for SDK readiness diagnostics.
  - **Real-Time WebSockets & Diff Streaming:** Implemented `/ws/tara` WebSocket route that passes user prompts to `agent.chat(prompt)` and streams agent thoughts, tool invocations, tokens, and progressive line-by-line diffs (`diff_line`) and complete diff models (`file_diff`) over WebSockets.
  - **Monaco Diff Editor Integration:** Connected frontend `app.js` to `/ws/tara` so incoming diffs stream directly into Monaco's `createDiffEditor()` via `monaco.editor.createModel()`, rendering real-time code additions, deletions, and modifications.
  - **Comprehensive Test Suite:** Built automated tests in `backend/tests/test_antigravity_sdk.py` verifying SDK capability resolution, workspace targeting, diff calculations, asynchronous REST endpoints, and WebSocket streaming.
- **Why we built it:**
  - Moves TARA beyond basic LLM prompts into a true agentic coding engine capable of directly reading, navigating, editing, and streaming codebase diffs into the Monaco editor with non-blocking concurrency.

---

### Step 18: Dribbble-Inspired "IDE — AI Developer Environment" UI/UX Overhaul
- **What was done:**
  - **Slim Vertical Activity Dock (52px):** Implemented a high-end icon dock on the far left with glowing SVG icons for PRD Spec, File Explorer, Code Canvas, 3-Way Diff, Security SAST, Sandbox Terminal, and Copilot Toggle.
  - **Right-Side Dedicated AI Copilot Panel (350px):** Built an interactive AI copilot drawer directly connected to the `/ws/tara` WebSocket stream. Displays real-time typing responses, collapsible thought accordions with subtle violet glow, tool execution pill badges, and quick action chips (`⚡ Add TTL Eviction`, `🛡️ SAST Hardening`, `🧪 Generate Pytest`).
  - **Floating Monaco Canvas Controls & Breadcrumbs:** Added path breadcrumbs (`workspace / src / main.py`), live editing indicator, and floating action pills (`▶ Run in Sandbox`, `❖ 3-Way Diff`).
  - **Obsidian Glassmorphic Theme:** Designed a deep charcoal/obsidian palette (`#07090e`, `#10141f`, `#151a28`) with electric violet (`#8b5cf6`) and cyber cyan (`#06b6d4`) accents, subtle glowing borders, and backdrop blurs (`backdrop-filter: blur(16px)`).
- **Why we built it:**
  - Directly matches the high-end, futuristic **"IDE - AI developer environment"** visual concept by Anatoliy Demyanchuk on Dribbble, giving TARA a world-class developer experience.

---

### Step 19: Strix Autonomous Security Tool Integration & E2B Runner Pipeline
- **What was done:**
  - **E2B Sandbox Update:** Updated `backend/app/sandbox/e2b_runner.py` and `backend/app/sandbox/runner.py` to run three security tools against the workspace inside isolated execution environments (E2B Cloud MicroVM, Docker, or LocalEphemeral): `flake8`, `bandit -r . -f json`, and `strix -n --target ./` (running in non-interactive mode).
  - **Environment Variable Forwarding:** Forwarded `STRIX_LLM` and `LLM_API_KEY` (as well as `GEMINI_API_KEY`) into the E2B instance context via `envs` in `Sandbox.create(...)` and `commands.run(...)`.
  - **Unified Output Parser & SecurityFinding Schema:** Combined results from Flake8, Bandit, and Strix into a unified Pydantic `SecurityFinding` schema (`tool`, `severity`, `issue`, `file_path`, `line_number`, `category`, `exploit_poc`, `patch_recommendation`). Handled both JSON payloads and structured CLI report formats.
  - **Automated Hardening with ChatGoogleGenerativeAI:** Integrated `ChatGoogleGenerativeAI` in `backend/app/agents/security.py` to synthesize production-ready hardened code patches from the unified security findings, with an option to write patched versions directly to workspace files.
  - **Real-Time WebSocket Updates & Monaco Diff Sync:** Integrated `/ws/security` and connected `backend/app/static/app.js` to stream real-time tool execution logs (`[FLAKE8]`, `[BANDIT]`, `[STRIX]`), line-by-line diffs (`diff_line`), and complete diff models (`file_diff`) into Monaco's `createDiffEditor()` for side-by-side or inline review, with one-click patch application (`btn-accept-patch`).
  - **Automated Verification:** Added a comprehensive test suite `backend/tests/test_e2b_strix.py` (9 passing tests) verifying schema serialization, OWASP mapping, environment forwarding, CLI output parsing, patching with disk writing, WebSocket streaming, and REST endpoints.
- **Why we built it:**
  - Brings autonomous penetration testing (`usestrix/strix`) into TARA's security layer alongside static linters (Flake8) and AST analysis (Bandit).
  - Gives developers an end-to-end automated security pipeline: discover vulnerabilities, forward LLM context in an isolated E2B microVM, synthesize AI patches with Gemini, and visually review and accept diffs directly inside the Monaco editor.

---

### Step 20: Model Context Protocol (MCP) Servers Integration with Strix & Google Antigravity IDE
- **What was done:**
  - **Strix MCP Configuration:** Created `~/.strix/mcp-servers.json` and project workspace `./mcp-servers.json` defining both local stdio tools (`local_fs` via `@modelcontextprotocol/server-filesystem`) and remote HTTP tools (`github` via Copilot MCP endpoint).
  - **Antigravity IDE Customization Registration:** Configured `~/.gemini/config/mcp_config.json` and `.agents/mcp_config.json` using Antigravity's `mcpServers` schema (`serverUrl` and `headers` for HTTP transports, `command` and `args` for stdio).
  - **Strix Runner & E2B Runner MCP Flags:** Enhanced `backend/app/sandbox/strix_runner.py` and `backend/app/sandbox/e2b_runner.py` to support `--mcp-config`, `--mcp-server`, and `--mcp-exclude` CLI flags, mount configuration paths, bundle `mcp-servers.json` into sandbox payloads, and parse MCP connection logs (`MCP: connected X servers (Y tools): ...`).
  - **Security Agent & API Schemas:** Added `mcp_config`, `mcp_server`, and `mcp_exclude` fields to `StrixScanRequest` in `backend/app/routers/security.py` and passed them down to `run_unified_security_scan`.
  - **Skill Documentation:** Updated `.agents/skills/strix-security-scan/SKILL.md` with configuration guides, CLI options, verification steps, and dashboard commands (`strix view`).
- **Why we built it:**
  - Standardizes tool access across both the Antigravity agent runtime and Strix's autonomous penetration testing loops through open Model Context Protocol (MCP) servers.
  - Allows Strix to discover issues, query repositories, and interact with external systems using verified MCP tools with granular inclusion and exclusion controls.

---

### Step 21: Real-Time Token-by-Token Code Generation with Antigravity SDK & Monaco Live Streaming
- **What was done:**
  - **Antigravity SDK Backend Streaming (`backend/app/routers/tara_stream.py`):** Created a dedicated streaming router initializing `google.antigravity.Agent` using `LocalAgentConfig` with `api_key=os.getenv("GEMINI_API_KEY")`. Implemented `async for chunk in agent.chat(user_prompt, stream=True):` to capture content deltas and streamed structured JSON payloads (`{ "type": "CODE_DELTA", "file_path": "main.py", "delta": chunk.text }`) over the `/ws/tara/stream` WebSocket endpoint.
  - **FastAPI Lifecycle Mount:** Registered the WebSocket `/ws/tara/stream` endpoint before static asset mounts in `backend/app/main.py`.
  - **Client-Side Live Monaco Typing (`backend/app/static/app.js`):** Connected to `/ws/tara/stream`. On receiving `CODE_DELTA`, resolves the active Monaco editor model (`this.editor.getModel()`), calculates the active cursor boundary, and applies character edits directly into the buffer via `editor.executeEdits("tara-stream", [...])` rather than replacing the buffer at the end. Automatically tracks cursor positioning via `editor.revealLine()`.
  - **Interactive UI Support:** Added a "⚡ Live Stream" persona chip in the copilot panel and enabled `/stream` / `/live` prompt prefixes.
- **Why we built it:**
  - Moves beyond batch generation or whole-file replacements, giving developers an interactive AI pair-programming experience where code appears token-by-token in real time.

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
| 2026-09-15 | `backend/app/routers/tara.py` & `tara_agent.py` | Built non-blocking `/api/tara/edit`, `/ws/tara` diff streaming, and Monaco viewer | Autonomous workspace file execution with progressive line diffs rendered directly in Monaco. |
| 2026-09-15 | `frontend` (`index.html`, `style.css`, `app.js`) | Re-engineered UI to match Dribbble "IDE - AI developer environment" | Slim Activity Dock, right AI Copilot drawer, floating Monaco breadcrumb bar, and obsidian glassmorphism. |
| 2026-09-15 | `backend/app/sandbox/e2b_runner.py` & `runner.py` | Integrated Strix (`strix -n --target ./`), Flake8, and Bandit in E2B with env forwarding | Triple-layer SAST & penetration testing with `STRIX_LLM` and `LLM_API_KEY` forwarded to E2B context. |
| 2026-09-15 | `backend/app/agents/security.py` & `routers/security.py` | Unified `SecurityFinding` Pydantic parser, ChatGoogleGenerativeAI patcher, and `/ws/security` | Automatic code patch synthesis, disk writes, and real-time Monaco `createDiffEditor()` streaming. |
| 2026-09-15 | `backend/tests/test_e2b_strix.py` | Comprehensive test suite for Strix E2B runner, parser, and WebSocket diff stream | 100% pass rate across 9 tests verifying triple-layer security pipeline. |
| 2026-09-14 | `want.md` | Created project requirements document for user inputs | Lists upcoming credentials (GitHub PAT) and Web IDE preferences. |
| 2026-09-14 | `learning.md` | Maintained this comprehensive learning document | To explain everything built in simple English and log all future progress. |
| 2026-09-16 | `backend/app/main.py` | Fixed WebSocket 403 Forbidden errors on `/ws/security` and `/ws/tara` | Root cause: `allow_credentials=True` with `allow_origins=["*"]` violates CORS spec and rejects WS upgrades. Fixed by setting `allow_credentials=False` and reordering routes so WebSocket endpoints are registered before StaticFiles mounts. |
| 2026-09-16 | `backend/app/static/style.css` | Complete CSS redesign: forest-green/cream color palette and IDE layout | Replaced obsidian-charcoal/purple theme with deep forest green (`#2B3F31`) backgrounds and warm cream (`#E5D5BE`) accents, matching user's reference images. Layout refined to mirror the two-panel IDE split from the Dribbble screenshot. |
| 2026-09-16 | `backend/app/static/style.css` | Antigravity 3-Theme CSS Engine | Complete rewrite with `data-theme` attribute-driven CSS variables. 3 palettes: Dark Obsidian (`#1E1F22`), Light Clean Slate (`#FFFFFF`), Cyber High-Contrast (`#0B0E14`). All colors reference CSS variables for instant theme switching. Glassmorphism on modals, 4px corners, smooth transitions. |
| 2026-09-16 | `backend/app/static/index.html` | Antigravity Layout Redesign | Restructured to: Left Nav Rail (dock icons) → File Tree Sidebar → Center Monaco Canvas (code/diff/audit tabs) → Right AI Copilot Panel → Bottom Terminal. Added theme selector dropdown in header. All DOM IDs preserved for `app.js` backward compatibility. |
| 2026-09-16 | `backend/app/static/theme.js` | Dynamic Theme Switching Engine | New file: switches `data-theme` on `<html>`, syncs Monaco themes (`vs-dark`/`vs`/`hc-black`), persists to localStorage, supports `Ctrl+Shift+T` keyboard shortcut for cycling. Exposes `window.TaraTheme` API. |
| 2026-09-16 | `style.css`, `index.html`, `theme.js` | **Monochrome Obsidian Redesign** | Complete rewrite to ChatGPT/Vercel/Shadcn-inspired aesthetic. Pitch black `#09090B` base, `#121215` surfaces, `#27272A` zinc borders, pure white `#FFFFFF` primary CTAs (white bg, black text). Zero gradients, glows, or neon. 6px radius, 150ms transitions, Inter + JetBrains Mono. Active dock items use 2px white left-border indicator. Diff highlights use muted green/red rgba overlays. |
| 2026-09-16 | `mcp-servers.json`, `~/.strix/`, `strix_runner.py`, `e2b_runner.py` | **Model Context Protocol (MCP) Integration for Strix & Antigravity** | Registered global and workspace MCP servers for `local_fs` and `github`. Added `--mcp-config`, `--mcp-server`, `--mcp-exclude` execution options to Strix and E2B runners. Surfaced live MCP tool connection status events in WebSocket pipeline and updated skill documentation. |
---

### Step 22: Live Code Writing on Human Approval & Interactive Streaming
- **What was done:**
  - **Live Code Writing on Human Approval (`backend/app/static/app.js`):** When the user approves at the Human Approval Gate, TARA now immediately switches the center Monaco canvas to the "Code" tab (`#tab-editor-view`), clears the initial template comments, sets the active file to `src / main.py`, and triggers token-by-token live streaming via `/ws/tara/stream`.
  - **Direct Character Buffer Streaming:** As content deltas arrive via WebSockets, Monaco inserts text continuously using `executeEdits` and scrolls along with the cursor using `revealLine`, giving the user real-time visual feedback of code being authored live.
  - **Clean Code Output (`backend/app/routers/tara_stream.py`):** Stripped markdown code fences (````python` and ````) on chunk arrival and reinforced the system instruction to write raw executable Python directly into the editor buffer.
  - **Automatic Prompt Routing:** Any prompt in the right Copilot panel requesting code generation or modifications (or using the `⚡ Live Stream` chip) now streams directly into Monaco in real time.
- **Why we built it:**
  - In earlier versions, clicking "Approve" triggered a synchronous background server job. While agents were thinking and generating code on the server, the user was left looking at an empty editor with a static comment for 30 seconds wondering if anything was happening. Live streaming makes the entire development process visible, transparent, and engaging.

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
| 2026-09-15 | `backend/app/routers/tara.py` & `tara_agent.py` | Built non-blocking `/api/tara/edit`, `/ws/tara` diff streaming, and Monaco viewer | Autonomous workspace file execution with progressive line diffs rendered directly in Monaco. |
| 2026-09-15 | `frontend` (`index.html`, `style.css`, `app.js`) | Re-engineered UI to match Dribbble "IDE - AI developer environment" | Slim Activity Dock, right AI Copilot drawer, floating Monaco breadcrumb bar, and obsidian glassmorphism. |
| 2026-09-15 | `backend/app/sandbox/e2b_runner.py` & `runner.py` | Integrated Strix (`strix -n --target ./`), Flake8, and Bandit in E2B with env forwarding | Triple-layer SAST & penetration testing with `STRIX_LLM` and `LLM_API_KEY` forwarded to E2B context. |
| 2026-09-15 | `backend/app/agents/security.py` & `routers/security.py` | Unified `SecurityFinding` Pydantic parser, ChatGoogleGenerativeAI patcher, and `/ws/security` | Automatic code patch synthesis, disk writes, and real-time Monaco `createDiffEditor()` streaming. |
| 2026-09-15 | `backend/tests/test_e2b_strix.py` | Comprehensive test suite for Strix E2B runner, parser, and WebSocket diff stream | 100% pass rate across 9 tests verifying triple-layer security pipeline. |
| 2026-09-14 | `want.md` | Created project requirements document for user inputs | Lists upcoming credentials (GitHub PAT) and Web IDE preferences. |
| 2026-09-14 | `learning.md` | Maintained this comprehensive learning document | To explain everything built in simple English and log all future progress. |
| 2026-09-16 | `backend/app/main.py` | Fixed WebSocket 403 Forbidden errors on `/ws/security` and `/ws/tara` | Root cause: `allow_credentials=True` with `allow_origins=["*"]` violates CORS spec and rejects WS upgrades. Fixed by setting `allow_credentials=False` and reordering routes so WebSocket endpoints are registered before StaticFiles mounts. |
| 2026-09-16 | `backend/app/static/style.css` | Complete CSS redesign: forest-green/cream color palette and IDE layout | Replaced obsidian-charcoal/purple theme with deep forest green (`#2B3F31`) backgrounds and warm cream (`#E5D5BE`) accents, matching user's reference images. Layout refined to mirror the two-panel IDE split from the Dribbble screenshot. |
| 2026-09-16 | `backend/app/static/style.css` | Antigravity 3-Theme CSS Engine | Complete rewrite with `data-theme` attribute-driven CSS variables. 3 palettes: Dark Obsidian (`#1E1F22`), Light Clean Slate (`#FFFFFF`), Cyber High-Contrast (`#0B0E14`). All colors reference CSS variables for instant theme switching. Glassmorphism on modals, 4px corners, smooth transitions. |
| 2026-09-16 | `backend/app/static/index.html` | Antigravity Layout Redesign | Restructured to: Left Nav Rail (dock icons) → File Tree Sidebar → Center Monaco Canvas (code/diff/audit tabs) → Right AI Copilot Panel → Bottom Terminal. Added theme selector dropdown in header. All DOM IDs preserved for `app.js` backward compatibility. |
| 2026-09-16 | `backend/app/static/theme.js` | Dynamic Theme Switching Engine | New file: switches `data-theme` on `<html>`, syncs Monaco themes (`vs-dark`/`vs`/`hc-black`), persists to localStorage, supports `Ctrl+Shift+T` keyboard shortcut for cycling. Exposes `window.TaraTheme` API. |
| 2026-09-16 | `style.css`, `index.html`, `theme.js` | **Monochrome Obsidian Redesign** | Complete rewrite to ChatGPT/Vercel/Shadcn-inspired aesthetic. Pitch black `#09090B` base, `#121215` surfaces, `#27272A` zinc borders, pure white `#FFFFFF` primary CTAs (white bg, black text). Zero gradients, glows, or neon. 6px radius, 150ms transitions, Inter + JetBrains Mono. Active dock items use 2px white left-border indicator. Diff highlights use muted green/red rgba overlays. |
| 2026-09-16 | `mcp-servers.json`, `~/.strix/`, `strix_runner.py`, `e2b_runner.py` | **Model Context Protocol (MCP) Integration for Strix & Antigravity** | Registered global and workspace MCP servers for `local_fs` and `github`. Added `--mcp-config`, `--mcp-server`, `--mcp-exclude` execution options to Strix and E2B runners. Surfaced live MCP tool connection status events in WebSocket pipeline and updated skill documentation. |
| 2026-09-16 | `tara_stream.py`, `main.py`, `app.js` | **Token-by-Token Antigravity Code Streaming into Monaco** | Built `/ws/tara/stream` WebSocket endpoint using Antigravity Agent async iterator `chat(stream=True)`. Integrated Monaco `executeEdits` buffer insertion and `revealLine` auto-scroller for live typing. |
| 2026-09-16 | `app.js`, `tara_stream.py`, `learning.md` | **Live Code Writing on Approval Gate** | Connected HITL Approve action and Copilot prompt inputs directly to `/ws/tara/stream` so Monaco immediately opens `main.py` and live-types code character by character in real time. |
| 2026-09-17 | `tara_stream.py`, `app.js`, `index.html`, `style.css` | **Interactive Code Editing & Pair-Programming System** | Transformed the editor and copilot chat into a fully interactive AI pair-programmer: context-aware editing of existing editor code, inline `Ctrl+K` AI command bar, Accept/Undo review banner, multi-model failover, and interactive quick action chips. |

---

### Step 23: Interactive Code Editing & Pair-Programming System
- **What was done:**
  - **Context-Aware Code Editing (`backend/app/routers/tara_stream.py`):** Upgraded `AntigravityStreamAgent.chat()` and `/ws/tara/stream` to ingest the active editor's `current_code`, selected lines (`selection`), and target file path. Instead of wiping the buffer and starting over with a generic template, TARA now surgically modifies, refactors, or adds methods to the user's existing codebase while preserving existing architecture, imports, and classes.
  - **Multi-Model Availability Failover:** Built an automatic model failover loop across `gemini-3.5-flash`, `gemini-3.5-flash-lite`, and `gemini-2.5-flash` to prevent `503 UNAVAILABLE` or `404 NOT_FOUND` outages.
  - **Interactive Inline AI Command Bar (`Ctrl+K`):** Added a floating interactive command bar directly inside the Monaco editor canvas (toggleable via `Ctrl+K`, `Cmd+K`, or the `✨ Edit with TARA` topbar button). Allows developers to type editing directives or click quick suggestion chips directly over the code.
  - **Active Editor Review & Rollback Bar (`[✓ Accept] [↺ Undo]`):** Before modifying code, TARA captures a rollback snapshot. After streaming updates, a floating review bar allows developers to inspect the result and click `↺ Undo` to immediately revert or `✓ Accept` to keep the changes.
  - **Interactive Copilot Chat & Quick Action Chips:** Wired up all Copilot chips (`⚡ Add TTL Eviction`, `🛡 SAST Hardening`, `🧪 Generate Tests`) and the prompt textarea so any user instruction in the chat drawer applies directly to the active Monaco Editor and replies with conversational confirmation.
- **Why we built it:**
  - Coding assistants should be conversational pair-programmers, not static one-way generators. Developers can now talk directly to their code: asking TARA to add a function, edit a line, fix an edge case, or generate tests, and watch the editor update live with full undo control.
