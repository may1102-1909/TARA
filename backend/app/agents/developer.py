"""Agent 2: Software Developer.

Turns the approved PRD and Architect Plan into a modular, PRD-specific multi-file application.
Differentiates between web applications (separate HTML/CSS/JS frontend + Python backend)
and non-web applications (modular Python packages, APIs, or CLI tools without forced frontend files).
Supports repair loops when receiving failure tracebacks and failing files from QA.
"""

import datetime
import html
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Ensure backend root is on sys.path for direct script execution
_backend_dir = str(Path(__file__).resolve().parent.parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.graph.state import AgentState
from app.core.config import settings
from app.core.llm import call_gemini_with_fallback
from app.agents.planner import _detect_web_requirement
from app.agents.skills_loader import load_skills, format_skills_for_prompt

logger = logging.getLogger(__name__)

# Initialize GenAI client if valid API key is present
try:
    from google import genai
    from google.genai import types
    _key = os.getenv("GEMINI_API_KEY", "") or settings.gemini_api_key
    if _key and _key.startswith("AIzaSy"):
        client = genai.Client(api_key=_key)
    else:
        client = None
except Exception:
    client = None


class GeneratedFile(BaseModel):
    path: str = Field(
        description="Safe project-relative path, e.g. 'main.py', 'cache.py', 'index.html', or 'static/styles.css'."
    )
    content: str = Field(
        description="Complete contents for this one file, with a clear responsibility and no placeholder implementation."
    )


class DeveloperCodeOutput(BaseModel):
    summary: str = Field(
        description="Briefly explain how the PRD requirements map to the generated files and implementation."
    )
    files: list[GeneratedFile] = Field(
        description="Complete, PRD-specific project files organized with separated responsibilities."
    )


DEVELOPER_SYSTEM_PROMPT = """You are TARA's senior product engineer. Implement the user's PRD and the Architect's Plan as a clean, complete, and coherent multi-file application.

Generation Rules:
1. Choose the simplest architecture that satisfies the PRD.
2. Give each file a clear, distinct responsibility. Keep related code together and avoid monolithic single-file applications.
3. Make files work together: imports, API routes, data structures, and asset paths must agree.
4. For Web Applications (when requires_web is True):
   - Generate separate frontend files: frontend/index.html (or index.html), frontend/styles.css (or static/styles.css), and frontend/app.js (or static/app.js).
   - Generate Python backend files (e.g. main.py with FastAPI) when the requirements need backend or API behavior. Serve index.html at / and mount static files.
   - Do not add buttons or controls that do nothing. Hook real interaction handlers in app.js.
5. For Non-Web Projects (when requires_web is False):
   - DO NOT force web files (no index.html, styles.css, or app.js).
   - Generate a clean modular Python codebase (e.g. main.py, domain logic file, models.py, utils.py).
6. Do not use generic app content or a canned project template unrelated to the PRD. Everything must be derived from the PRD requirements.
7. Do not return TODOs, placeholder implementations, or fake claims that tests passed.
8. Keep dependencies minimal. Include only packages the project actually needs.
9. Use safe relative file paths. Reject absolute paths and paths containing '..'.
10. If this is a repair attempt, carefully review the failing files and test output to fix the exact root causes of the failures.

Return complete file contents in a single JSON object matching DeveloperCodeOutput without markdown code fences."""


def _prompt(
    prd_content: str,
    human_notes: str = "",
    ceo_critique: Optional[Dict[str, Any]] = None,
    plan: Optional[Dict[str, Any]] = None,
    repair_context: Optional[Dict[str, Any]] = None,
    repair_count: int = 0,
) -> str:
    parts = [f"Approved PRD:\n{prd_content}"]

    if plan:
        plan_desc = f"""Architect Plan:
- Project Summary: {plan.get('project_summary', '')}
- Architecture Type: {plan.get('architecture_type', '')}
- Requires Web Frontend: {plan.get('requires_web', False)}
- File Plan:
"""
        for f in plan.get("file_plan", []):
            plan_desc += f"  * {f.get('path')}: {f.get('responsibility')}\n"
        plan_desc += "- Acceptance Criteria:\n"
        for ac in plan.get("acceptance_criteria", []):
            plan_desc += f"  * {ac}\n"
        parts.append(plan_desc)

        # Inject selected engineering skills
        selected_skills = plan.get("selected_skills", [])
        if selected_skills:
            loaded_skills = load_skills(selected_skills)
            if loaded_skills:
                parts.append(format_skills_for_prompt(loaded_skills))

    if ceo_critique:
        parts.append("CEO review guidance:\n" + str(ceo_critique))

    if human_notes:
        parts.append(f"User's implementation notes:\n{human_notes}")

    if repair_context and repair_count > 0:
        failing_files = repair_context.get("failing_files", [])
        test_out = repair_context.get("test_output", "")
        issues = repair_context.get("issues", [])
        repair_msg = f"""=== REPAIR ATTEMPT #{repair_count} ===
Previous QA verification failed. You MUST repair the code to fix these specific issues:
- Failing Files: {', '.join(failing_files) if failing_files else 'None specific'}
- Test Output / Traceback:\n{test_out}
- Identified QA Issues:\n"""
        for issue in issues:
            f_path = issue.get("file_path", "general")
            i_type = issue.get("issue_type", "Bug")
            desc = issue.get("description", "")
            repair_msg += f"  * [{f_path}] {i_type}: {desc}\n"
        parts.append(repair_msg)

    return "\n\n".join(parts)


def _validate_generated_files(output: DeveloperCodeOutput, requires_web: bool = False) -> DeveloperCodeOutput:
    """Validates safe relative paths and ensures required files exist without placeholders."""
    normalized: Dict[str, str] = {}
    if not output.files:
        raise ValueError("Developer output contains no files.")

    for generated_file in output.files:
        path = generated_file.path.replace("\\", "/").strip()
        parts = Path(path).parts
        if not path or path.startswith("/") or any(part in ("..", ".") for part in parts):
            raise ValueError(f"Unsafe generated file path: {generated_file.path}")
        if re.match(r"^[A-Za-z]:", path) or path.lower().endswith((".env", ".pem", ".key", ".token")):
            raise ValueError(f"Disallowed generated file path: {generated_file.path}")
        if path in normalized:
            raise ValueError(f"Duplicate generated file path: {path}")
        if not generated_file.content or not generated_file.content.strip():
            raise ValueError(f"Generated file is empty: {path}")
        normalized[path] = generated_file.content

    # If web app is requested, verify index.html or frontend/index.html is present
    if requires_web:
        has_html = (
            "index.html" in normalized
            or "frontend/index.html" in normalized
            or any(k.endswith("index.html") for k in normalized)
        )
        if not has_html:
            raise ValueError("Generated web project is missing required file: index.html or frontend/index.html")

    return output.model_copy(update={"files": [GeneratedFile(path=path, content=content) for path, content in normalized.items()]})


def call_ollama_qwen_coder(
    prd_content: str,
    human_notes: str = "",
    ceo_critique: Optional[Dict[str, Any]] = None,
    plan: Optional[Dict[str, Any]] = None,
    repair_context: Optional[Dict[str, Any]] = None,
    repair_count: int = 0,
    requires_web: bool = False,
) -> Optional[DeveloperCodeOutput]:
    """Queries local model qwen2.5-coder:7b to generate code with fast-fail connect timeout."""
    url = "http://localhost:11434/v1/chat/completions"
    model_name = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    user_prompt = _prompt(prd_content, human_notes, ceo_critique, plan, repair_context, repair_count)

    try:
        import httpx
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": DEVELOPER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        timeout_val = float(os.getenv("OLLAMA_CODEGEN_TIMEOUT_SECONDS", "5.0"))
        connect_val = float(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "1.5"))
        client_timeout = httpx.Timeout(timeout=timeout_val, connect=connect_val)

        with httpx.Client(timeout=client_timeout) as client_http:
            resp = client_http.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content_str = data["choices"][0]["message"]["content"]
                parsed = DeveloperCodeOutput.model_validate_json(content_str)
                if parsed.files:
                    parsed = _validate_generated_files(parsed, requires_web=requires_web)
                    logger.info("Successfully generated code using local model %s", model_name)
                    return parsed
    except Exception as exc:
        logger.debug("Local codegen notice (%s). Proceeding with alternative provider.", exc)
    return None


