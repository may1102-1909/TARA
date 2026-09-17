"""Test interactive code editing and token streaming via /ws/tara/stream."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routers.tara_stream import AntigravityStreamAgent, StreamChunk


def test_tara_stream_agent_initialization():
    """Verify AntigravityStreamAgent initializes properly."""
    agent = AntigravityStreamAgent()
    assert agent is not None
    assert agent.workspace is not None


@pytest.mark.asyncio
async def test_tara_stream_edit_chat():
    """Verify AntigravityStreamAgent yields code chunks for an edit request with existing code."""
    agent = AntigravityStreamAgent()
    existing_code = (
        "class Cache:\n"
        "    def __init__(self):\n"
        "        self.items = {}\n"
    )
    prompt = "Add a delete method to remove keys."

    chunks = []
    async for chunk in agent.chat(prompt=prompt, stream=True, current_code=existing_code, file_path="main.py"):
        assert isinstance(chunk, StreamChunk)
        assert isinstance(chunk.text, str)
        chunks.append(chunk.text)

    full_output = "".join(chunks)
    assert len(full_output) > 0
    # Should not contain markdown fences
    assert "```python" not in full_output
    assert "```" not in full_output


def test_websocket_stream_interactive_edit():
    """Verify WebSocket /ws/tara/stream accepts edit payloads and streams tokens."""
    client = TestClient(app)
    with client.websocket_connect("/ws/tara/stream") as websocket:
        init_msg = websocket.receive_json()
        assert init_msg["type"] == "STREAM_INIT"

        payload = {
            "prompt": "Add a thread-safe get method with TTL check",
            "file_path": "main.py",
            "current_code": "class Cache:\n    def __init__(self):\n        self.items = {}\n",
            "action": "edit",
        }
        websocket.send_json(payload)

        start_msg = websocket.receive_json()
        assert start_msg["type"] == "STREAM_START"
        assert start_msg["is_edit"] is True
        assert start_msg["file_path"] == "main.py"

        # Receive at least one CODE_DELTA
        deltas = []
        while True:
            msg = websocket.receive_json()
            if msg["type"] == "CODE_DELTA":
                deltas.append(msg["delta"])
            elif msg["type"] == "STREAM_END":
                assert msg["status"] == "completed"
                break

        assert len(deltas) > 0

        # Receive companion COPILOT_MESSAGE
        copilot_msg = websocket.receive_json()
        assert copilot_msg["type"] == "COPILOT_MESSAGE"
        assert "main.py" in copilot_msg["message"]
