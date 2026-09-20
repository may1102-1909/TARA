"""Tiered Sandbox Runner for Isolated Execution, SAST Analysis, and Code Execution.

Supports three tiers:
1. E2B Sandbox (Cloud MicroVMs if E2B_API_KEY is configured)
2. Docker Sandbox (Local isolated container if Docker daemon is active)
3. Local Ephemeral Sandbox (Temporary isolated directory with environment scrubbing and timeout limits)
"""

import abc
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    sandbox_tier: str


class BaseSandbox(abc.ABC):
    """Abstract interface for sandboxed workspace execution."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.tier_name = "base"

    @abc.abstractmethod
    def write_files(self, files: Dict[str, str]) -> None:
        """Writes given files into the isolated sandbox environment."""
        pass

    @abc.abstractmethod
    def read_files(self) -> Dict[str, str]:
        """Reads all files currently inside the sandbox environment."""
        pass

    @abc.abstractmethod
    def run_command(
        self,
        cmd: List[str],
        timeout: int = 30,
        envs: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Executes a command inside the sandbox."""
        pass

    def start_server(self, entrypoint: Optional[str] = None, port: Optional[int] = None) -> int:
        """Starts a background server process inside the sandbox and returns allocated port."""
        raise NotImplementedError

    def stop_server(self) -> None:
        """Stops the running background server process."""
        pass

    def restart_server(self, entrypoint: Optional[str] = None) -> int:
        """Restarts the running background server process."""
        self.stop_server()
        return self.start_server(entrypoint=entrypoint)

    def get_server_port(self) -> Optional[int]:
        return getattr(self, "server_port", None)

    def is_server_alive(self) -> bool:
        port = self.get_server_port()
        if not port:
            return False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.4)
                return s.connect_ex(('127.0.0.1', port)) == 0
        except Exception:
            return False

    def discover_openapi_routes(self) -> List[Dict[str, Any]]:
        """Queries the running server for live OpenAPI paths or extracts decorators."""
        return []

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Destroys and cleans up the sandbox resources."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


