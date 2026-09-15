---
name: strix-security-scan
description: Autonomous SAST penetration testing and automated code hardening using Strix, Bandit, and Flake8 within TARA IDE.
---

# Strix Security Scan & Code Hardening

This skill enables Google Antigravity IDE and TARA agents to run autonomous penetration testing using **Strix** (`usestrix/strix`), static analysis with Bandit, and linting with Flake8.

## Usage & Commands

Run a security audit against the workspace:
```bash
python -m app.sandbox.strix_runner
```
Or via HTTP API:
```bash
curl -X POST http://127.0.0.1:8000/api/security/strix-scan
```

## How It Works

1. **Triple-Layer Scanning**:
   - **Flake8**: Code quality, syntax errors, and missing imports.
   - **Bandit**: AST analysis for Python security vulnerabilities.
   - **Strix**: Autonomous agentic penetration testing (`strix -n --target ./`).

2. **Unified Findings**:
   - Results are parsed into the unified `SecurityFindingModel` (`tool`, `severity`, `issue`, `file_path`, `line_number`).

3. **Automated AI Hardening**:
   - `ChatGoogleGenerativeAI` refactors affected modules and generates clean patches.
   - Diffs are streamed over `/ws/security` into Monaco Editor (`createDiffEditor`).
   - Approved patches can be applied with the "Accept Patch" action (`POST /api/security/apply-patch`).
