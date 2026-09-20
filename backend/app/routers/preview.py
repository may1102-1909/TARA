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
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Response, HTTPException, status
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preview", tags=["preview"])


class PreviewReloadRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="Active session identifier")
    files: Optional[Dict[str, str]] = Field(default=None, description="Workspace files dictionary")
    target_file: Optional[str] = Field(default="index.html", description="Active file trigger")
    trigger: Optional[str] = Field(default="manual", description="Trigger source (manual, agent_stream, dev_qa)")
    url: Optional[str] = Field(default="/preview", description="Target preview URL")
    version_tag: Optional[str] = Field(default=None, description="Code revision tag e.g. Build v1")
    proxy_url: Optional[str] = Field(default=None, description="Proxied sandbox base URL")
    routes: Optional[List[Dict[str, Any]]] = Field(default=None, description="Discovered route endpoints")


class PreviewStatusResponse(BaseModel):
    connected_clients: int
    latest_trigger: Optional[str] = None
    latest_file: Optional[str] = None
    status: str = "ready"
    session_id: Optional[str] = None
    version_tag: Optional[str] = None


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
            "session_id": None,
            "version_tag": "Live Sandbox",
            "routes": [],
            "proxy_url": None,
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
            "session_id": self.latest_state.get("session_id"),
            "version_tag": self.latest_state.get("version_tag", "Live Sandbox"),
            "routes": self.latest_state.get("routes", []),
            "proxy_url": self.latest_state.get("proxy_url"),
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
        session_id: Optional[str] = None,
        version_tag: Optional[str] = None,
        routes: Optional[List[Dict[str, Any]]] = None,
        proxy_url: Optional[str] = None,
    ):
        """Broadcasts hot-reload payload to all connected preview clients."""
        if files:
            self.latest_state["files"] = files
        if target_file:
            self.latest_state["target_file"] = target_file
        if url:
            self.latest_state["url"] = url
        if session_id:
            self.latest_state["session_id"] = session_id
        if version_tag:
            self.latest_state["version_tag"] = version_tag
        if routes is not None:
            self.latest_state["routes"] = routes
        if proxy_url:
            self.latest_state["proxy_url"] = proxy_url
        self.latest_state["trigger"] = trigger
        self.latest_state["status"] = "ready"

        payload = {
            "type": "HOT_RELOAD",
            "status": "ready",
            "files": files or self.latest_state.get("files", {}),
            "target_file": target_file or self.latest_state.get("target_file", "index.html"),
            "trigger": trigger,
            "url": url or self.latest_state.get("url", "http://localhost:3000"),
            "session_id": session_id or self.latest_state.get("session_id"),
            "version_tag": version_tag or self.latest_state.get("version_tag", "Live Sandbox"),
            "routes": routes if routes is not None else self.latest_state.get("routes", []),
            "proxy_url": proxy_url or self.latest_state.get("proxy_url"),
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
    session_id: Optional[str] = None,
    version_tag: Optional[str] = None,
    routes: Optional[List[Dict[str, Any]]] = None,
    proxy_url: Optional[str] = None,
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
                    session_id=session_id,
                    version_tag=version_tag,
                    routes=routes,
                    proxy_url=proxy_url,
                )
            )
        else:
            asyncio.run(
                preview_manager.broadcast_reload(
                    files=files,
                    target_file=target_file,
                    trigger=trigger,
                    url=url,
                    session_id=session_id,
                    version_tag=version_tag,
                    routes=routes,
                    proxy_url=proxy_url,
                )
            )
    except Exception as exc:
        logger.debug("Asyncio loop not active for preview broadcast: %s", exc)


@router.get("/routes/{session_id}")
async def get_session_routes(session_id: str) -> Dict[str, Any]:
    """Discovers runtime routes and metadata directly from the running sandbox instance."""
    from app.sandbox.runner import get_or_create_session_sandbox, active_session_sandboxes
    from app.core.session_manager import session_manager

    snapshot = session_manager.get_state_snapshot(session_id)
    files = (
        snapshot.get("security_patches")
        or snapshot.get("qa_refactored_files")
        or snapshot.get("dev_code_files")
        or {}
    )

    sb = active_session_sandboxes.get(session_id)
    if not sb and files:
        sb = get_or_create_session_sandbox(session_id, files)

    if not sb:
        return {
            "session_id": session_id,
            "status": "not_started",
            "server_port": None,
            "has_ui": False,
            "routes": [],
            "version_tag": "No Build",
        }

    # If server is not running yet, attempt startup
    if not sb.is_server_alive() and files:
        sb.write_files(files)
        try:
            sb.start_server()
        except Exception as e:
            logger.warning("Failed to auto-start sandbox server for %s: %s", session_id, e)

    port = sb.get_server_port()
    is_alive = sb.is_server_alive()
    routes = sb.discover_openapi_routes() if is_alive else []
    has_ui = "index.html" in (files or sb.read_files())

    version_tag = (
        "Build v3 (Security Patched)" if snapshot.get("security_patches")
        else ("Build v2 (QA Refactored)" if snapshot.get("qa_refactored_files")
        else ("Build v1 (Dev Scaffold)" if snapshot.get("dev_code_files")
        else "Live Sandbox"))
    )

    proxy_base = f"/api/preview/proxy/{session_id}"
    docs_url = f"{proxy_base}/docs"
    openapi_url = f"{proxy_base}/openapi.json"

    return {
        "session_id": session_id,
        "status": "running" if is_alive else "stopped",
        "server_port": port,
        "has_ui": has_ui,
        "openapi_url": openapi_url,
        "docs_url": docs_url,
        "version_tag": version_tag,
        "routes": routes,
    }


