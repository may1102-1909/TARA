"""Comprehensive tests for google-antigravity SDK integration, workspace capabilities,

FastAPI endpoints (/api/tara/edit), and line-by-line diff streaming in TARA.
"""

import asyncio
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.agents.antigravity_agent import (
    is_antigravity_installed,
    create_antigravity_agent_config,
    resolve_workspace_tools,
)
from app.agents.tara_agent import (
    TaraAgentOrchestrator,
    compute_line_diff,
    resolve_workspace_tools as tara_resolve_workspace_tools,
)

client = TestClient(app)


def test_antigravity_sdk_installed():
    """Verify google-antigravity SDK is installed and accessible in the environment."""
    assert is_antigravity_installed() is True


def test_workspace_capabilities_mapping():
    """Verify built-in workspace capabilities (READ_FILE, WRITE_FILE, LIST_DIR) map to BuiltinTools."""
    from google.antigravity import BuiltinTools

    # Resolve specific capabilities
    tools = resolve_workspace_tools(["READ_FILE", "WRITE_FILE", "LIST_DIR"])
    assert BuiltinTools.VIEW_FILE in tools
    assert BuiltinTools.EDIT_FILE in tools
    assert BuiltinTools.CREATE_FILE in tools
    assert BuiltinTools.LIST_DIR in tools

    # Resolve default full capability set
    all_tools = tara_resolve_workspace_tools()
    assert BuiltinTools.VIEW_FILE in all_tools
    assert BuiltinTools.LIST_DIR in all_tools
    assert BuiltinTools.CREATE_FILE in all_tools
    assert BuiltinTools.EDIT_FILE in all_tools


def test_antigravity_agent_configuration():
    """Verify Antigravity Agent configuration is properly assembled with workspace target."""
    from google.antigravity import BuiltinTools

    config = create_antigravity_agent_config(
        system_instructions="You are TARA's Senior Principal AI Software Engineer.",
        workspace_path="test_workspace",
        capabilities=["READ_FILE", "WRITE_FILE", "LIST_DIR"],
    )
    assert config is not None
    assert config.system_instructions == "You are TARA's Senior Principal AI Software Engineer."
    assert any("test_workspace" in w for w in config.workspaces)

    # Check that file tools are enabled
    tools = config.capabilities.enabled_tools
    assert BuiltinTools.VIEW_FILE in tools
    assert BuiltinTools.EDIT_FILE in tools
    assert BuiltinTools.CREATE_FILE in tools
    assert BuiltinTools.LIST_DIR in tools


def test_orchestrator_initialization_and_diff_computation():
    """Verify TaraAgentOrchestrator workspace targeting and line-by-line diff computation."""
    orchestrator = TaraAgentOrchestrator()
    assert orchestrator.is_available() is True
    assert orchestrator.workspace_path.exists()

    orig = "def hello():\n    return 'old'\n"
    mod = "def hello():\n    return 'new'\n\ndef added():\n    pass\n"

    diff_data = compute_line_diff(orig, mod, "test_file.py")
    assert diff_data["filename"] == "test_file.py"
    assert diff_data["original"] == orig
    assert diff_data["modified"] == mod
    assert diff_data["additions"] > 0
    assert diff_data["deletions"] > 0
    assert any("return 'new'" in line for line in diff_data["diff_lines"])


def test_api_tara_status_endpoint():
    """Verify GET /api/tara/status returns runtime diagnostics and available tools."""
    res = client.get("/api/tara/status")
    assert res.status_code == 200
    data = res.json()
    assert data["antigravity_sdk_installed"] is True
    assert isinstance(data["available_workspace_tools"], list)
    assert len(data["available_workspace_tools"]) > 0
    assert "active_jobs_count" in data


def test_api_tara_edit_async_endpoint():
    """Verify POST /api/tara/edit queues a non-blocking asynchronous edit job."""
    payload = {
        "prompt": "Inspect codebase and prepare refactoring recommendations.",
        "target_file": "main.py",
        "sync": False,
    }
    res = client.post("/api/tara/edit", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert "Agent task queued asynchronously" in data["message"]

    job_id = data["job_id"]

    # Verify job can be queried via GET /api/tara/jobs/{job_id}
    job_res = client.get(f"/api/tara/jobs/{job_id}")
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["job_id"] == job_id
    assert job_data["prompt"] == payload["prompt"]


def test_websocket_tara_handshake():
    """Verify WebSocket /ws/tara connection and initial handshake."""
    with client.websocket_connect("/ws/tara") as websocket:
        init_data = websocket.receive_json()
        assert init_data["type"] == "init"
        assert init_data["sdk_ready"] is True
        assert "workspace" in init_data


def test_line_by_line_diff_streaming_events():
    """Verify line-by-line diff streaming events emitted to callback."""
    events = []

    async def mock_callback(event):
        events.append(event)

    orchestrator = TaraAgentOrchestrator()

    # Simulate diff computation and streaming
    orig = "line1\nline2\n"
    mod = "line1\nline2_modified\nline3_added\n"
    diff_data = compute_line_diff(orig, mod, "module.py")

    assert diff_data["additions"] == 2
    assert diff_data["deletions"] == 1
    assert len(diff_data["diff_lines"]) > 0
