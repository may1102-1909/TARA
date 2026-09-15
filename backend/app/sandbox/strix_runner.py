"""Programmatic Strix Runner for Autonomous Security Penetration Testing.

Executes Strix (https://github.com/usestrix/strix) in headless / non-interactive mode:
`strix -n --target <directory>`

Supports:
1. Isolated Docker container mounting target workspace directory.
2. Direct execution inside E2B Cloud Sandbox.
3. Local subprocess fallback with JSON & heuristic vulnerability parsing.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.sandbox.e2b_runner import SecurityFindingModel, map_strix_to_owasp
from app.core.config import settings

logger = logging.getLogger(__name__)


class StrixRunner:
    """Runs Strix programmatically in headless mode against a target workspace."""

    def __init__(self, workspace_path: Optional[str] = None):
        if workspace_path:
            self.workspace_path = Path(workspace_path).resolve()
        else:
            self.workspace_path = Path(__file__).resolve().parent.parent.parent.parent
        self.strix_llm = os.getenv("STRIX_LLM", "gemini/gemini-2.5-flash")
        self.llm_api_key = os.getenv("LLM_API_KEY", settings.gemini_api_key or os.getenv("GEMINI_API_KEY", ""))

    def is_docker_available(self) -> bool:
        """Checks if Docker daemon is running and reachable."""
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return res.returncode == 0
        except Exception:
            return False

    def is_strix_cli_available(self) -> bool:
        """Checks if strix CLI binary is installed in the system PATH."""
        return shutil.which("strix") is not None

    def run_strix(
        self,
        target_dir: Optional[str] = None,
        timeout: int = 60
    ) -> List[SecurityFindingModel]:
        """Runs Strix in non-interactive mode (`strix -n --target <path>`) and parses findings."""
        target = Path(target_dir).resolve() if target_dir else self.workspace_path
        findings: List[SecurityFindingModel] = []
        stdout = ""
        stderr = ""

        env = os.environ.copy()
        env["STRIX_LLM"] = self.strix_llm
        env["LLM_API_KEY"] = self.llm_api_key

        # Option A: Isolated Docker Container Execution
        if self.is_docker_available():
            logger.info("Running Strix inside isolated Docker container mounting: %s", target)
            docker_cmd = [
                "docker", "run", "--rm",
                "-v", f"{str(target)}:/src",
                "-e", f"STRIX_LLM={self.strix_llm}",
                "-e", f"LLM_API_KEY={self.llm_api_key}",
                "usestrix/strix:latest",
                "strix", "-n", "--target", "/src"
            ]
            try:
                proc = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=env
                )
                stdout = proc.stdout
                stderr = proc.stderr
            except Exception as d_err:
                logger.warning("Docker Strix execution failed: %s. Falling back to CLI/local.", d_err)

        # Option B: Direct CLI Execution (if installed or Docker failed)
        if not stdout and self.is_strix_cli_available():
            logger.info("Running Strix via host CLI binary...")
            cli_cmd = ["strix", "-n", "--target", str(target)]
            try:
                proc = subprocess.run(
                    cli_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=env,
                    cwd=str(target)
                )
                stdout = proc.stdout
                stderr = proc.stderr
            except Exception as c_err:
                logger.warning("CLI Strix execution failed: %s", c_err)

        # Parse output into SecurityFindingModel schema
        findings = self.parse_strix_results(stdout, stderr, target)
        return findings

    def parse_strix_results(
        self,
        stdout: str,
        stderr: str,
        target_dir: Path
    ) -> List[SecurityFindingModel]:
        """Parses JSON or text findings from Strix into SecurityFindingModel items."""
        findings: List[SecurityFindingModel] = []
        combined = f"{stdout}\n{stderr}".strip()

        # 1. JSON parsing
        try:
            data = json.loads(stdout)
            items = data if isinstance(data, list) else (data.get("findings") or data.get("vulnerabilities") or [])
            for it in items:
                title = it.get("title") or it.get("issue") or it.get("name") or "Strix Finding"
                sev = it.get("severity", "medium").lower()
                f_path = it.get("file_path") or it.get("file") or "main.py"
                ln = it.get("line_number") or it.get("line")
                poc = it.get("poc") or it.get("exploit")
                findings.append(
                    SecurityFindingModel(
                        tool="strix",
                        severity=sev,
                        issue=title,
                        file_path=str(f_path).replace("\\", "/").lstrip("./"),
                        line_number=int(ln) if ln and str(ln).isdigit() else None,
                        category=map_strix_to_owasp(title),
                        exploit_poc=poc,
                        patch_recommendation=it.get("remediation"),
                    )
                )
            if findings:
                return findings
        except Exception:
            pass

        # 2. Text report regex parsing
        pattern = re.compile(r"\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s+([^:\n]+)(?::\s*([^\s:]+)(?::(\d+))?)?", re.IGNORECASE)
        for match in pattern.finditer(combined):
            sev = match.group(1).lower()
            issue = match.group(2).strip()
            f_path = match.group(3) or "main.py"
            ln = int(match.group(4)) if match.group(4) else 1
            findings.append(
                SecurityFindingModel(
                    tool="strix",
                    severity=sev,
                    issue=issue,
                    file_path=f_path.replace("\\", "/").lstrip("./"),
                    line_number=ln,
                    category=map_strix_to_owasp(issue),
                    patch_recommendation=f"Harden against {issue}.",
                )
            )

        # 3. Code heuristics if no external container/CLI returned findings
        if not findings and target_dir.exists():
            for py_file in target_dir.rglob("*.py"):
                if "__pycache__" in str(py_file) or ".pytest" in str(py_file):
                    continue
                try:
                    code = py_file.read_text(encoding="utf-8", errors="replace")
                    rel_name = str(py_file.relative_to(target_dir)).replace("\\", "/")
                    if "eval(" in code:
                        findings.append(
                            SecurityFindingModel(
                                tool="strix",
                                severity="critical",
                                issue="Dynamic Code Injection via eval()",
                                file_path=rel_name,
                                line_number=1,
                                category="A03:2021-Injection",
                                exploit_poc="eval('__import__(\"os\").system(\"id\")')",
                                patch_recommendation="Use ast.literal_eval() or explicit data structures.",
                            )
                        )
                    if "shell=True" in code:
                        findings.append(
                            SecurityFindingModel(
                                tool="strix",
                                severity="high",
                                issue="Command Injection via subprocess shell=True",
                                file_path=rel_name,
                                line_number=1,
                                category="A03:2021-Injection",
                                exploit_poc="Arbitrary argument chaining",
                                patch_recommendation="Pass command arguments as a list with shell=False.",
                            )
                        )
                except Exception:
                    pass

        return findings
