# TARA — Tech-Architecture & Automated Review Assistant

> Autonomous software consultancy inside a web-based IDE powered by multi-agent orchestration.

---

## Overview

**TARA** transforms a raw Product Requirements Document (PRD/BRD, `.pdf` or `.md`) into a verified, refactored, and security-hardened Python codebase through an observable pipeline of 4 specialized AI agents:

1. **CEO / VC Evaluator**: Critiques business viability, flags gaps, and halts at a **Human-in-the-Loop (HITL) approval gate** (Approve / Request Changes / Reject).
2. **Software Developer**: Generates modular Python source code based on the approved spec.
3. **Quality Engineer (QA)**: Refactors verbose or custom code into standard-library idioms and best practices.
4. **Security Officer**: Conducts automated SAST (`bandit`, `flake8`, `ast`), patches vulnerabilities, and produces a final release package (`.zip`) with an audit summary.

The user interacts through a VS Code-like interface featuring **Monaco Editor**, real-time streaming agent console outputs, and a 3-way code diff viewer (`Dev` → `QA` → `Security`).

---

## Documentation

- [Full PRD & BRD Specification (v1.1)](./docs/PRD.md)

---

## Architectural Highlights

- **Frontend**: Next.js (React) + Monaco Editor + WebSocket/SSE streaming + 3-way Diff Viewer.
- **Backend Orchestration**: Python LangGraph `StateGraph` with native interrupts and session checkpointing (Sqlite / Redis / PostgreSQL).
- **Execution Sandbox**: Docker / E2B sandbox for isolated code generation, test execution, and SAST.
- **Target Output**: Python (v1).

---

## Milestones

- [x] **M1**: LangGraph workflow skeleton with working human-in-the-loop interrupt/resume (API-driven).
- [ ] **M2**: Monaco-based IDE shell with streaming console tabs wired to backend.
- [ ] **M3**: CEO agent integrated end-to-end: upload → critique → approval gate (with revision loop).
- [ ] **M4**: Developer + QA agents integrated with sandboxed execution; live file tree population.
- [ ] **M5**: Security agent integrated; SAST + automated patching + zip export.
- [ ] **M6**: Beta hardening: reconnect logic, session cleanup, audit summary polish.

---

## Getting Started

### Backend Setup & Tests

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Run automated test suite
$env:PYTHONPATH="backend"
python -m pytest backend/tests -v

# 3. Start development server
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