def get_free_port() -> int:
    """Finds an unused localhost port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class LocalEphemeralSandbox(BaseSandbox):
    """Tier 3: Local isolated temporary directory with timeout guards and env sanitization."""

    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.tier_name = "LocalEphemeralSandbox"
        self.temp_dir = tempfile.mkdtemp(prefix=f"tara_sandbox_{session_id[:8]}_")
        self.root_path = Path(self.temp_dir).resolve()
        self.server_proc: Optional[subprocess.Popen] = None
        self.server_port: Optional[int] = None
        self.active_entrypoint: Optional[str] = None

    def write_files(self, files: Dict[str, str]) -> None:
        for rel_path, content in files.items():
            # Prevent path traversal attacks
            target = (self.root_path / rel_path).resolve()
            if not str(target).startswith(str(self.root_path)):
                raise ValueError(f"Illegal path traversal attempt: {rel_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def read_files(self) -> Dict[str, str]:
        result = {}
        if not self.root_path.exists():
            return result
        for file_path in self.root_path.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(self.root_path).as_posix()
                # Skip pycache and hidden files
                if "__pycache__" in rel_path or rel_path.startswith("."):
                    continue
                try:
                    result[rel_path] = file_path.read_text(encoding="utf-8")
                except Exception:
                    pass
        return result

    def run_command(
        self,
        cmd: List[str],
        timeout: int = 30,
        envs: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        # Build sanitized environment (prevent leaking host API keys into sandbox processes)
        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "PYTHONPATH": str(self.root_path),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        # Retain necessary system paths for Python
        for k in ("TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "COMSPEC", "PATHEXT"):
            if k in os.environ:
                clean_env[k] = os.environ[k]

        # Inject forwarded sandbox environment variables (e.g. STRIX_LLM, LLM_API_KEY)
        if envs:
            clean_env.update(envs)

        # Use the current Python interpreter if 'python', 'flake8', or 'bandit' is invoked
        formatted_cmd = []
        for i, part in enumerate(cmd):
            if i == 0 and part in ("python", "python3"):
                formatted_cmd.append(sys.executable)
            elif i == 0 and part in ("flake8", "bandit"):
                # Run as python -m tool to avoid Windows PATH issues
                formatted_cmd.extend([sys.executable, "-m", part])
            elif i == 0 and part == "strix":
                # Strix command: check if strix is in PATH or can be invoked
                strix_path = shutil.which("strix")
                if strix_path:
                    formatted_cmd.append(strix_path)
                else:
                    formatted_cmd.append("strix")
            else:
                formatted_cmd.append(part)

        start_time = time.time()
        try:
            proc = subprocess.run(
                formatted_cmd,
                cwd=str(self.root_path),
                env=clean_env,
                input="",
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False
            )
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration_ms=round(duration, 2),
                sandbox_tier=self.tier_name
            )
        except subprocess.TimeoutExpired:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                stdout="",
                stderr=f"Execution timed out after {timeout} seconds.",
                exit_code=-1,
                duration_ms=round(duration, 2),
                sandbox_tier=self.tier_name
            )
        except Exception as exc:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                stdout="",
                stderr=f"Sandbox execution error: {exc}",
                exit_code=1,
                duration_ms=round(duration, 2),
                sandbox_tier=self.tier_name
            )

    def start_server(self, entrypoint: Optional[str] = None, port: Optional[int] = None) -> int:
        """Launches the generated app inside the sandbox on an isolated port and waits until responsive."""
        if self.is_server_alive() and self.server_port:
            return self.server_port

        self.stop_server()
        alloc_port = port or get_free_port()
        self.server_port = alloc_port

        files = self.read_files()
        
        # Determine entrypoint
        target_ep = entrypoint
        if not target_ep or target_ep not in files:
            candidates = [k for k in files.keys() if k.endswith("main.py") or k.endswith("app.py")]
            if candidates:
                target_ep = candidates[0]
            else:
                py_files = [k for k in files.keys() if k.endswith(".py")]
                target_ep = py_files[0] if py_files else "main.py"
        self.active_entrypoint = target_ep

        ep_content = files.get(target_ep, "")
        
        # Check if project is static web app (index.html present and no FastAPI/Flask)
        has_index_html = "index.html" in files
        is_fastapi = "FastAPI" in ep_content or any("FastAPI" in c for c in files.values())
        is_flask = "Flask" in ep_content or any("Flask" in c for c in files.values())

        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "PYTHONPATH": str(self.root_path),
            "PORT": str(alloc_port),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        for k in ("TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "COMSPEC", "PATHEXT"):
            if k in os.environ:
                clean_env[k] = os.environ[k]

        if has_index_html and not is_fastapi and not is_flask:
            cmd = [sys.executable, "-m", "http.server", str(alloc_port), "--bind", "127.0.0.1"]
        elif is_fastapi:
            mod_name = Path(target_ep).stem
            cmd = [
                sys.executable, "-m", "uvicorn", f"{mod_name}:app",
                "--host", "127.0.0.1",
                "--port", str(alloc_port),
                "--log-level", "warning"
            ]
        else:
            cmd = [sys.executable, str(self.root_path / target_ep)]

        logger.info("Starting sandbox app server on port %d: %s", alloc_port, cmd)
        try:
            self.server_proc = subprocess.Popen(
                cmd,
                cwd=str(self.root_path),
                env=clean_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        except Exception as e:
            logger.error("Failed to spawn sandbox server process: %s", e)
            raise

        # Poll until port is alive
        for _ in range(40):
            if self.is_server_alive():
                logger.info("Sandbox app server is responsive on port %d", alloc_port)
                return alloc_port
            if self.server_proc.poll() is not None:
                _, stderr = self.server_proc.communicate()
                logger.error("Sandbox app server crashed on boot: %s", stderr)
                raise RuntimeError(f"Server exited unexpectedly: {stderr}")
            time.sleep(0.1)

        return alloc_port

    def stop_server(self) -> None:
        """Gracefully terminates the background server process."""
        if self.server_proc:
            try:
                self.server_proc.terminate()
                self.server_proc.wait(timeout=2)
            except Exception:
                try:
                    self.server_proc.kill()
                except Exception:
                    pass
            self.server_proc = None
        self.server_port = None

    def discover_openapi_routes(self) -> List[Dict[str, Any]]:
        """Queries the running server for live OpenAPI paths or extracts decorators via regex."""
        if not self.is_server_alive() or not self.server_port:
            return self._discover_routes_from_ast()

        try:
            url = f"http://127.0.0.1:{self.server_port}/openapi.json"
            req = urllib.request.Request(url, headers={"User-Agent": "TARA-Preview-Probe"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                paths = data.get("paths", {})
                routes = []
                for p, methods in paths.items():
                    for m, spec in methods.items():
                        if m.lower() in ("get", "post", "put", "delete", "patch"):
                            routes.append({
                                "method": m.upper(),
                                "path": p,
                                "summary": spec.get("summary") or f"{m.upper()} {p}",
                                "tags": spec.get("tags", []),
                                "params": [param.get("name") for param in spec.get("parameters", []) if "name" in param],
                            })
                return routes
        except Exception as e:
            logger.debug("Failed to fetch live openapi.json from sandbox (falling back to AST): %s", e)
            return self._discover_routes_from_ast()

    def _discover_routes_from_ast(self) -> List[Dict[str, Any]]:
        """Fallback route extractor via regex decorator inspection."""
        routes = []
        files = self.read_files()
        for fpath, code in files.items():
            if not fpath.endswith(".py"):
                continue
            import re
            matches = re.findall(r'@(?:app|router)\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']', code, re.IGNORECASE)
            for method, path in matches:
                routes.append({
                    "method": method.upper(),
                    "path": path,
                    "summary": f"{method.upper()} {path}",
                    "tags": [Path(fpath).stem],
                    "params": re.findall(r'\{([^}]+)\}', path),
                })
        return routes

    def cleanup(self) -> None:
        self.stop_server()
        if Path(self.temp_dir).exists():
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning("Error cleaning up sandbox dir %s: %s", self.temp_dir, e)


class DockerSandbox(BaseSandbox):
    """Tier 2: Isolated Docker micro-container execution with CPU/Memory limits and no network."""

    def __init__(self, session_id: str, image: str = "python:3.12-slim"):
        super().__init__(session_id)
        self.tier_name = "DockerSandbox"
        self.image = image
        self.temp_dir = tempfile.mkdtemp(prefix=f"tara_docker_{session_id[:8]}_")
        self.root_path = Path(self.temp_dir).resolve()

    def write_files(self, files: Dict[str, str]) -> None:
        for rel_path, content in files.items():
            target = (self.root_path / rel_path).resolve()
            if not str(target).startswith(str(self.root_path)):
                raise ValueError(f"Illegal path traversal attempt: {rel_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def read_files(self) -> Dict[str, str]:
        result = {}
        if not self.root_path.exists():
            return result
        for file_path in self.root_path.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(self.root_path).as_posix()
                if "__pycache__" in rel_path or rel_path.startswith("."):
                    continue
                try:
                    result[rel_path] = file_path.read_text(encoding="utf-8")
                except Exception:
                    pass
        return result

    def run_command(
        self,
        cmd: List[str],
        timeout: int = 30,
        envs: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        # Construct docker run command with security limits
        host_mount = str(self.root_path).replace("\\", "/")
        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1.0",
            "-v", f"{host_mount}:/workspace",
            "-w", "/workspace",
        ]
        if envs:
            for k, v in envs.items():
                docker_cmd.extend(["-e", f"{k}={v}"])
        docker_cmd.append(self.image)
        docker_cmd.extend(cmd)

        start_time = time.time()
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration_ms=round(duration, 2),
                sandbox_tier=self.tier_name
            )
        except subprocess.TimeoutExpired:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                stdout="",
                stderr=f"Docker container execution timed out after {timeout}s.",
                exit_code=-1,
                duration_ms=round(duration, 2),
                sandbox_tier=self.tier_name
            )
        except Exception as exc:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                stdout="",
                stderr=f"Docker execution failed: {exc}",
                exit_code=1,
                duration_ms=round(duration, 2),
                sandbox_tier=self.tier_name
            )

    def cleanup(self) -> None:
        if Path(self.temp_dir).exists():
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning("Error cleaning up docker mount %s: %s", self.temp_dir, e)


class E2BSandbox(BaseSandbox):
    """Tier 1: Cloud isolated microVM execution using E2B Code Interpreter."""

    def __init__(
        self,
        session_id: str,
        api_key: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None
    ):
        super().__init__(session_id)
        self.tier_name = "E2BSandbox"
        from app.core.config import settings
        self.api_key = api_key or settings.e2b_api_key or os.getenv("E2B_API_KEY")
        self.envs = dict(envs or {})
        self.files_cache: Dict[str, str] = {}
        self.sandbox_instance = None
        self._sast_tools_installed = False

    def _ensure_sandbox(self):
        if self.sandbox_instance is None:
            from e2b_code_interpreter import Sandbox
            self.sandbox_instance = Sandbox.create(
                api_key=self.api_key,
                envs=self.envs if self.envs else None
            )

    def write_files(self, files: Dict[str, str]) -> None:
        self.files_cache.update(files)
        try:
            self._ensure_sandbox()
            for path, content in files.items():
                clean_path = path.replace("\\", "/").lstrip("/")
                self.sandbox_instance.files.write(clean_path, content)
        except Exception as exc:
            logger.warning("E2B write_files error: %s", exc)

    def read_files(self) -> Dict[str, str]:
        if self.sandbox_instance is None:
            return self.files_cache
        updated = {}
        for path in self.files_cache:
            clean_path = path.replace("\\", "/").lstrip("/")
            try:
                content = self.sandbox_instance.files.read(clean_path)
                if content is not None:
                    updated[path] = content
                else:
                    updated[path] = self.files_cache[path]
            except Exception:
                updated[path] = self.files_cache[path]
        return updated

    def run_command(
        self,
        cmd: List[str],
        timeout: int = 30,
        envs: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        start_time = time.time()
        try:
            self._ensure_sandbox()
            cmd_str = " ".join(cmd)
            # If command involves bandit, flake8, or strix, ensure they are installed in E2B microVM
            if ("bandit" in cmd_str or "flake8" in cmd_str or "strix" in cmd_str) and not self._sast_tools_installed:
                try:
                    self.sandbox_instance.commands.run("pip install bandit flake8", timeout=60)
                    if "strix" in cmd_str:
                        self.sandbox_instance.commands.run("pip install strix-agent", timeout=60)
                    self._sast_tools_installed = True
                except Exception as inst_err:
                    logger.warning("Failed to install SAST/Strix tools in E2B: %s", inst_err)

            combined_envs = dict(self.envs)
            if envs:
                combined_envs.update(envs)

            stdout = ""
            stderr = ""
            exit_code = 0
            try:
                exec_out = self.sandbox_instance.commands.run(
                    cmd_str,
                    timeout=timeout,
                    envs=combined_envs if combined_envs else None
                )
                stdout = exec_out.stdout or ""
                stderr = exec_out.stderr or ""
                exit_code = exec_out.exit_code or 0
            except Exception as e:
                # E2B throws CommandExitException when commands return non-zero exit code (e.g. bandit findings)
                if hasattr(e, "exit_code"):
                    stdout = getattr(e, "stdout", "") or ""
                    stderr = getattr(e, "stderr", "") or ""
                    exit_code = getattr(e, "exit_code", 1) or 1
                else:
                    raise

            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=round(duration, 2),
                sandbox_tier=self.tier_name
            )
        except Exception as exc:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                stdout="",
                stderr=f"E2B execution error: {exc}",
                exit_code=1,
                duration_ms=round(duration, 2),
                sandbox_tier=self.tier_name
            )

    def cleanup(self) -> None:
        if self.sandbox_instance:
            try:
                self.sandbox_instance.kill()
            except Exception:
                pass
            self.sandbox_instance = None


def _is_docker_available() -> bool:
    """Checks if docker CLI is present and the Docker daemon is responding."""
    try:
        res = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2
        )
        return res.returncode == 0
    except Exception:
        return False


def _is_e2b_available() -> bool:
    """Checks if E2B_API_KEY is configured and library is installed."""
    from app.core.config import settings
    api_key = settings.e2b_api_key or os.getenv("E2B_API_KEY")
    if not api_key:
        return False
    try:
        import e2b_code_interpreter
        return True
    except ImportError:
        return False


def get_sandbox(session_id: str, envs: Optional[Dict[str, str]] = None) -> BaseSandbox:
    """Factory creating the appropriate sandbox instance according to environment capabilities."""
    if _is_e2b_available():
        logger.info("Initializing Tier 1: E2BSandbox for session %s", session_id)
        return E2BSandbox(session_id, envs=envs)

    if _is_docker_available():
        logger.info("Initializing Tier 2: DockerSandbox for session %s", session_id)
        return DockerSandbox(session_id)

    logger.info("Initializing Tier 3: LocalEphemeralSandbox for session %s", session_id)
    return LocalEphemeralSandbox(session_id)


# Global registry of persistent session sandboxes
active_session_sandboxes: Dict[str, BaseSandbox] = {}


def get_or_create_session_sandbox(session_id: str, files: Optional[Dict[str, str]] = None) -> BaseSandbox:
    """Retrieves or creates a long-lived session sandbox instance, writing files if provided.
    
    Session sandboxes require local loopback connectivity (127.0.0.1) for reverse-proxying
    the live interactive preview to the running app process.
    """
    if session_id in active_session_sandboxes:
        sb = active_session_sandboxes[session_id]
        if files:
            sb.write_files(files)
        return sb

    sb = LocalEphemeralSandbox(session_id)
    if files:
        sb.write_files(files)
    active_session_sandboxes[session_id] = sb
    return sb


def cleanup_session_sandbox(session_id: str) -> None:
    """Terminates any running server processes and deletes the sandbox for the given session."""
    sb = active_session_sandboxes.pop(session_id, None)
    if sb:
        try:
            sb.cleanup()
        except Exception as e:
            logger.warning("Error cleaning up session sandbox %s: %s", session_id, e)

