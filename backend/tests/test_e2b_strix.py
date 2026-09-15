"""Comprehensive tests for E2B Security Runner, Flake8, Bandit, and Strix integration,

Unified SecurityFinding Pydantic schema, ChatGoogleGenerativeAI patching,
and WebSocket diff streaming for Google Antigravity IDE.
"""

import asyncio
import json
import os
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.sandbox.e2b_runner import (
    E2BSecurityRunner,
    SecurityFinding,
    SecurityFindingModel,
    map_strix_to_owasp,
)
from app.agents.security import (
    run_unified_security_scan,
    patch_codebase_with_chat_google,
    stream_security_scan_and_diffs,
    deterministic_patch_fallback,
)

client = TestClient(app)

VULNERABLE_TEST_CODE = """import os
import subprocess

def dangerous_exec(user_input):
    # Intentional eval flaw for Strix/Bandit detection
    result = eval(user_input)
    # Intentional shell=True command injection flaw
    subprocess.run("echo " + user_input, shell=True)
    return result
"""

CLEAN_TEST_CODE = """def safe_calc(a: int, b: int) -> int:
    return a + b
"""


def test_security_finding_pydantic_schema():
    """Verify SecurityFinding schema fields: tool, severity, issue, file_path, line_number."""
    finding = SecurityFinding(
        tool="strix",
        severity="critical",
        issue="Dynamic Code Execution via eval()",
        file_path="src/engine.py",
        line_number=14,
        category="A03:2021-Injection",
        exploit_poc="eval('__import__(\"os\").system(\"id\")')",
        patch_recommendation="Use ast.literal_eval()",
    )

    data = finding.model_dump()
    assert data["tool"] == "strix"
    assert data["severity"] == "critical"
    assert data["issue"] == "Dynamic Code Execution via eval()"
    assert data["file_path"] == "src/engine.py"
    assert data["line_number"] == 14
    assert data["category"] == "A03:2021-Injection"

    # Verify compatibility alias and state dict
    assert SecurityFindingModel is SecurityFinding
    state_dict = finding.to_state_dict()
    assert state_dict["tool"] == "strix"
    assert state_dict["file"] == "src/engine.py"
    assert state_dict["line"] == 14


def test_strix_owasp_mapping():
    """Verify keyword mapping of Strix issues to OWASP Top 10 categories."""
    assert map_strix_to_owasp("SQL Injection in query builder") == "A03:2021-Injection"
    assert map_strix_to_owasp("Command Injection via shell=True") == "A03:2021-Injection"
    assert map_strix_to_owasp("JWT Session Token Bypass") == "A07:2021-Identification and Authentication Failures"
    assert map_strix_to_owasp("Insecure MD5 Cryptographic Hash") == "A02:2021-Cryptographic Failures"
    assert map_strix_to_owasp("IDOR Access Control Violation") == "A01:2021-Broken Access Control"
    assert map_strix_to_owasp("SSRF to internal metadata service") == "A10:2021-Server-Side Request Forgery (SSRF)"


def test_e2b_runner_env_forwarding_and_execution():
    """Verify E2BSecurityRunner sets STRIX_LLM and LLM_API_KEY and executes tools."""
    os.environ["STRIX_LLM"] = "gemini/gemini-2.5-flash"
    os.environ["LLM_API_KEY"] = "test-security-key-123"

    runner = E2BSecurityRunner(session_id="test_security_env_run")
    assert runner.strix_llm == "gemini/gemini-2.5-flash"
    assert runner.forwarded_envs["STRIX_LLM"] == "gemini/gemini-2.5-flash"
    assert runner.forwarded_envs["LLM_API_KEY"] == "test-security-key-123"

    events_received = []

    def log_callback(event):
        events_received.append(event)

    files = {"vulnerable.py": VULNERABLE_TEST_CODE}
    findings = runner.run_security_pipeline(files, event_callback=log_callback)

    assert isinstance(findings, list)
    assert len(findings) > 0
    # Check that findings contain tools
    tools = [f.tool for f in findings]
    assert "strix" in tools or "bandit" in tools or "flake8" in tools

    # Check that events were emitted
    assert len(events_received) > 0
    phases = [e.get("phase") for e in events_received]
    assert "init" in phases
    assert "scan_complete" in phases


