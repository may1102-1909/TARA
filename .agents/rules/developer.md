# TARA Developer Agent Rule

When editing or generating code inside `backend/app/agents/developer.py` or handling code-gen tasks:
Act as a Senior Developer. Read the following PRD and generate a complete single-file FastAPI service with WebSockets.
1. Always use the local model `qwen2.5-coder:7b` located at `http://localhost:11434/v1`.
2. Ensure generated code is complete (no placeholders like `# TODO` or `// implement later`).
3. Enforce multi-file JSON outputs matching the `DeveloperCodeOutput` schema (containing `summary` and `files` with `path` and `content`).
4. Handle exceptions cleanly and maintain modular architecture across backend routes and UI components.             Act as a Senior Developer. Read the following PRD and generate a complete single-file FastAPI service with WebSockets.

### PRD Specification:
- Title: Live Real-Time Code Streaming API
- Endpoint 1: POST /api/prd - Accepts a JSON body with { "prd_title": string, "description": string } and returns a generated task ID.
- Endpoint 2: WebSocket /ws/stream/{task_id} - Streams mock code generation tokens every 100ms back to the client as JSON: { "type": "CODE_DELTA", "delta": string }.
- Requirements: Include standard CORS middleware, typed Pydantic request models, and mock streaming logic. Do not leave any placeholders or TODOs.
