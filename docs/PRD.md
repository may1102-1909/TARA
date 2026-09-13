# TARA — Tech-Architecture & Automated Review Assistant
## Product Requirements Document (PRD) & Business Requirements Document (BRD)

**Document Version:** 1.1  
**Status:** Draft  
**Date:** September 13, 2026  

**Changelog (v1.1):** Locked v1 target language (Python), resolved approval-gate strategy (single gate + Request Changes loop), defined retention policy, and confirmed HITL strategy (single gate + diff viewer). See Sections 3.1, 5.3, 5.4, 6, and 9.

---

## 1. Executive Summary

TARA is a multi-agent AI system that simulates an autonomous software consultancy inside a web-based IDE. A user uploads a Product Requirements Document (PRD/BRD, `.pdf` or `.md`), and a pipeline of four specialized AI agents — CEO, Developer, QA Engineer, and Security Officer — sequentially evaluate, build, refine, and harden a working software artifact from that spec. The experience is delivered through a VS Code–like interface (Monaco Editor) with live streaming console output per agent, a human-in-the-loop approval gate after the initial business critique, and a sandboxed execution environment for safe code generation and adversarial security testing.

The end deliverable is a downloadable package containing refined source code, security patches, and an audit summary — effectively compressing a full software consultancy engagement (viability review → build → QA → security hardening) into a single automated, observable workflow.

---

## 2. Business Objectives (BRD)

| Objective | Description |
|---|---|
| **Reduce time-to-prototype** | Compress the cycle from "idea/spec" to "reviewed, secured code" from days/weeks to a single automated session. |
| **De-risk early builds** | Catch market/product flaws (CEO agent) *before* any code is written, avoiding wasted engineering effort. |
| **Enforce quality gates by default** | Make refactoring-to-standards and security review non-optional steps in the generation pipeline, not afterthoughts. |
| **Preserve human control** | Ensure no code is generated or executed without explicit human sign-off on the business case first. |
| **Demonstrate agentic orchestration** | Serve as a flagship example of a stateful, auditable, multi-agent system with real HITL (human-in-the-loop) checkpoints — not a single mega-prompt. |

### 2.1 Target Users
- Solo founders / indie hackers validating an idea and wanting a first secured codebase.
- Engineering leads who want an automated first-pass review pipeline (business + code + security) before human review.
- Hackathon teams and internal innovation labs needing rapid, defensible prototypes.
- Internal platform teams evaluating LangGraph/agentic orchestration patterns.

### 2.2 Success Metrics
- **Time-to-package**: median time from PRD upload to downloadable zip < 15 minutes for a small-to-medium spec.
- **Approval-gate integrity**: 100% of runs halt at the CEO checkpoint until explicit human action (no silent auto-proceed).
- **Vulnerability catch rate**: Security agent flags ≥ OWASP Top 10 categories relevant to the generated stack.
- **Session resumability**: ≥ 99% of paused sessions can be resumed after the human decision, even after browser refresh.
- **User trust signal**: post-run survey — users report the audit summary as "clear enough to act on" (qualitative, tracked in beta).

---

## 3. Scope

### 3.1 In Scope (v1)
- **Target generated-code language: Python.** Standardizing the *output* on Python keeps v1 complexity low — static analysis tooling (`ast`, `bandit`, `flake8`) is mature, deterministic, and runs cleanly inside sandboxes for the QA and Security agents.
- **Agent backend framework: either Python (LangGraph) or TypeScript/Node.js (`LangGraph.js` / `@langchain/langgraph`)** — team's choice based on the primary stack. Since the frontend is Next.js, `LangGraph.js` is a valid option to keep orchestration native to Node; Python LangGraph remains the reference implementation for agent/tooling maturity.
- Single-project, single-PRD runs (one spec in, one package out).
- Four fixed agent roles (CEO, Developer, QA, Security), executed per the defined graph.
- Monaco-based file viewer/editor for generated files (read/edit, not full multi-file project management).
- Streaming console output per agent via WebSocket/SSE.
- One human-in-the-loop gate (post-CEO review).
- Sandboxed code execution (Docker or E2B) for generation, testing, and security probing.
- Zip export of final code, patches, and audit summary.
- Support for `.pdf` and `.md` PRD uploads.

