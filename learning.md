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
| 2026-09-14 | `learning.md` | Created this comprehensive learning document | To explain everything built in simple English and log all future progress. |