def call_gemini_codegen(
    prd_content: str,
    human_notes: str = "",
    ceo_critique: Optional[Dict[str, Any]] = None,
    plan: Optional[Dict[str, Any]] = None,
    repair_context: Optional[Dict[str, Any]] = None,
    repair_count: int = 0,
    requires_web: bool = False,
) -> Optional[DeveloperCodeOutput]:
    """Uses Google Gemini for code generation."""
    global client
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    if client is None and api_key and api_key.startswith("AIzaSy"):
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
        except Exception as exc:
            logger.warning("Could not initialize Gemini for developer: %s", exc)
            return None

    if client is None:
        return None

    try:
        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=DEVELOPER_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=DeveloperCodeOutput,
            temperature=0.2,
        )
        user_prompt = _prompt(prd_content, human_notes, ceo_critique, plan, repair_context, repair_count)
        response = call_gemini_with_fallback(
            client=client,
            contents=user_prompt,
            config=config,
            preferred_model=settings.default_model or "gemini-3.5-flash",
        )
        if response.parsed and isinstance(response.parsed, DeveloperCodeOutput):
            return _validate_generated_files(response.parsed, requires_web=requires_web)
        if response.text:
            parsed = DeveloperCodeOutput.model_validate_json(response.text)
            return _validate_generated_files(parsed, requires_web=requires_web)
    except Exception as exc:
        logger.warning("Gemini code generation notice: %s", exc)
    return None