def test_strix_output_parser():
    """Verify parse_strix_output handles JSON and structured CLI text output formats."""
    runner = E2BSecurityRunner(session_id="test_parser")
    files = {"main.py": VULNERABLE_TEST_CODE}

    # 1. JSON list format
    json_stdout = json.dumps([
        {
            "title": "Arbitrary Code Execution via eval",
            "severity": "critical",
            "file": "main.py",
            "line": 6,
            "remediation": "Use ast.literal_eval"
        }
    ])
    findings1 = runner.parse_strix_output(json_stdout, "", files)
    assert len(findings1) == 1
    assert findings1[0].tool == "strix"
    assert findings1[0].severity == "critical"
    assert findings1[0].line_number == 6
    assert findings1[0].category == "A03:2021-Injection"

    # 2. CLI Text format
    cli_stdout = "[HIGH] Command Injection in utils/exec.py:22"
    findings2 = runner.parse_strix_output(cli_stdout, "", files)
    assert len(findings2) == 1
    assert findings2[0].tool == "strix"
    assert findings2[0].severity == "high"
    assert findings2[0].file_path == "utils/exec.py"
    assert findings2[0].line_number == 22


def test_patch_codebase_auto_write(tmp_path):
    """Verify patch_codebase_with_chat_google hardens code and writes patched versions to disk."""
    files = {"vuln.py": VULNERABLE_TEST_CODE}
    findings = [
        SecurityFinding(
            tool="strix",
            severity="critical",
            issue="Dynamic Code Execution (eval)",
            file_path="vuln.py",
            line_number=6,
            category="A03:2021-Injection",
        ),
        SecurityFinding(
            tool="bandit",
            severity="high",
            issue="subprocess with shell=True",
            file_path="vuln.py",
            line_number=8,
            category="A03:2021-Injection",
        )
    ]

    # Test deterministic patching and disk write
    patched_map = patch_codebase_with_chat_google(
        files,
        findings,
        session_id="test_patch_write",
        workspace_dir=tmp_path,
        write_to_disk=True,
    )

    assert "vuln.py" in patched_map
    hardened_code = patched_map["vuln.py"]
    assert "shell=False" in hardened_code
    assert "ast.literal_eval" in hardened_code

    # Verify file was written to disk
    written_file = tmp_path / "vuln.py"
    assert written_file.exists()
    disk_content = written_file.read_text(encoding="utf-8")
    assert "shell=False" in disk_content


def test_stream_security_scan_and_diffs():
    """Verify stream_security_scan_and_diffs emits WebSocket diff events."""
    events = []

    async def callback(evt):
        events.append(evt)

    async def _run():
        files = {"api.py": VULNERABLE_TEST_CODE}
        return await stream_security_scan_and_diffs(
            files=files,
            session_id="test_stream",
            event_callback=callback,
        )

    result = asyncio.run(_run())

    assert result["status"] == "completed"
    assert len(result["findings"]) > 0
    assert len(result["diffs"]) > 0

    event_types = [e["type"] for e in events]
    assert "status" in event_types
    assert "scan_complete" in event_types
    assert "diff_stream_start" in event_types
    assert "diff_line" in event_types
    assert "file_diff" in event_types
    assert "complete" in event_types


def test_api_strix_scan_endpoint():
    """Verify POST /api/security/strix-scan returns unified findings and patched files."""
    payload = {
        "files": {"main.py": VULNERABLE_TEST_CODE},
        "session_id": "test_api_scan"
    }
    res = client.post("/api/security/strix-scan", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert data["findings_count"] > 0
    assert "main.py" in data["patched_files"]
    assert "shell=False" in data["patched_files"]["main.py"]


def test_api_apply_patch_endpoint(tmp_path):
    """Verify POST /api/security/apply-patch writes the patched code."""
    rel_path = "test_scratch_patched.py"
    target = Path(__file__).resolve().parent.parent.parent / rel_path

    try:
        payload = {
            "file_path": rel_path,
            "patched_code": "# Patched securely\ndef run():\n    pass\n",
            "session_id": "test_apply"
        }
        res = client.post("/api/security/apply-patch", json=payload)
        assert res.status_code == 200
        assert res.json()["status"] == "applied"
        assert target.exists()
        assert "Patched securely" in target.read_text(encoding="utf-8")
    finally:
        if target.exists():
            target.unlink()


def test_security_websocket_endpoint():
    """Verify /ws/security WebSocket connects and handles scan requests."""
    with client.websocket_connect("/ws/security") as ws:
        init_msg = ws.receive_json()
        assert init_msg["type"] == "init"
        assert "flake8" in init_msg["tools"]
        assert "bandit" in init_msg["tools"]
        assert "strix" in init_msg["tools"]

        ws.send_json({
            "action": "scan",
            "files": {"service.py": VULNERABLE_TEST_CODE},
            "session_id": "ws_test_session"
        })

        # Collect events until scan completion or complete
        got_diff = False
        for _ in range(50):
            msg = ws.receive_json()
            if msg.get("type") in ("file_diff", "diff_stream_start"):
                got_diff = True
            if msg.get("type") == "complete":
                break

        assert got_diff is True