### 3.2 Out of Scope (v1)
- Generated code in languages other than Python (e.g., TypeScript/Node, Go output targets are deferred to v2+).
- Multi-repo or existing-codebase ingestion (brownfield projects).
- Continuous/production deployment pipelines (CI/CD integration is a future phase).
- Multiple human approval gates (only one gate at CEO step in v1).
- Real-time multi-user collaboration in the IDE.
- Support for languages/stacks beyond an initial supported set (to be defined in tech spec — e.g., Python and TypeScript/Node first).
- Fine-grained per-line human code review UI (beyond basic Monaco editing).

---

## 4. User Journey (End-to-End)

1. **Upload**: User uploads a `.pdf` or `.md` PRD/BRD through the IDE's landing/upload panel.
2. **CEO Review**: Agent 1 parses the document, evaluates market viability, feature gaps, and flaws, and streams an executive critique to its console tab.
3. **Approval Gate**: Workflow halts. UI surfaces the critique with three actions: **Approve & Proceed**, **Request Changes**, or **Reject**. Choosing Request Changes lets the user attach notes, which are appended to the conversation history before looping back to the CEO agent for a revised critique. State is persisted so the session survives a page refresh, across any number of revision loops.
4. **Build Phase**: On approval, Agent 2 (Developer) and Agent 3 (QA Engineer) run — Developer drafts modules; QA concurrently/iteratively refactors verbose or custom code into standard-library equivalents. Both stream to their own console tabs; files appear live in the Monaco file tree.
5. **Security Phase**: Agent 4 (Security Officer) performs SAST against the refactored code inside the sandbox, patches identified vulnerabilities, and compiles the release package.
6. **Delivery**: User downloads a `.zip` containing final code, applied patches, and a human-readable audit summary (what was found, what was fixed, what remains as a known risk).
7. **Rejection path**: If the user rejects at the approval gate, the workflow ends; the CEO critique remains available for reference/export, and no code is generated.

---

## 5. Functional Requirements

### 5.1 Frontend / IDE Interface
| ID | Requirement |
|---|---|
| FR-1 | Web-based IDE built on Next.js/React. |
| FR-2 | Monaco Editor integration for file tree browsing, syntax-highlighted viewing, and editing of generated files. |
| FR-3 | Separate console/tab per agent (CEO, Developer, QA, Security) showing streamed, timestamped output. |
| FR-4 | Persistent workflow state indicator (e.g., a stepper: CEO → Approval → Build → Security → Package) visible at all times. |
| FR-5 | Approval gate UI: renders the CEO's critique in full, with **Approve**, **Request Changes** (with a free-text notes field), and **Reject** controls; disables downstream tabs until a decision is made. |
| FR-5a | On Request Changes, the UI shows the revision count/history so the user can track how many rounds of feedback have occurred. |
| FR-5b | After QA and Security phases complete, the Monaco Editor surfaces a **Diff Viewer** showing `Original Dev Code` → `Refactored QA Code` → `Hardened Security Code`, so the user can visually review all automated changes before downloading. |
| FR-6 | File upload component supporting `.pdf` and `.md`, with client-side validation (file type, size limit). |
| FR-7 | Download panel for the final `.zip` package once the Security phase completes. |
| FR-8 | Session recovery: reloading the page restores the correct workflow state and streamed history from the backend. |

### 5.2 Real-Time Communication
| ID | Requirement |
|---|---|
| FR-9 | Backend streams agent output to the frontend via WebSockets or SSE, keyed by agent/session ID. |
| FR-10 | Each console tab subscribes only to its corresponding agent's stream to avoid cross-talk. |
| FR-11 | Connection loss triggers automatic reconnect with backfill of missed messages from the persisted state. |

