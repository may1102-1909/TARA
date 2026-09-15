# Strix Security Integration Rules for Antigravity IDE

- **Custom Command**: `run-strix-scan` executes the triple-layer security pipeline (Flake8, Bandit, and Strix) against active workspace code.
- **Environment**: Automatically inject `STRIX_LLM` and `LLM_API_KEY` into the execution context.
- **Automated Hardening**: Auto-generate patches using `ChatGoogleGenerativeAI`.
- **Interactive Patch Acceptance**: Users can accept proposed diffs via the "Accept Patch" UI button or `POST /api/security/apply-patch` to update workspace files dynamically.
