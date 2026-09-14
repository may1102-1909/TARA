"""End-to-end API integration tests for TARA FastAPI server."""

import io
import zipfile
import pytest
from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_PRD_TEXT = """# Microservice PRD
Build an order processing microservice in Python with REST endpoints,
data validation, logging, and security best practices.
"""


def test_api_health():
    """Verify health endpoint."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}


def test_api_full_session_lifecycle():
    """Test full cycle: Start -> Check Critique at Gate -> Approve -> Download ZIP."""
    # 1. Start Session
    session_id = "test-api-full-lifecycle"
    start_payload = {
        "session_id": session_id,
        "prd_text": SAMPLE_PRD_TEXT,
        "prd_filename": "OrderService_PRD.md"
    }
    res = client.post("/api/sessions/start", json=start_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == session_id
    assert data["is_interrupted"] is True
    assert data["status"] == "awaiting_approval"
    assert data["ceo_critique"] is not None
    assert data["dev_code_files"] == {}
    
    # 2. Inspect session via GET
    get_res = client.get(f"/api/sessions/{session_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["status"] == "awaiting_approval"
    
    # 3. Approve at HITL gate
    decide_payload = {
        "action": "approve",
        "notes": "PRD scope approved by lead."
    }
    decide_res = client.post(f"/api/sessions/{session_id}/decide", json=decide_payload)
    assert decide_res.status_code == 200
    decide_data = decide_res.json()
    assert decide_data["status"] == "completed"
    assert decide_data["user_action"] == "approve"
    assert len(decide_data["dev_code_files"]) > 0
    assert len(decide_data["security_patches"]) > 0
    assert decide_data["audit_summary"] is not None
    
    # 4. Download Release Package (.zip)
    dl_res = client.get(f"/api/sessions/{session_id}/download")
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/zip"
    
    # Verify zip content
    zf = zipfile.ZipFile(io.BytesIO(dl_res.content))
    file_list = zf.namelist()
    assert "src/main.py" in file_list
    assert "audit_summary.json" in file_list
    assert "AUDIT_SUMMARY.md" in file_list


def test_api_revision_loop():
    """Test revision loop: Start -> Request Changes -> Verify Revision -> Approve."""
    session_id = "test-api-revision-flow"
    client.post("/api/sessions/start", json={
        "session_id": session_id,
        "prd_text": SAMPLE_PRD_TEXT
    })
    
    # Request changes
    res_rc = client.post(f"/api/sessions/{session_id}/decide", json={
        "action": "request_changes",
        "notes": "Please specify rate limiting and token authentication explicitly."
    })
    assert res_rc.status_code == 200
    data_rc = res_rc.json()
    assert data_rc["revision_count"] == 1
    assert data_rc["status"] == "awaiting_approval"
    assert "rate limiting" in str(data_rc["human_feedback_notes"])
    
    # Now approve
    res_appr = client.post(f"/api/sessions/{session_id}/decide", json={
        "action": "approve"
    })
    assert res_appr.status_code == 200
    assert res_appr.json()["status"] == "completed"


def test_api_direct_graph_run():
    """Verify POST /api/sessions/graph/run runs sequential multi-agent graph to completion."""
    res = client.post("/api/sessions/graph/run", json={"prd_text": SAMPLE_PRD_TEXT})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert "result" in data
    assert "ceo_critique" in data["result"]
    assert "security_patches" in data["result"]