### 5.3 Backend Orchestration (LangGraph)
| ID | Requirement |
|---|---|
| FR-12 | Orchestration implemented as a `StateGraph` with nodes: `ceo_node`, `human_approval_gate`, `dev_qa_node` (parallel), `security_node`. |
| FR-13 | Graph execution halts at `human_approval_gate` until an external `approve` / `request_changes` / `reject` signal is received via API — true interrupt, not a polling stub. |
| FR-14 | Shared `AgentState` object carries the PRD content, CEO critique, human feedback notes, a `revision_count`, generated code artifacts, QA refactor notes, and security findings across nodes. |
| FR-15 | `dev_qa_node` runs Developer and QA agents with a defined interaction pattern (e.g., QA reviews Developer's output incrementally, not only after full completion). |
| FR-16 | Conditional edge (`post_ceo_router`) routes to `dev_qa_node` on approval, back to `ceo_node` (with appended human notes and incremented `revision_count`) on Request Changes, or `END` on rejection: <br>```python<br>def post_ceo_router(state: AgentState):<br>    if state["user_action"] == "approve":<br>        return "dev_qa_node"<br>    elif state["user_action"] == "request_changes":<br>        return "ceo_node"  # loops back with human feedback added to prompt<br>    return END  # reject / exit<br>``` |
| FR-16a | No hard cap on `revision_count` in v1, but the UI surfaces the count to the user; consider a soft warning (not a block) past a configurable threshold (e.g., 5 rounds) to surface possible loop fatigue. |
| FR-17 | All intermediate state is checkpointed (e.g., LangGraph persistence/checkpointer) so a paused session survives backend restarts. |

### 5.4 Agent Specifications

**Agent 1 — CEO / VC Evaluator**
- Input: parsed PRD/BRD text (from `.pdf`/`.md`).
- Task: assess market viability, identify feature gaps, flag structural/logical flaws.
- Output: structured executive critique (summary verdict, key risks, gaps, recommendation) + raw commentary stream.
- Must explicitly request human sign-off; must not proceed automatically.
- **Revision handling**: when re-entered via a Request Changes loop, must incorporate the appended human notes and produce an updated critique (not a repeat of the original) — the prompt should reference `revision_count` and prior feedback explicitly.

**Agent 2 — Software Developer**
- Input: approved spec + CEO critique (as context/constraints).
- Task: draft functional code modules implementing the approved scope.
- Output: file tree of raw source files, streamed incrementally to its console and the Monaco file view.

**Agent 3 — Quality Engineer**
- Input: Developer's code output (may run concurrently, reviewing as files land).
- Task: refactor verbose/custom implementations into language-standard library equivalents (e.g., custom HTTP handling → standard library HTTP server); improve readability/maintainability.
- Output: refactored files + a change log of what was replaced and why.

**Agent 4 — Security Officer / Hacker**
- Input: refactored code from QA phase.
- Task: run static analysis (SAST) mapped to OWASP Top 10 categories; attempt to identify exploitable patterns; patch identified issues.
- Output: patched code, a vulnerability report (finding, severity, fix applied or residual risk), and the final compiled release package.
- Must execute all analysis/testing inside the sandbox — never against the host.

### 5.5 Sandbox & Packaging
| ID | Requirement |
|---|---|
| FR-18 | All code generation, execution, and security testing runs inside isolated containers (Docker or E2B). |
| FR-19 | Sandbox has no network/filesystem access to the host server or other sessions. |
| FR-20 | Sandbox is torn down (or reset) at the end of each session. |
| FR-21 | Final output is packaged as a `.zip` containing: final code, applied security patches, and a human-readable audit summary document. |
| FR-22 | Audit summary includes a timeline of what each agent did, key decisions, and any unresolved risks flagged by the Security agent. |

---

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Security** | No agent-generated or agent-executed code ever runs outside the sandbox. Host secrets/credentials must never be reachable from within the sandbox. |
| **Reliability** | Graph state must be durable across a pause of arbitrary length (approval gate has no timeout by default, or a configurable one). |
| **Observability** | Every agent action (tool call, file write, decision) is logged and retrievable for the audit summary. |
| **Performance** | Streaming output should feel "live" (sub-second latency from agent token generation to UI render). |
| **Scalability** | Each session's sandbox and graph execution should be isolated per-user/session to support concurrent runs. |
| **Extensibility** | Agent roles, prompts, and graph edges should be config-driven where feasible, to support adding new agents/stages later without core rework. |

### 6.1 Data Retention Policy

| Data | Storage | Retention |
|---|---|---|
| **Active workflow state** | Redis / PostgreSQL via LangGraph checkpointer threads | Duration of the active session (including any Request Changes revision loops). |
| **Sandbox containers (Docker/E2B)** | Ephemeral, per-session | Destroyed immediately after the final `.zip` is generated. |
| **Raw project files & generated code bundle** | Server storage | Retained **24 hours** post-completion to allow re-download/resume, then removed by an automated TTL cleanup job. |
| **Metadata & logs** (tokens used, generation duration, error logs) | Analytics store | Retained indefinitely in anonymized form; raw code/content is scrubbed before long-term retention. |

---

## 7. Technical Architecture Overview

- **Frontend**: Next.js/React + Monaco Editor; WebSocket/SSE client for live agent streams; state managed to reflect the current graph node.
- **Backend Orchestration**: LangGraph (Python, reference implementation) or `LangGraph.js` (if keeping orchestration native to the Next.js/Node stack), modeling the workflow as a `StateGraph`:
  - `ceo_node` → `human_approval_gate` → (conditional via `post_ceo_router`) → `dev_qa_node` → `security_node` → `END`
  - The conditional router supports three outcomes: **approve** (proceed to build), **request_changes** (loop back to `ceo_node` with appended notes and incremented `revision_count`), or **reject** (`END`).
  - Human-in-the-loop implemented as a genuine interrupt/checkpoint, resumed via an external API call carrying the approve / request_changes / reject signal.
  - **Single-gate strategy for v1**: only one structural HITL checkpoint (post-CEO, with unlimited revision loops). QA and Security phases run autonomously; their combined output is presented via the Diff Viewer (FR-5b) rather than a second blocking gate — preserving the "autonomous execution" feel while still giving the user full visibility before download. A second gate (post-QA) is reserved for v2 if user feedback shows it's needed.
- **Target generated-code language**: Python (v1). Enables deterministic, sandboxed static analysis via `ast`, `bandit`, and `flake8` for the QA and Security agents.
- **Execution Sandbox**: Docker containers or E2B for isolated code generation, test execution, and adversarial security probing.
- **Storage**: Session/workflow state persistence (for resumability), generated file storage, and final package storage (zip artifacts).

---

## 8. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Agents generate insecure code that the Security agent fails to catch | High | Treat Security agent output as advisory, not a guarantee; clearly label residual risks in the audit summary; do not claim "production-ready." |
| Long-running or abandoned sessions at the approval gate consume resources | Medium | Configurable session TTL / cleanup policy for idle paused sessions. |
| Sandbox escape or resource abuse during Security agent's adversarial testing | High | Strict container isolation, resource limits (CPU/memory/network), no host-reachable credentials. |
| Streaming disconnects cause user confusion about workflow state | Medium | Persist all streamed output server-side; reconnect logic backfills from last known state. |
| Scope creep — users expect brownfield/multi-repo support in v1 | Medium | Explicitly document out-of-scope items (Section 3.2) and communicate v1 boundaries clearly in-product. |

---

## 9. Decisions Log & Remaining Open Questions

### 9.1 Resolved (v1.1)

| Question | Decision |
|---|---|
| Target language(s) for generated code? | **Python only** for v1 — mature, deterministic static-analysis tooling (`ast`, `bandit`, `flake8`). Other languages deferred to v2+. |
| Backend agent framework? | **LangGraph (Python)** as reference, or **LangGraph.js** if orchestration should stay native to the Next.js/Node stack — team's choice. |
| Binary vs. multi-path approval gate? | **Three-way gate**: Approve / Request Changes (loops back to `ceo_node` with human notes + `revision_count`) / Reject. |
| Retention policy for generated code/session data? | Active state in Redis/PostgreSQL for session duration; sandbox destroyed immediately post-package; raw code retained **24h** then TTL-cleaned; anonymized metadata/logs retained indefinitely. See Section 6.1. |
| Single vs. multi-gate HITL strategy? | **Single gate (post-CEO)** for v1, with unlimited Request Changes revisions. QA/Security run autonomously; a **Diff Viewer** (Dev → QA → Security) gives visibility before download instead of a second blocking gate. Multi-gate reserved for v2. |

### 9.2 Still Open

- Should there be a soft cap or warning threshold on `revision_count` to surface possible loop fatigue to the user (see FR-16a)?
- Does the Diff Viewer need per-hunk accept/reject controls in v1, or is a read-only three-way diff sufficient before download?
- Should anonymized analytics (Section 6.1) be opt-out for users, or standard for all sessions?

---

## 10. Milestones (Proposed)

| Phase | Deliverable |
|---|---|
| M1 | LangGraph workflow skeleton with working human-in-the-loop interrupt/resume (no UI, API-driven). |
| M2 | Monaco-based IDE shell with streaming console tabs wired to a mock agent backend. |
| M3 | CEO agent integrated end-to-end: upload → critique → approval gate, with session persistence. |
| M4 | Developer + QA agents integrated with sandboxed execution; live file tree population. |
| M5 | Security agent integrated; SAST + patching + zip packaging complete. |
| M6 | Beta hardening: reconnect logic, session cleanup, audit summary polish. |

---

*End of document.*
