"""Tests for Live App Preview Split Panel (Davis AI UI Style).

Verifies:
- Live Preview WebSocket (/ws/preview) handshake and message handling.
- REST endpoints /api/preview/status and /api/preview/reload.
- Static assets (preview.css, preview-frame.js, PreviewFrame.jsx).
- Split canvas layout elements in index.html.
"""

from pathlib import Path
from starlette.testclient import TestClient

from app.main import app
from app.routers.preview import preview_manager

client = TestClient(app)


def test_preview_status_endpoint():
    """Verify GET /api/preview/status returns operational status."""
    res = client.get("/api/preview/status")
    assert res.status_code == 200
    data = res.json()
    assert "connected_clients" in data
    assert "status" in data
    assert data["status"] == "ready"


def test_preview_reload_endpoint():
    """Verify POST /api/preview/reload accepts hot-reload triggers."""
    payload = {
        "files": {"index.html": "<h1>Test App</h1>"},
        "target_file": "index.html",
        "trigger": "test_unit",
        "url": "http://localhost:3000",
    }
    res = client.post("/api/preview/reload", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "reloaded"
    assert data["target_file"] == "index.html"


def test_preview_static_assets():
    """Verify preview.css and preview-frame.js are served properly."""
    res_css = client.get("/static/preview.css")
    assert res_css.status_code == 200
    assert ".split-canvas-container" in res_css.text
    assert ".preview-card" in res_css.text
    assert ".preview-header" in res_css.text
    assert ".preview-error-overlay" in res_css.text

    res_js = client.get("/static/preview-frame.js")
    assert res_js.status_code == 200
    assert "PreviewFrameComponent" in res_js.text
    assert "PREVIEW_CONSOLE_LOG" in res_js.text
    assert "PREVIEW_RUNTIME_ERROR" in res_js.text


def test_preview_react_component_files():
    """Verify PreviewFrame.jsx source file exists."""
    components_dir = Path(__file__).resolve().parent.parent / "app" / "static" / "components"
    jsx_file = components_dir / "PreviewFrame.jsx"
    css_file = components_dir / "PreviewFrame.css"
    assert jsx_file.exists()
    assert css_file.exists()
    assert "export default function PreviewFrame" in jsx_file.read_text(encoding="utf-8")


def test_index_html_has_split_canvas_and_preview_root():
    """Verify index.html contains split canvas layout and preview container."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "split-canvas-container" in html
    assert "split-editor-pane" in html
    assert "split-preview-pane" in html
    assert "tara-preview-root" in html
    assert "/static/preview.css" in html
    assert "/static/preview-frame.js" in html


def test_preview_websocket_handshake():
    """Verify WebSocket /ws/preview accepts connections and receives PREVIEW_INIT handshake."""
    with client.websocket_connect("/ws/preview") as websocket:
        init_data = websocket.receive_json()
        assert init_data["type"] == "PREVIEW_INIT"
        assert init_data["status"] == "ready"
        assert "connected_clients" in init_data

        # Test PING / PONG
        websocket.send_json({"type": "PING"})
        pong = websocket.receive_json()
        assert pong["type"] == "PONG"
