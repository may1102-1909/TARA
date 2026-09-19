"""Tests for React Bits PromptBar component integration in TARA IDE."""

from pathlib import Path
from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_index_html_includes_promptbar():
    """Verify that index.html contains PromptBar stylesheet, script, and mount container."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "/static/prompt-bar.css" in html
    assert "/static/prompt-bar.js" in html
    assert 'id="tara-prompt-bar-root"' in html


def test_promptbar_static_assets():
    """Verify PromptBar CSS and JS are served properly with correct MIME types and content."""
    res_css = client.get("/static/prompt-bar.css")
    assert res_css.status_code == 200
    assert ".prompt-bar" in res_css.text
    assert ".prompt-bar__sparks" in res_css.text
    assert "--pb-spark" in res_css.text

    res_js = client.get("/static/prompt-bar.js")
    assert res_js.status_code == 200
    assert "PromptBarComponent" in res_js.text
    assert "ARROW_UP" in res_js.text
    assert "SQUARE" in res_js.text


def test_promptbar_react_component_files():
    """Verify PromptBar React component source files exist in static/components/."""
    components_dir = Path(__file__).resolve().parent.parent / "app" / "static" / "components"
    jsx_file = components_dir / "PromptBar.jsx"
    css_file = components_dir / "PromptBar.css"
    assert jsx_file.exists()
    assert css_file.exists()
    assert "export default function PromptBar" in jsx_file.read_text(encoding="utf-8")