@router.api_route("/proxy/{session_id}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
@router.api_route("/proxy/{session_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_preview_request(session_id: str, request: Request, path: str = ""):
    """Reverse-proxies requests directly to the session's live sandboxed microservice process."""
    from app.sandbox.runner import get_or_create_session_sandbox, active_session_sandboxes
    from app.core.session_manager import session_manager

    sb = active_session_sandboxes.get(session_id)
    if not sb:
        snapshot = session_manager.get_state_snapshot(session_id)
        files = (
            snapshot.get("security_patches")
            or snapshot.get("qa_refactored_files")
            or snapshot.get("dev_code_files")
            or {}
        )
        if not files:
            return Response(
                content="<html><body style='background:#09090b;color:#e4e4e7;font-family:sans-serif;padding:2rem;text-align:center;'>"
                        "<h2 style='color:#f43f5e;'>No Microservice Code Available</h2>"
                        "<p style='color:#a1a1aa;'>Build code for this session first before previewing.</p>"
                        "</body></html>",
                media_type="text/html",
                status_code=404,
            )
        sb = get_or_create_session_sandbox(session_id, files)

    if not sb.is_server_alive():
        try:
            port = sb.start_server()
        except Exception as exc:
            logger.error("Error starting server for session %s: %s", session_id, exc)
            return Response(
                content=f"<html><body style='background:#09090b;color:#e4e4e7;font-family:sans-serif;padding:2rem;'>"
                        f"<h2 style='color:#f43f5e;'>Sandbox Execution Error</h2>"
                        f"<pre style='background:#18181b;padding:1rem;border-radius:6px;color:#f87171;'>{exc}</pre>"
                        f"</body></html>",
                media_type="text/html",
                status_code=502,
            )
    else:
        port = sb.get_server_port()

    if not port:
        return Response(
            content="<html><body style='background:#09090b;color:#e4e4e7;font-family:sans-serif;padding:2rem;'>"
                    "<h2 style='color:#f43f5e;'>Sandbox Server Unreachable</h2>"
                    "<p>No active port found for this sandbox.</p>"
                    "</body></html>",
            media_type="text/html",
            status_code=502,
        )

    clean_path = path.lstrip("/")
    target_url = f"http://127.0.0.1:{port}/{clean_path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Filter headers to forward
    exclude_headers = {"host", "content-length", "connection", "accept-encoding"}
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in exclude_headers
    }
    forward_headers["host"] = f"127.0.0.1:{port}"

    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=body if body else None,
            )

            content_bytes = resp.content
            media_type = resp.headers.get("content-type", "")

            # If serving FastAPI /docs Swagger UI, rewrite OpenAPI JSON spec URL so it routes through proxy
            proxy_base = f"/api/preview/proxy/{session_id}"
            if "text/html" in media_type or clean_path in ("docs", "docs/"):
                try:
                    html_str = content_bytes.decode("utf-8")
                    proxy_openapi = f"{proxy_base}/openapi.json"
                    # Rewrite OpenAPI spec URL in Swagger UI
                    if "/openapi.json" in html_str:
                        html_str = html_str.replace("url: '/openapi.json'", f"url: '{proxy_openapi}'")
                        html_str = html_str.replace('url: "/openapi.json"', f'url: "{proxy_openapi}"')
                    content_bytes = html_str.encode("utf-8")
                except Exception as rewrite_err:
                    logger.debug("Failed rewriting Swagger UI html: %s", rewrite_err)

            response_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")
            }

            return Response(
                content=content_bytes,
                status_code=resp.status_code,
                headers=response_headers,
                media_type=media_type,
            )

    except httpx.RequestError as req_err:
        logger.warning("Proxy connection failed for session %s (port %s): %s", session_id, port, req_err)
        return Response(
            content=f"<html><body style='background:#09090b;color:#e4e4e7;font-family:sans-serif;padding:2rem;'>"
                    f"<h2 style='color:#f43f5e;'>502 Bad Gateway</h2>"
                    f"<p>The sandboxed microservice on port {port} did not respond: {req_err}</p>"
                    f"</body></html>",
            media_type="text/html",
            status_code=502,
        )


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
