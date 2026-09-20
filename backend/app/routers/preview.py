"""FastAPI router and WebSocket endpoint for real-time Live App Preview.

Provides:
- WebSocket /ws/preview (and /api/preview/ws) for bidirectional live preview sync.
- Hot-reload broadcasting when TARA developer agent or Antigravity SDK updates code.
- Capturing preview console logs and runtime error reports.
- REST endpoints /api/preview/status and /api/preview/reload.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preview", tags=["preview"])


class PreviewReloadRequest(BaseModel):
    files: Optional[Dict[str, str]] = Field(default=None, description="Workspace files dictionary")
    target_file: Optional[str] = Field(default="index.html", description="Active file trigger")
    trigger: Optional[str] = Field(default="manual", description="Trigger source (manual, agent_stream, dev_qa)")
    url: Optional[str] = Field(default="/preview", description="Target preview URL")


class PreviewStatusResponse(BaseModel):
    connected_clients: int
    latest_trigger: Optional[str] = None
    latest_file: Optional[str] = None
    status: str = "ready"


class PreviewConnectionManager:
    """Manages active WebSockets connections to the Live App Preview panel."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.latest_state: Dict[str, Any] = {
            "status": "ready",
            "files": {},
            "target_file": "index.html",
            "trigger": "init",
            "url": "http://localhost:3000",
        }
        self.log_history: List[Dict[str, Any]] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("Preview WebSocket client connected. Active: %d", len(self.active_connections))
        # Send initial handshake state
        await websocket.send_json({
            "type": "PREVIEW_INIT",
            "status": self.latest_state.get("status", "ready"),
            "target_file": self.latest_state.get("target_file", "index.html"),
            "url": self.latest_state.get("url", "http://localhost:3000"),
            "connected_clients": len(self.active_connections),
        })

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info("Preview WebSocket client disconnected. Active: %d", len(self.active_connections))

    async def broadcast_reload(
        self,
        files: Optional[Dict[str, str]] = None,
        target_file: Optional[str] = None,
        trigger: str = "agent_stream",
        url: Optional[str] = None,
    ):
        """Broadcasts hot-reload payload to all connected preview clients."""
        if files:
            self.latest_state["files"] = files
        if target_file:
            self.latest_state["target_file"] = target_file
        if url:
            self.latest_state["url"] = url
        self.latest_state["trigger"] = trigger
        self.latest_state["status"] = "ready"

        payload = {
            "type": "HOT_RELOAD",
            "status": "ready",
            "files": files or self.latest_state.get("files", {}),
            "target_file": target_file or self.latest_state.get("target_file", "index.html"),
            "trigger": trigger,
            "url": url or self.latest_state.get("url", "http://localhost:3000"),
        }

        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(payload)
            except Exception as e:
                logger.warning("Failed to send hot reload to client: %s", e)
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)


# Global preview connection manager
preview_manager = PreviewConnectionManager()


def broadcast_preview_reload_sync(
    files: Optional[Dict[str, str]] = None,
    target_file: Optional[str] = None,
    trigger: str = "agent_stream",
    url: Optional[str] = None,
):
    """Synchronous / fire-and-forget helper to broadcast hot-reload to all preview frames."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            asyncio.create_task(
                preview_manager.broadcast_reload(
                    files=files,
                    target_file=target_file,
                    trigger=trigger,
                    url=url,
                )
            )
        else:
            asyncio.run(
                preview_manager.broadcast_reload(
                    files=files,
                    target_file=target_file,
                    trigger=trigger,
                    url=url,
                )
            )
    except Exception as exc:
        logger.debug("Asyncio loop not active for preview broadcast: %s", exc)


@router.get("/status", response_model=PreviewStatusResponse)
async def get_preview_status():
    """Returns the current preview engine status and active connection count."""
    return PreviewStatusResponse(
        connected_clients=len(preview_manager.active_connections),
        latest_trigger=preview_manager.latest_state.get("trigger"),
        latest_file=preview_manager.latest_state.get("target_file"),
        status=preview_manager.latest_state.get("status", "ready"),
    )


@router.post("/reload")
async def trigger_preview_reload(req: PreviewReloadRequest):
    """Manually triggers a hot-reload across all connected preview frames."""
    await preview_manager.broadcast_reload(
        files=req.files,
        target_file=req.target_file,
        trigger=req.trigger or "manual_post",
        url=req.url,
    )
    return {
        "status": "reloaded",
        "broadcast_to": len(preview_manager.active_connections),
        "target_file": req.target_file,
    }


async def preview_websocket_handler(websocket: WebSocket):
    """Handles incoming WebSocket connections on /ws/preview."""
    await preview_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "PING":
                await websocket.send_json({"type": "PONG"})

            elif msg_type == "HOT_RELOAD_REQUEST":
                await preview_manager.broadcast_reload(
                    files=data.get("files"),
                    target_file=data.get("target_file"),
                    trigger="client_request",
                    url=data.get("url"),
                )

            elif msg_type == "PREVIEW_STATUS_UPDATE":
                status = data.get("status", "ready")
                preview_manager.latest_state["status"] = status
                # Echo to other clients if needed
                for client in list(preview_manager.active_connections):
                    if client != websocket:
                        try:
                            await client.send_json({
                                "type": "STATUS_CHANGED",
                                "status": status,
                            })
                        except Exception:
                            pass

            elif msg_type == "CONSOLE_LOG":
                # Store in recent logs and log to server
                log_item = {
                    "level": data.get("level", "info"),
                    "message": data.get("message", ""),
                    "time": data.get("time"),
                }
                preview_manager.log_history.append(log_item)
                if len(preview_manager.log_history) > 200:
                    preview_manager.log_history.pop(0)

            elif msg_type == "IFRAME_RUNTIME_ERROR":
                logger.warning("Preview iframe error: %s at %s:%s", data.get("message"), data.get("lineno"), data.get("colno"))

    except WebSocketDisconnect:
        preview_manager.disconnect(websocket)
    except Exception as e:
        logger.error("Error in preview websocket handler: %s", e)
        preview_manager.disconnect(websocket)


@router.websocket("/ws")
async def preview_subroute_websocket(websocket: WebSocket):
    """Subrouted WebSocket on /api/preview/ws."""
    await preview_websocket_handler(websocket)


async def preview_websocket_endpoint(websocket: WebSocket):
    """Direct root WebSocket on /ws/preview."""
    await preview_websocket_handler(websocket)
