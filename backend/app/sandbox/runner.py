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
import subprocess
import sys
import tempfile
import time
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
    def run_command(self, cmd: List[str], timeout: int = 30) -> ExecutionResult:
        """Executes a command inside the sandbox."""
        pass

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Destroys and cleans up the sandbox resources."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


class LocalEphemeralSandbox(BaseSandbox):
    """Tier 3: Local isolated temporary directory with timeout guards and env sanitization."""

    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.tier_name = "LocalEphemeralSandbox"
        self.temp_dir = tempfile.mkdtemp(prefix=f"tara_sandbox_{session_id[:8]}_")
        self.root_path = Path(self.temp_dir).resolve()

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

    def run_command(self, cmd: List[str], timeout: int = 30) -> ExecutionResult:
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

        # Use the current Python interpreter if 'python' is invoked
        formatted_cmd = []
        for i, part in enumerate(cmd):
            if i == 0 and part in ("python", "python3"):
                formatted_cmd.append(sys.executable)
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

    def cleanup(self) -> None:
        if Path(self.temp_dir).exists():
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning("Error cleaning up sandbox dir %s: %s", self.temp_dir, e)


class DockerSandbox(BaseSandbox):
    """Tier 2: Isolated Docker micro-container execution with CPU/Memory limits and no network."""

    def __init__(self, session_id: str, image: str = "python:3.11-slim"):
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

    def run_command(self, cmd: List[str], timeout: int = 30) -> ExecutionResult:
        # Construct docker run command with security limits
        host_mount = str(self.root_path).replace("\\", "/")
        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1.0",
            "-v", f"{host_mount}:/workspace",
            "-w", "/workspace",
            self.image
        ] + cmd

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

    def __init__(self, session_id: str, api_key: Optional[str] = None):
        super().__init__(session_id)
        self.tier_name = "E2BSandbox"
        self.api_key = api_key or os.getenv("E2B_API_KEY")
        self.files_cache: Dict[str, str] = {}
        # Lazy initialization
        self.sandbox_instance = None

    def _ensure_sandbox(self):
        if self.sandbox_instance is None:
            from e2b_code_interpreter import Sandbox
            self.sandbox_instance = Sandbox(api_key=self.api_key)

    def write_files(self, files: Dict[str, str]) -> None:
        self.files_cache.update(files)
        try:
            self._ensure_sandbox()
            for path, content in files.items():
                self.sandbox_instance.files.write(path, content)
        except Exception as exc:
            logger.warning("E2B write_files error: %s", exc)

    def read_files(self) -> Dict[str, str]:
        # Return updated cache or read from sandbox
        return self.files_cache

    def run_command(self, cmd: List[str], timeout: int = 30) -> ExecutionResult:
        start_time = time.time()
        try:
            self._ensure_sandbox()
            command_str = " ".join(cmd)
            exec_out = self.sandbox_instance.commands.run(command_str, timeout=timeout)
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(
                stdout=exec_out.stdout or "",
                stderr=exec_out.stderr or "",
                exit_code=exec_out.exit_code or 0,
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
    if not os.getenv("E2B_API_KEY"):
        return False
    try:
        import e2b_code_interpreter
        return True
    except ImportError:
        return False


def get_sandbox(session_id: str) -> BaseSandbox:
    """Factory creating the appropriate sandbox instance according to environment capabilities."""
    if _is_e2b_available():
        logger.info("Initializing Tier 1: E2BSandbox for session %s", session_id)
        return E2BSandbox(session_id)

    if _is_docker_available():
        logger.info("Initializing Tier 2: DockerSandbox for session %s", session_id)
        return DockerSandbox(session_id)

    logger.info("Initializing Tier 3: LocalEphemeralSandbox for session %s", session_id)
    return LocalEphemeralSandbox(session_id)
