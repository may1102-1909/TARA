"""Automated test suite verifying Live App Preview with real sandbox execution,
live reverse-proxy, runtime OpenAPI route discovery, back-to-back PRDs (Cache vs Auth),
and process teardown lifecycle upon export.
"""

import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.sandbox.runner import active_session_sandboxes, cleanup_session_sandbox

client = TestClient(app)


@pytest.fixture(autouse=True)
def fast_preview_test_env(monkeypatch):
    """Bypasses external LLM and E2B cloud API network roundtrips to execute the live sandbox suite in seconds."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "e2b_api_key", "")
    monkeypatch.setenv("E2B_API_KEY", "")

    from app.agents import ceo, developer, qa, security
    monkeypatch.setattr(ceo, "evaluate_prd", lambda *args, **kwargs: ceo.evaluate_prd_fallback(*args, **kwargs))
    monkeypatch.setattr(developer, "generate_code_from_prd", lambda prd, *args: developer.generate_code_fallback(prd))
    monkeypatch.setattr(qa, "analyze_code_qa", lambda *args, **kwargs: qa.analyze_code_qa_fallback(*args, **kwargs))
    monkeypatch.setattr(security, "LANGCHAIN_GENAI_AVAILABLE", False)
    monkeypatch.setattr(security, "run_unified_security_scan", lambda files, **kwargs: ([], ""))


def test_cache_prd_live_sandbox_and_proxy():
    """Test Cache PRD: Start -> Approve -> Verify Uvicorn sandbox launches -> Test routes & proxy."""
    session_id = f"test-cache-{int(time.time())}"

    cache_prd = """
    # PRD: High-Performance Distributed In-Memory Cache Microservice
    1. Key-value store with string keys and JSON payloads.
    2. TTL expiration and background eviction.
    3. Health check, /cache/set, /cache/get/{key}, /cache/keys, and /cache/metrics.
    """

    try:
        # 1. Start pipeline up to HITL approval gate
        start_res = client.post("/api/sessions/start", json={
            "session_id": session_id,
            "prd_text": cache_prd,
            "prd_filename": "cache_prd.md"
        })
        assert start_res.status_code == 200, f"Start failed: {start_res.text}"
        data = start_res.json()
        assert data["status"] == "awaiting_approval"

        # 2. Approve decision -> triggers code generation & sandbox server launch
        decide_res = client.post(f"/api/sessions/{session_id}/decide", json={
            "action": "approve",
            "notes": "Ensure TTL support and metrics endpoints."
        })
        assert decide_res.status_code == 200, f"Decide failed: {decide_res.text}"
        decide_data = decide_res.json()
        assert decide_data["status"] == "completed"

        # 3. Verify sandbox was registered and server process is alive
        assert session_id in active_session_sandboxes
        sb = active_session_sandboxes[session_id]
        port = sb.get_server_port()
        assert port is not None and port > 0
        assert sb.is_server_alive() is True

        # 4. Query runtime OpenAPI route discovery endpoint
        routes_res = client.get(f"/api/preview/routes/{session_id}")
        assert routes_res.status_code == 200
        routes_data = routes_res.json()
        assert routes_data["session_id"] == session_id
        assert routes_data["status"] == "running"
        assert routes_data["server_port"] == port
        assert "docs" in routes_data["docs_url"]

        route_paths = [r["path"] for r in routes_data["routes"]]
        assert any("/cache/set" in p for p in route_paths), f"Missing /cache/set in {route_paths}"
        assert any("/cache/get" in p for p in route_paths), f"Missing /cache/get in {route_paths}"
        assert any("/health" in p for p in route_paths), f"Missing /health in {route_paths}"

        # 5. Execute real proxied HTTP requests against the live sandboxed server
        # A: Health check
        health_res = client.get(f"/api/preview/proxy/{session_id}/health")
        assert health_res.status_code == 200
        health_json = health_res.json()
        assert health_json.get("status") == "ok"
        assert health_json.get("service") == "cache-microservice"

        # B: Store a key via proxied POST
        set_payload = {"key": "user:101", "value": {"name": "Alice", "role": "admin"}, "ttl": 300}
        set_res = client.post(f"/api/preview/proxy/{session_id}/cache/set", json=set_payload)
        assert set_res.status_code in (200, 201), f"Cache set failed: {set_res.text}"
        set_json = set_res.json()
        assert set_json.get("status") == "success"

        # C: Retrieve key via proxied GET
        get_res = client.get(f"/api/preview/proxy/{session_id}/cache/get/user:101")
        assert get_res.status_code == 200
        get_json = get_res.json()
        assert get_json.get("found") is True
        assert get_json.get("value", {}).get("name") == "Alice"

        # 6. Verify Swagger /docs proxy rewriting
        docs_res = client.get(f"/api/preview/proxy/{session_id}/docs")
        assert docs_res.status_code == 200
        assert "swagger-ui" in docs_res.text.lower()
        # Ensure OpenAPI URL inside docs was rewritten to proxied route
        assert f"/api/preview/proxy/{session_id}/openapi.json" in docs_res.text

    finally:
        cleanup_session_sandbox(session_id)


def test_auth_prd_differentiation_back_to_back():
    """Test Auth PRD: Confirms genuinely different routes, schemas, and live sandbox execution."""
    session_id = f"test-auth-{int(time.time())}"

    auth_prd = """
    # PRD: Authentication & Rate Limiting Microservice
    1. Issue JWT tokens with username and role.
    2. Verify tokens and revoke active sessions.
    3. Rate limiter tracking client request quotas.
    """

    try:
        # 1. Start pipeline
        start_res = client.post("/api/sessions/start", json={
            "session_id": session_id,
            "prd_text": auth_prd,
            "prd_filename": "auth_prd.md"
        })
        assert start_res.status_code == 200

        # 2. Approve
        decide_res = client.post(f"/api/sessions/{session_id}/decide", json={
            "action": "approve",
            "notes": "FastAPI auth implementation."
        })
        assert decide_res.status_code == 200

        # 3. Verify server alive
        assert session_id in active_session_sandboxes
        sb = active_session_sandboxes[session_id]
        assert sb.is_server_alive() is True

        # 4. Query runtime route discovery -> must be genuinely distinct from Cache PRD
        routes_res = client.get(f"/api/preview/routes/{session_id}")
        assert routes_res.status_code == 200
        routes_data = routes_res.json()
        route_paths = [r["path"] for r in routes_data["routes"]]

        assert any("/auth/token" in p for p in route_paths), f"Missing /auth/token in {route_paths}"
        assert any("/auth/verify" in p for p in route_paths), f"Missing /auth/verify in {route_paths}"
        assert any("/rate-limit" in p for p in route_paths), f"Missing /rate-limit in {route_paths}"
        # Cache endpoints MUST NOT exist in Auth PRD
        assert not any("/cache/set" in p for p in route_paths)

        # 5. Execute proxied auth request -> issue token
        token_payload = {"username": "lead_architect", "password": "secure_secret_pass", "role": "admin"}
        token_res = client.post(f"/api/preview/proxy/{session_id}/auth/token", json=token_payload)
        assert token_res.status_code in (200, 201), f"Auth token failed: {token_res.text}"
        token_json = token_res.json()
        access_token = token_json.get("access_token")
        assert access_token is not None
        assert "tara_sec" in access_token

        # 6. Verify token via proxied POST
        verify_res = client.post(f"/api/preview/proxy/{session_id}/auth/verify", json={"token": access_token})
        assert verify_res.status_code == 200
        verify_json = verify_res.json()
        assert verify_json.get("valid") is True
        assert verify_json.get("claims", {}).get("username") == "lead_architect"

    finally:
        cleanup_session_sandbox(session_id)


def test_sandbox_lifecycle_cleanup_on_download():
    """Verifies that downloading release .zip package tears down sandbox process and port."""
    session_id = f"test-lifecycle-{int(time.time())}"

    prd = """
    # PRD: Test Lifecycle Service
    CRUD items microservice.
    """

    try:
        # Start & approve
        client.post("/api/sessions/start", json={
            "session_id": session_id,
            "prd_text": prd,
            "prd_filename": "lifecycle.md"
        })
        client.post(f"/api/sessions/{session_id}/decide", json={"action": "approve"})

        # Verify sandbox was running
        assert session_id in active_session_sandboxes
        sb = active_session_sandboxes[session_id]
        assert sb.is_server_alive() is True

        # Download release package
        dl_res = client.get(f"/api/sessions/{session_id}/download")
        assert dl_res.status_code == 200
        assert dl_res.headers["content-type"] == "application/zip"

        # Verify sandbox was cleaned up and removed from active registry
        assert session_id not in active_session_sandboxes
        assert sb.is_server_alive() is False

    finally:
        cleanup_session_sandbox(session_id)