def generate_code_fallback(
    prd_text: str = "",
    plan: Optional[Dict[str, Any]] = None,
    repair_context: Optional[Dict[str, Any]] = None,
) -> DeveloperCodeOutput:
    """Generates a complete, PRD-specific implementation derived from the PRD and plan.

    Clearly marks the output as a deterministic fallback so TARA and the user are aware.
    """
    title_match = re.search(r"(?im)^\s*#\s+(.+)$", prd_text or "")
    title = (title_match.group(1).strip() if title_match else "Autonomous Application")[:80]

    # Extract requirements
    requirements = []
    for line in (prd_text or "").splitlines():
        cleaned = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", line).strip()
        if cleaned and not line.lstrip().startswith("#") and len(cleaned) > 5:
            requirements.append(cleaned)
        if len(requirements) >= 6:
            break

    if not requirements:
        requirements = [f"Core functionality for {title}", "Robust input validation and error logging"]

    requires_web = bool(plan.get("requires_web", False)) if plan else _detect_web_requirement(prd_text)
    prd_lower = (prd_text or "").lower()

    files: Dict[str, str] = {}

    if requires_web:
        # Web Application: Separate frontend (HTML, CSS, JS) + FastAPI backend
        feature_items = "\n".join(f'        <li class="feature-item">{html.escape(req)}</li>' for req in requirements)
        use_frontend_dir = any(f.get("path", "").startswith("frontend/") for f in plan.get("file_plan", [])) if plan else True
        css_href = "styles.css" if use_frontend_dir else "/static/styles.css"
        js_src = "app.js" if use_frontend_dir else "/static/app.js"
        
        index_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{css_href}">
</head>
<body>
  <div class="app-container">
    <header class="app-header">
      <div class="fallback-banner" role="alert">
        <span class="badge">[FALLBACK - MODEL UNAVAILABLE]</span>
        <span>Deterministic PRD prototype for <strong>{html.escape(title)}</strong></span>
      </div>
      <h1 id="app-title">{html.escape(title)}</h1>
      <p class="subtitle">Autonomous system compiled by TARA</p>
    </header>

    <main class="main-content">
      <section class="card spec-card">
        <h2>Specifications & Features</h2>
        <ul id="features-list">
{feature_items}
        </ul>
      </section>

      <section class="card interactive-card">
        <h2>Interactive Console</h2>
        <form id="action-form" onsubmit="return false;">
          <div class="form-group">
            <label for="input-data">Payload / Input Parameter</label>
            <input type="text" id="input-data" placeholder="Enter test query or command..." required>
          </div>
          <div class="button-group">
            <button type="button" id="execute-btn" class="btn primary-btn">Execute Action</button>
            <button type="button" id="refresh-btn" class="btn secondary-btn">Check Status</button>
          </div>
        </form>
        <div id="status-panel" class="status-panel" aria-live="polite">
          <span class="status-label">System State:</span>
          <span id="status-text" class="status-value">Ready</span>
        </div>
        <pre id="output-console" class="output-console">Ready for user interaction.</pre>
      </section>
    </main>

    <footer class="app-footer">
      <p>TARA Engineering Agency · Automated Architecture</p>
    </footer>
  </div>
  <script src="{js_src}" defer></script>
</body>
</html>
"""
        styles_css = """/* Responsive Neobrutalist & Modern Stylesheet */
:root {
  --bg: #f8f9fa;
  --card-bg: #ffffff;
  --text: #212529;
  --primary: #0d6efd;
  --primary-hover: #0b5ed7;
  --border: #dee2e6;
  --radius: 8px;
  --font-sans: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background-color: var(--bg);
  color: var(--text);
  font-family: var(--font-sans);
  line-height: 1.6;
  padding: 24px;
}

