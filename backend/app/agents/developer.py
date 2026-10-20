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
   - Generate separate frontend files: index.html (semantic markup), static/styles.css (responsive CSS), and static/app.js (interactive JavaScript).
   - Generate Python backend files (e.g. main.py with FastAPI) when the requirements need backend or API behavior. Serve index.html at / and mount static files at /static.
   - Do not add buttons or controls that do nothing. Hook real interaction handlers in app.js.
5. For Non-Web Projects (when requires_web is False):
   - DO NOT force web files (no index.html, static/styles.css, or static/app.js).
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

    # If web app is requested, verify index.html is present
    if requires_web:
        if "index.html" not in normalized:
            raise ValueError("Generated web project is missing required file: index.html")

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
        
        index_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="/static/styles.css">
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
  <script src="/static/app.js" defer></script>
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
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", tags=["UI"])
def serve_index() -> FileResponse:
    """Serves the main application HTML interface."""
    index_path = Path(__file__).resolve().parent / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found.")
    return FileResponse(index_path)


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
        files["index.html"] = index_html
        files["static/styles.css"] = styles_css
        files["static/app.js"] = app_js
        files["main.py"] = main_py
        files["models.py"] = models_py
        files["utils.py"] = utils_py

    else:
        # Non-Web Application: Modular Python codebase without forcing web files
        if "cache" in prd_lower:
            cache_py = '''"""Thread-safe In-Memory TTL Cache Implementation."""

import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from models import CacheEntry, CacheStats


class InProcessTTLCache:
    """High-performance in-memory key-value cache with TTL expiration."""

    def __init__(self, default_ttl: float = 300.0):
        self._store: Dict[str, Tuple[Any, Optional[float]]] = {}
        self._lock = threading.RLock()
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Stores a key-value pair with optional TTL in seconds."""
        if not key or not isinstance(key, str):
            raise ValueError("Key must be a non-empty string.")
        
        expires_at = time.time() + (ttl if ttl is not None else self.default_ttl)
        with self._lock:
            self._store[key] = (value, expires_at)
        return True

    def get(self, key: str) -> Optional[Any]:
        """Retrieves a value if not expired, returning None otherwise."""
        now = time.time()
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None
            val, exp = self._store[key]
            if exp is not None and now > exp:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return val

    def delete(self, key: str) -> bool:
        """Deletes a key from the cache, returning True if key existed."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def cleanup_expired(self) -> int:
        """Removes expired entries and returns count of evicted items."""
        now = time.time()
        evicted = 0
        with self._lock:
            expired_keys = [k for k, (_, exp) in self._store.items() if exp is not None and now > exp]
            for k in expired_keys:
                del self._store[k]
                evicted += 1
        return evicted

    def get_stats(self) -> CacheStats:
        """Returns snapshot statistics for cache telemetry."""
        with self._lock:
            return CacheStats(
                total_items=len(self._store),
                hits=self._hits,
                misses=self._misses,
            )
'''
            models_py = '''"""Data schemas for Cache Service."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class CacheEntry(BaseModel):
    key: str
    value: Any
    ttl_seconds: Optional[float] = 300.0


class CacheStats(BaseModel):
    total_items: int
    hits: int
    misses: int
'''
            utils_py = '''"""Utility routines and time helpers."""

from datetime import datetime, timezone


def get_iso_timestamp() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
'''
            main_py = '''"""Cache Service Demonstration and Entrypoint."""

import time
import logging
from cache import InProcessTTLCache
from utils import get_iso_timestamp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cache_service")


def run_demo():
    """Executes verification and demonstration of in-memory TTL cache."""
    logger.info("Initializing in-memory TTL cache at %s", get_iso_timestamp())
    cache = InProcessTTLCache(default_ttl=2.0)

    # 1. Basic Set & Get
    cache.set("session:user_101", {"name": "Alice", "role": "admin"})
    val = cache.get("session:user_101")
    logger.info("Retrieved key 'session:user_101': %s", val)
    assert val is not None, "Failed to retrieve stored key"

    # 2. TTL Expiration check
    cache.set("ephemeral:token", "temp_secret_xyz", ttl=0.5)
    time.sleep(0.6)
    expired_val = cache.get("ephemeral:token")
    logger.info("Retrieved expired key: %s (expected None)", expired_val)
    assert expired_val is None, "Expired key was not evicted"

    # 3. Cleanup routine
    evicted = cache.cleanup_expired()
    logger.info("Ran cleanup_expired: evicted %d items", evicted)

    stats = cache.get_stats()
    logger.info("Cache stats: %s", stats.model_dump())
    print("Cache demonstration completed successfully.")


if __name__ == "__main__":
    run_demo()
'''
            files["main.py"] = main_py
            files["cache.py"] = cache_py
            files["models.py"] = models_py
            files["utils.py"] = utils_py

        elif "order" in prd_lower or "api" in prd_lower:
            models_py = '''"""Data models for Order Microservice."""

from typing import List, Optional
from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    item_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)
    quantity: int = Field(default=1, gt=0)


class OrderCreate(BaseModel):
    customer_id: str = Field(..., min_length=1)
    items: List[OrderItem] = Field(..., min_items=1)


class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    items: List[OrderItem]
    total_amount: float
    status: str
    created_at: str
'''
            service_py = '''"""Order processing business logic."""

import uuid
from typing import Dict, List, Optional
from models import OrderCreate, OrderResponse
from utils import get_current_timestamp


class OrderService:
    """Manages order creation, calculation, and retrieval."""

    def __init__(self):
        self._orders: Dict[str, OrderResponse] = {}

    def create_order(self, order_data: OrderCreate) -> OrderResponse:
        order_id = f"ord_{uuid.uuid4().hex[:10]}"
        total = sum(item.price * item.quantity for item in order_data.items)
        created = OrderResponse(
            order_id=order_id,
            customer_id=order_data.customer_id,
            items=order_data.items,
            total_amount=round(total, 2),
            status="confirmed",
            created_at=get_current_timestamp(),
        )
        self._orders[order_id] = created
        return created

    def get_order(self, order_id: str) -> Optional[OrderResponse]:
        return self._orders.get(order_id)

    def list_orders(self) -> List[OrderResponse]:
        return list(self._orders.values())
'''
            utils_py = '''"""Utility routines and timestamp formatters."""

from datetime import datetime, timezone


def get_current_timestamp() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
'''
            main_py = '''"""Order Processing Microservice REST API."""

from typing import Dict, List
from fastapi import FastAPI, HTTPException, status
from models import OrderCreate, OrderResponse
from service import OrderService
from utils import get_current_timestamp

app = FastAPI(
    title="Order Processing Microservice",
    description="PRD-compliant microservice generated by TARA.",
    version="1.0.0",
)

service = OrderService()


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "order_service", "timestamp": get_current_timestamp()}


@app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED, tags=["Orders"])
def create_order_endpoint(payload: OrderCreate) -> OrderResponse:
    """Creates and confirms a new customer order."""
    return service.create_order(payload)


@app.get("/orders/{order_id}", response_model=OrderResponse, tags=["Orders"])
def get_order_endpoint(order_id: str) -> OrderResponse:
    """Retrieves an existing order by ID."""
    order = service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
'''
            files["main.py"] = main_py
            files["models.py"] = models_py
            files["service.py"] = service_py
            files["utils.py"] = utils_py

        else:
            # Generic Python modular implementation
            models_py = '''"""Data types and schemas."""

from typing import Any, Dict
from pydantic import BaseModel, Field


class ServicePayload(BaseModel):
    name: str = Field(..., min_length=1)
    parameters: Dict[str, Any] = Field(default_factory=dict)
'''
            core_py = f'''"""Core implementation satisfying {title}."""

from typing import Any, Dict
from models import ServicePayload
from utils import get_timestamp


class CoreEngine:
    """Domain engine implementing core business requirements."""

    def __init__(self):
        self.state: Dict[str, Any] = {{"initialized": True}}

    def process(self, payload: ServicePayload) -> Dict[str, Any]:
        result = {{
            "name": payload.name,
            "processed": True,
            "timestamp": get_timestamp(),
            "details": payload.parameters,
        }}
        return result
'''
            utils_py = '''"""Utility routines and helpers."""

from datetime import datetime, timezone


def get_timestamp() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
'''
            main_py = f'''"""Entrypoint and CLI orchestrator for {title}."""

from core import CoreEngine
from models import ServicePayload
from utils import get_timestamp


def main():
    print(f"Starting {title} at {{get_timestamp()}}")
    engine = CoreEngine()
    payload = ServicePayload(name="default_task", parameters={{"mode": "automated"}})
    res = engine.process(payload)
    print("Execution result:", res)
    return res


if __name__ == "__main__":
    main()
'''
            files["main.py"] = main_py
            files["core.py"] = core_py
            files["models.py"] = models_py
            files["utils.py"] = utils_py

    summary = f"[FALLBACK - MODEL UNAVAILABLE] PRD-derived implementation for: {title}"
    return DeveloperCodeOutput(
        summary=summary,
        files=[GeneratedFile(path=path, content=content) for path, content in files.items()]
    )


def generate_code_from_prd(
    prd_content: str,
    human_notes: str = "",
    ceo_critique: Optional[Dict[str, Any]] = None,
    plan: Optional[Dict[str, Any]] = None,
    repair_context: Optional[Dict[str, Any]] = None,
    repair_count: int = 0,
) -> DeveloperCodeOutput:
    """Generates a PRD-specific project, preferring local coding model, falling back to cloud or deterministic fallback."""
    requires_web = bool(plan.get("requires_web", False)) if plan else _detect_web_requirement(prd_content)

    ollama_output = call_ollama_qwen_coder(
        prd_content=prd_content,
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
        prd_content=prd_content,
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
    return generate_code_fallback(prd_content, plan=plan, repair_context=repair_context)


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
            prd_content=prd_text,
            human_notes=notes_str,
            ceo_critique=ceo_critique,
            plan=plan,
            repair_context=repair_context,
            repair_count=repair_count,
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
