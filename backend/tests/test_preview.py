"""Tests for Live App Preview split panel backend router and WebSocket /ws/preview."""

import json
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.routers.preview import preview_manager, broadcast_preview_reload_sync

client = TestClient(app)


def test_preview_status_endpoint():
    """Verify GET /api/preview/status endpoint returns valid connection manager metadata."""
    res = client.get("/api/preview/status")
    assert res.status_code == 200
    data = res.json()
    assert "connected_clients" in data
    assert "status" in data
    assert data["status"] in ["ready", "syncing", "executing"]


def test_preview_reload_post_endpoint():
    """Verify POST /api/preview/reload triggers broadcast without errors."""
    payload = {
        "files": {
            "index.html": "<!DOCTYPE html><html><body><h1>Test Live Preview</h1></body></html>",
            "style.css": "body { background: #09090B; color: #FFFFFF; }",
        },
        "target_file": "index.html",
        "trigger": "test_suite",
        "url": "http://localhost:3000/preview",
    }
    res = client.post("/api/preview/reload", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "reloaded"
    assert data["target_file"] == "index.html"


def test_preview_websocket_handshake_and_ping_pong():
    """Verify WebSocket /ws/preview connects, sends PREVIEW_INIT, and responds to PING."""
    with client.websocket_connect("/ws/preview") as ws:
        # Initial handshake message
        init_msg = ws.receive_json()
        assert init_msg["type"] == "PREVIEW_INIT"
        assert "status" in init_msg
        assert "connected_clients" in init_msg

        # Send PING and expect PONG
        ws.send_json({"type": "PING"})
        pong_msg = ws.receive_json()
        assert pong_msg["type"] == "PONG"


def test_preview_websocket_hot_reload_broadcast():
    """Verify WebSocket client receives HOT_RELOAD payload on manual trigger."""
    with client.websocket_connect("/ws/preview") as ws:
        # Handshake
        ws.receive_json()

        # Trigger reload request from client
        ws.send_json({
            "type": "HOT_RELOAD_REQUEST",
            "files": {"index.html": "<div>Hot Reloaded</div>"},
            "target_file": "index.html",
            "url": "http://localhost:3000",
        })

        # Client should receive HOT_RELOAD broadcast
        msg = ws.receive_json()
        assert msg["type"] == "HOT_RELOAD"
        assert msg["files"]["index.html"] == "<div>Hot Reloaded</div>"
        assert msg["target_file"] == "index.html"
        assert msg["status"] == "ready"


def test_preview_websocket_console_logs_and_runtime_errors():
    """Verify WebSocket handles CONSOLE_LOG and IFRAME_RUNTIME_ERROR gracefully."""
    with client.websocket_connect("/ws/preview") as ws:
        ws.receive_json()

        # Send console log payload
        ws.send_json({
            "type": "CONSOLE_LOG",
            "level": "warn",
            "message": "Component rendered twice in strict mode",
            "time": "12:00:00",
        })

        # Send iframe runtime error payload
        ws.send_json({
            "type": "IFRAME_RUNTIME_ERROR",
            "message": "Uncaught ReferenceError: foo is not defined",
            "source": "App.jsx",
            "lineno": 42,
            "colno": 12,
            "stack": "ReferenceError: foo is not defined\n    at App.jsx:42:12",
        })

        # Send status update
        ws.send_json({
            "type": "PREVIEW_STATUS_UPDATE",
            "status": "executing",
        })


def test_broadcast_preview_reload_sync_helper():
    """Verify broadcast_preview_reload_sync helper executes without throwing errors."""
    broadcast_preview_reload_sync(
        files={"app.py": "print('live test')"},
        target_file="app.py",
        trigger="unit_test",
    )
    assert preview_manager.latest_state["target_file"] == "app.py"
    assert preview_manager.latest_state["trigger"] == "unit_test"