.app-container {
  max-width: 900px;
  margin: 0 auto;
}

.fallback-banner {
  background: #fff3cd;
  color: #664d03;
  border: 1px solid #ffe69c;
  border-left: 4px solid #ffc107;
  padding: 8px 14px;
  border-radius: 4px;
  font-size: 0.9rem;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.fallback-banner .badge {
  background: #ffc107;
  color: #000;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 0.75rem;
}

.app-header {
  margin-bottom: 24px;
}

.app-header h1 {
  font-size: 1.85rem;
  font-weight: 700;
}

.subtitle {
  color: #6c757d;
  font-size: 0.95rem;
}

.main-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

@media (max-width: 768px) {
  .main-content { grid-template-columns: 1fr; }
}

.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.04);
}

.card h2 {
  font-size: 1.2rem;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}

.feature-item {
  margin-left: 20px;
  margin-bottom: 8px;
}

.form-group {
  margin-bottom: 14px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 600;
  font-size: 0.9rem;
}

.form-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.95rem;
}

.button-group {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.btn {
  padding: 9px 16px;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.primary-btn {
  background: var(--primary);
  color: #ffffff;
}

.primary-btn:hover { background: var(--primary-hover); }

.secondary-btn {
  background: #e9ecef;
  color: var(--text);
}

.secondary-btn:hover { background: #dee2e6; }

.status-panel {
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 6px;
  font-size: 0.85rem;
  margin-bottom: 12px;
}

.status-value {
  font-weight: 700;
  color: #198754;
}

.output-console {
  background: #212529;
  color: #f8f9fa;
  padding: 12px;
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  white-space: pre-wrap;
  min-height: 80px;
  max-height: 160px;
  overflow-y: auto;
}

.app-footer {
  text-align: center;
  color: #adb5bd;
  font-size: 0.85rem;
}
"""
        app_js = """// Client-side interactions for TARA PRD Web Prototype
document.addEventListener("DOMContentLoaded", () => {
  const executeBtn = document.getElementById("execute-btn");
  const refreshBtn = document.getElementById("refresh-btn");
  const inputData = document.getElementById("input-data");
  const statusText = document.getElementById("status-text");
  const outputConsole = document.getElementById("output-console");

  function log(message, data = null) {
    const timestamp = new Date().toLocaleTimeString();
    let text = `[${timestamp}] ${message}`;
    if (data) {
      text += "\\n" + JSON.stringify(data, null, 2);
    }
    outputConsole.textContent = text;
  }

  // Execute Action Button Handler
  executeBtn?.addEventListener("click", async () => {
    const query = inputData?.value?.trim() || "sample_payload";
    statusText.textContent = "Processing...";
    statusText.style.color = "#0d6efd";

    try {
      const response = await fetch("/api/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload: query }),
      });

      if (response.ok) {
        const result = await response.json();
        statusText.textContent = "Success";
        statusText.style.color = "#198754";
        log("Execution successful:", result);
      } else {
        throw new Error(`Server returned status ${response.status}`);
      }
    } catch (err) {
      // Graceful local simulation fallback if backend endpoint is unavailable
      statusText.textContent = "Active (Local)";
      statusText.style.color = "#198754";
      log(`Action executed locally for query: "${query}"`, {
        status: "success",
        processed_input: query,
        timestamp: new Date().toISOString()
      });
    }
  });

  // Status Refresh Button Handler
  refreshBtn?.addEventListener("click", async () => {
    statusText.textContent = "Checking...";
    try {
      const response = await fetch("/health");
      if (response.ok) {
        const data = await response.json();
        statusText.textContent = "Healthy";
        statusText.style.color = "#198754";
        log("Health check returned:", data);
        return;
      }
    } catch (e) {
      // Local fallback status
    }
    statusText.textContent = "Operational";
    statusText.style.color = "#198754";
    log("System operational. Client interactive components ready.");
  });
});
"""
        main_py = f'''"""FastAPI application entrypoint for {title}."""

from pathlib import Path
from typing import Any, Dict
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from models import ActionRequest, ActionResponse, HealthStatus
from utils import get_current_timestamp, format_status_response

app = FastAPI(
    title="{title}",
    description="Automated PRD application generated by TARA.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static assets if directory exists
static_dir = Path(__file__).resolve().parent / "static"
frontend_dir = Path(__file__).resolve().parent / "frontend"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir)), name="frontend")


@app.get("/", tags=["UI"])
def serve_index() -> FileResponse:
    """Serves the main application HTML interface."""
    for cand in [
        Path(__file__).resolve().parent / "frontend" / "index.html",
        Path(__file__).resolve().parent / "index.html",
    ]:
        if cand.exists():
            return FileResponse(cand)
    raise HTTPException(status_code=404, detail="index.html not found.")


@app.get("/{{filename:path}}", include_in_schema=False)
def serve_asset(filename: str) -> FileResponse:
    """Serves static assets across frontend, static, or root directories."""
    for folder in [
        Path(__file__).resolve().parent / "frontend",
        Path(__file__).resolve().parent / "static",
        Path(__file__).resolve().parent,
    ]:
        target = (folder / filename).resolve()
        if target.is_file():
            return FileResponse(target)
    raise HTTPException(status_code=404, detail="Asset not found.")


@app.get("/health", response_model=HealthStatus, tags=["System"])
def health_check() -> HealthStatus:
    """Health check endpoint confirming application liveness."""
    return HealthStatus(
        status="healthy",
        service="{title}",
        timestamp=get_current_timestamp()
    )


@app.post("/api/execute", response_model=ActionResponse, status_code=status.HTTP_200_OK, tags=["Operations"])
def execute_action(request: ActionRequest) -> ActionResponse:
    """Executes a domain operation requested from the user interface."""
    if not request.payload.strip():
        raise HTTPException(status_code=400, detail="Payload must not be empty.")
    
    processed = format_status_response(request.payload)
    return ActionResponse(
        status="success",
        result=processed,
        timestamp=get_current_timestamp()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
'''
        models_py = '''"""Data models and validation schemas for the application."""

from typing import Any, Dict
from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    status: str
    service: str
    timestamp: str


class ActionRequest(BaseModel):
    payload: str = Field(..., min_length=1, description="Input string or query")


class ActionResponse(BaseModel):
    status: str
    result: Dict[str, Any]
    timestamp: str
'''
        utils_py = '''"""Utility routines and helper functions."""

from datetime import datetime, timezone
from typing import Any, Dict


def get_current_timestamp() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def format_status_response(payload: str) -> Dict[str, Any]:
    """Formats processed response dictionary for API consumer."""
    return {
        "processed_length": len(payload),
        "echo": payload,
        "mode": "deterministic_execution",
    }
'''
        if use_frontend_dir:
            files["frontend/index.html"] = index_html
            files["frontend/styles.css"] = styles_css
            files["frontend/app.js"] = app_js
        else:
            files["index.html"] = index_html
            files["static/styles.css"] = styles_css
            files["static/app.js"] = app_js

        files["main.py"] = main_py
        files["models.py"] = models_py
        files["utils.py"] = utils_py

    else:
        # Non-Web Application: Modular Python codebase without forcing web files
        if "cache" in prd_lower:
            main_py = '''"""FastAPI In-Memory Distributed Cache Microservice generated by TARA Developer Agent."""

import time
import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
import uvicorn
from cache import CacheStore, InProcessTTLCache

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tara_cache_service")

app = FastAPI(
    title="TARA In-Memory Distributed Cache Microservice",
    description="High-throughput in-memory caching microservice with TTL expiration and metrics telemetry.",
    version="1.0.0",
)

store = CacheStore()


class CacheSetRequest(BaseModel):
    key: str = Field(..., min_length=1, description="Unique cache key", example="user:101:profile")
    value: Any = Field(..., description="Arbitrary JSON payload or primitive value to store", example={"name": "Alice", "role": "admin"})
    ttl: Optional[int] = Field(None, ge=1, description="Optional time-to-live in seconds", example=120)


class CacheGetResponse(BaseModel):
    key: str
    value: Optional[Any] = None
    found: bool
    expires_in_seconds: Optional[float] = None


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, Any]:
    """Health check endpoint providing service liveness and store size."""
    return {
        "status": "ok",
        "service": "cache-microservice",
        "keys_cached": store.size(),
        "timestamp": time.time(),
    }


@app.post("/cache/set", status_code=status.HTTP_201_CREATED, tags=["Cache Operations"])
def set_cache(req: CacheSetRequest) -> Dict[str, Any]:
    """Sets a key-value pair in cache with optional TTL."""
    store.set(req.key, req.value, req.ttl)
    logger.info("Cached key: %s with TTL: %s", req.key, req.ttl)
    return {"status": "success", "key": req.key, "ttl": req.ttl, "created_at": time.time()}


@app.get("/cache/get/{key}", response_model=CacheGetResponse, tags=["Cache Operations"])
def get_cache(key: str) -> CacheGetResponse:
    """Retrieves a cached value by key, checking TTL expiry."""
    val, found, rem = store.get_with_expiry(key)
    return CacheGetResponse(key=key, value=val, found=found, expires_in_seconds=rem)


@app.get("/cache/keys", tags=["Cache Operations"])
def list_keys() -> Dict[str, Any]:
    """Lists all active, non-expired keys currently in the cache."""
    active = store.active_keys()
    return {"keys": active, "total_active": len(active)}


@app.get("/cache/metrics", tags=["Telemetry"])
def cache_metrics() -> Dict[str, Any]:
    """Returns runtime telemetry: hits, misses, sets, and eviction counts."""
    return {
        "metrics": store.get_metrics(),
        "total_keys": store.size(),
        "timestamp": time.time(),
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
'''
            cache_py = '''"""In-memory cache storage implementation."""
import time
from typing import Any, Dict, List, Optional, Tuple

class InProcessTTLCache:
    def __init__(self, default_ttl: float = 300.0):
        self.default_ttl = default_ttl
        self._store: Dict[str, Tuple[Any, Optional[float]]] = {}
        self._metrics: Dict[str, int] = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "evictions": 0}

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        actual_ttl = ttl if ttl is not None else self.default_ttl
        expiry = (time.time() + actual_ttl) if actual_ttl and actual_ttl > 0 else None
        self._store[key] = (value, expiry)
        self._metrics["sets"] += 1
        return True

    def get(self, key: str) -> Optional[Any]:
        val, found, _ = self.get_with_expiry(key)
        return val if found else None

    def get_with_expiry(self, key: str) -> Tuple[Optional[Any], bool, Optional[float]]:
        now = time.time()
        if key in self._store:
            val, expiry = self._store[key]
            if expiry and now > expiry:
                del self._store[key]
                self._metrics["misses"] += 1
                self._metrics["evictions"] += 1
                return None, False, 0.0
            self._metrics["hits"] += 1
            rem = (expiry - now) if expiry else None
            return val, True, rem
        self._metrics["misses"] += 1
        return None, False, None

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            self._metrics["deletes"] += 1
            return True
        return False

    def active_keys(self) -> List[str]:
        now = time.time()
        return [k for k, (_, exp) in list(self._store.items()) if not exp or exp > now]

    def get_metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    def size(self) -> int:
        return len(self._store)

CacheStore = InProcessTTLCache
'''
            models_py = '''"""Data schemas for Cache Service."""
from typing import Any, Optional
from pydantic import BaseModel, Field

class CacheSetRequest(BaseModel):
    key: str = Field(..., min_length=1)
    value: Any
    ttl: Optional[int] = 300

class CacheGetResponse(BaseModel):
    key: str
    value: Optional[Any] = None
    found: bool
    expires_in_seconds: Optional[float] = None
'''
            utils_py = '''"""Utility routines and time helpers."""
import time
from datetime import datetime, timezone

def get_current_timestamp() -> float:
    return time.time()
'''
            files["main.py"] = main_py
            files["cache.py"] = cache_py
            files["models.py"] = models_py
            files["utils.py"] = utils_py

        elif "auth" in prd_lower or "token" in prd_lower:
            main_py = '''"""FastAPI Authentication and Rate Limiting Microservice."""

import time
import secrets
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tara_auth_service")

app = FastAPI(
    title="TARA Authentication & Rate Limiting Microservice",
    description="Stateless token issuance, session verification, and sliding window rate limiting.",
    version="1.0.0",
)

_active_tokens: Dict[str, Dict[str, Any]] = {}
_request_windows: Dict[str, List[float]] = {}
MAX_REQUESTS_PER_MINUTE = 60


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    role: Optional[str] = "developer"


class VerifyRequest(BaseModel):
    token: str = Field(..., min_length=10)


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, Any]:
    return {"status": "ok", "service": "auth-microservice", "timestamp": time.time()}


@app.post("/auth/token", status_code=status.HTTP_201_CREATED, tags=["Authentication"])
def issue_token(req: LoginRequest) -> Dict[str, Any]:
    token = f"tara_sec_{secrets.token_hex(20)}"
    claims = {
        "sub": req.username,
        "username": req.username,
        "role": req.role,
        "issued_at": time.time(),
        "expires_at": time.time() + 3600,
    }
    _active_tokens[token] = claims
    logger.info("Issued token for user %s with role %s", req.username, req.role)
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600, "claims": claims}


@app.post("/auth/verify", tags=["Authentication"])
def verify_token(req: VerifyRequest) -> Dict[str, Any]:
    if req.token not in _active_tokens:
        raise HTTPException(status_code=401, detail="Invalid token.")
    claims = _active_tokens[req.token]
    if time.time() > claims["expires_at"]:
        del _active_tokens[req.token]
        raise HTTPException(status_code=401, detail="Token has expired.")
    return {"valid": True, "claims": claims}


@app.post("/auth/revoke", tags=["Authentication"])
def revoke_token(req: VerifyRequest) -> Dict[str, Any]:
    if req.token in _active_tokens:
        del _active_tokens[req.token]
        return {"status": "revoked", "token": req.token}
    raise HTTPException(status_code=404, detail="Token not found.")


@app.get("/rate-limit/status", tags=["Rate Limiting"])
def rate_limit_status(client_id: str = "default_client") -> Dict[str, Any]:
    now = time.time()
    history = [t for t in _request_windows.get(client_id, []) if now - t < 60.0]
    history.append(now)
    _request_windows[client_id] = history
    remaining = max(0, MAX_REQUESTS_PER_MINUTE - len(history))
    return {
        "client_id": client_id,
        "limit_per_minute": MAX_REQUESTS_PER_MINUTE,
        "current_usage": len(history),
        "remaining_quota": remaining,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
'''
            models_py = '''"""Authentication schemas."""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "developer"

class VerifyRequest(BaseModel):
    token: str
'''
            utils_py = '''"""Auth utility helpers."""
import secrets

def generate_salt() -> str:
    return secrets.token_hex(16)
'''
            files["main.py"] = main_py
            files["models.py"] = models_py
            files["utils.py"] = utils_py

        else:
            main_py = '''"""FastAPI General Service Application generated by TARA Developer Agent."""

import time
import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tara_service")

app = FastAPI(
    title="TARA Microservice Application",
    description="Operational FastAPI REST microservice generated by TARA Multi-Agent Framework.",
    version="1.0.0",
)

_items_db: Dict[str, Dict[str, Any]] = {}


class ItemCreateRequest(BaseModel):
    name: str = Field(..., example="Primary Service Config")
    description: Optional[str] = Field(None, example="Configuration and telemetry entity")
    payload: Dict[str, Any] = Field(default_factory=dict, example={"status": "enabled", "workers": 4})


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "tara-microservice",
        "items_count": len(_items_db),
        "timestamp": time.time(),
    }


@app.post("/api/items", status_code=status.HTTP_201_CREATED, tags=["Items"])
def create_item(item: ItemCreateRequest) -> Dict[str, Any]:
    """Creates a new record in the service store."""
    item_id = str(len(_items_db) + 1)
    record = {
        "id": item_id,
        "name": item.name,
        "description": item.description,
        "payload": item.payload,
        "created_at": time.time(),
    }
    _items_db[item_id] = record
    return {"status": "created", "item": record}


@app.get("/api/items", tags=["Items"])
def list_items() -> Dict[str, Any]:
    """Lists all stored items."""
    return {"items": list(_items_db.values()), "total": len(_items_db)}


@app.get("/api/items/{item_id}", tags=["Items"])
def get_item(item_id: str) -> Dict[str, Any]:
    """Retrieves an item by identifier."""
    if item_id in _items_db:
        return _items_db[item_id]
    raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found.")


@app.get("/api/metrics", tags=["Telemetry"])
def get_metrics() -> Dict[str, Any]:
    """Returns application metrics and inventory."""
    return {
        "active_items": len(_items_db),
        "status": "healthy",
        "timestamp": time.time(),
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
'''
            models_py = '''"""Data models generated by TARA Developer Agent."""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ItemCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
'''
            utils_py = '''"""Utility routines and helpers."""
from datetime import datetime, timezone

def get_current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
'''
            files["main.py"] = main_py
            files["models.py"] = models_py
            files["utils.py"] = utils_py

    summary = f"[FALLBACK - MODEL UNAVAILABLE] PRD-derived implementation for: {title}"
    return DeveloperCodeOutput(
        summary=summary,
        files=[GeneratedFile(path=path, content=content) for path, content in files.items()]
    )


def generate_code_from_prd(
    prd_content: str = "",
    human_notes: str = "",
    ceo_critique: Optional[Dict[str, Any]] = None,
    plan: Optional[Dict[str, Any]] = None,
    repair_context: Optional[Dict[str, Any]] = None,
    repair_count: int = 0,
    *args,
    **kwargs,
) -> DeveloperCodeOutput:
    """Generates a PRD-specific project, preferring local coding model, falling back to cloud or deterministic fallback."""
    actual_prd = prd_content or (args[0] if args else "") or kwargs.get("prd", "") or kwargs.get("prd_text", "")
    requires_web = bool(plan.get("requires_web", False)) if plan else _detect_web_requirement(actual_prd)

    ollama_output = call_ollama_qwen_coder(
        prd_content=actual_prd,
        human_notes=human_notes,
        ceo_critique=ceo_critique,
        plan=plan,
        repair_context=repair_context,
        repair_count=repair_count,
        requires_web=requires_web,
    )
    if ollama_output is not None:
        return ollama_output

    gemini_output = call_gemini_codegen(
        prd_content=actual_prd,
        human_notes=human_notes,
        ceo_critique=ceo_critique,
        plan=plan,
        repair_context=repair_context,
        repair_count=repair_count,
        requires_web=requires_web,
    )
    if gemini_output is not None:
        return gemini_output

    logger.warning("Local and cloud code models are unavailable; using PRD-derived deterministic fallback.")
    return generate_code_fallback(actual_prd, plan=plan, repair_context=repair_context)


def developer_node(state: AgentState) -> Dict[str, Any]:
    """Developer Node executing dynamic code generation and repair iterations."""
    prd_text = state.get("prd_text", "")
    notes = state.get("human_feedback_notes", [])
    notes_str = "\n".join(notes) if notes else ""
    ceo_critique = state.get("ceo_critique")
    plan = state.get("plan")
    repair_context = state.get("qa_repair_context")
    repair_count = state.get("repair_count", 0)

    is_repair = bool(repair_context)
    if is_repair:
        repair_count += 1
        logger.info("Developer executing repair attempt #%d", repair_count)

    requires_web = bool(plan.get("requires_web", False)) if plan else _detect_web_requirement(prd_text)

    try:
        code_output: DeveloperCodeOutput = generate_code_from_prd(
            prd_text,
            notes_str,
            ceo_critique,
            plan,
            repair_context,
            repair_count,
        )
        code_output = _validate_generated_files(code_output, requires_web=requires_web)
        generated_files = {f.path: f.content for f in code_output.files}
        summary = code_output.summary
    except Exception as exc:
        logger.exception("Developer code generation exception; utilizing PRD fallback: %s", exc)
        code_output = generate_code_fallback(prd_text, plan=plan, repair_context=repair_context)
        code_output = _validate_generated_files(code_output, requires_web=requires_web)
        generated_files = {f.path: f.content for f in code_output.files}
        summary = code_output.summary

    log_stage = f"repair_attempt_{repair_count}" if is_repair else "code_generation"
    prefix = f"[Repair #{repair_count}] " if is_repair else ""
    log_msg = f"{prefix}{summary} Files: {', '.join(generated_files.keys())}"

    log_entry = {
        "agent": "Developer",
        "stage": log_stage,
        "message": log_msg,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repair_count": repair_count,
        "files": list(generated_files.keys()),
    }

    # Trigger Live App Preview hot-reload broadcast
    try:
        from app.routers.preview import broadcast_preview_reload_sync
        target_f = "index.html" if "index.html" in generated_files else "main.py"
        broadcast_preview_reload_sync(
            files=generated_files,
            target_file=target_f,
            trigger="developer_agent",
        )
    except Exception as e:
        logger.debug("Preview hot-reload broadcast notice in developer_node: %s", e)

    return {
        "dev_code_files": generated_files,
        "generated_code": generated_files,
        "code_summary": summary,
        "repair_count": repair_count,
        "current_stage": "code_generated" if not is_repair else f"code_repaired_attempt_{repair_count}",
        "logs": [log_entry],
    }


if __name__ == "__main__":
    sample_prd = """
    # PRD: Intelligent Cache Service
    Build a high-performance in-memory caching service in Python.
    Requirements:
    - Store key-value pairs with TTL.
    - Provide cleanup mechanism for expired entries.
    - Include robust error handling and logging.
    """

    result = generate_code_from_prd(sample_prd)
    print(f"Summary: {result.summary}\n")
    for f in result.files:
        print(f"--- File: {f.path} ---")
        print(f.content[:150])
        print("\n")
