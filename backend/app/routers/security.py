"""FastAPI router for Strix security scans, real-time diff streaming, and patch application."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

from app.agents.security import (
    stream_security_scan_and_diffs,
    run_unified_security_scan,
    patch_codebase_with_chat_google,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["security"])


class StrixScanRequest(BaseModel):
    files: Optional[Dict[str, str]] = Field(default=None, description="Files to scan (defaults to active workspace files)")
    session_id: Optional[str] = Field(default="default_session")
    target_dir: Optional[str] = Field(default=None, description="Optional custom target directory")
    auto_patch: bool = Field(default=False, description="Automatically write patched files directly to workspace")
    mcp_config: Optional[str] = Field(default=None, description="Optional path to custom MCP servers configuration file")
    mcp_server: Optional[str] = Field(default=None, description="Optional target specific MCP server")
    mcp_exclude: Optional[str] = Field(default=None, description="Optional MCP server to exclude")


class ApplyPatchRequest(BaseModel):
    file_path: str = Field(..., description="File path to patch")
    patched_code: str = Field(..., description="Patched code content")
    session_id: Optional[str] = Field(default="default_session")


@router.post("/strix-scan")
async def trigger_strix_scan(req: StrixScanRequest):
    """Executes triple-layer security scan (Flake8 + Bandit + Strix) and returns findings & patches."""
    workspace = Path(req.target_dir).resolve() if req.target_dir else Path(__file__).resolve().parent.parent.parent.parent
    files_to_scan = req.files
    if not files_to_scan:
        # Load files from active workspace if none provided
        files_to_scan = {}
        for py_file in workspace.rglob("*.py"):
            if any(part in str(py_file) for part in ("__pycache__", ".pytest", "venv", ".git", "site-packages")):
                continue
            try:
                rel = str(py_file.relative_to(workspace)).replace("\\", "/")
                files_to_scan[rel] = py_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

    if not files_to_scan:
        files_to_scan = {
            "main.py": "# Default entrypoint\ndef run():\n    pass\n"
        }

    findings, tier = run_unified_security_scan(
        files_to_scan,
        session_id=req.session_id,
        mcp_config=req.mcp_config,
        mcp_server=req.mcp_server,
        mcp_exclude=req.mcp_exclude,
    )
    patched_files = patch_codebase_with_chat_google(
        files_to_scan,
        findings,
        session_id=req.session_id,
        workspace_dir=workspace,
        write_to_disk=req.auto_patch,
    )

    return {
        "status": "completed",
        "sandbox_tier": tier,
        "findings_count": len(findings),
        "findings": [f.model_dump() for f in findings],
        "patched_files": patched_files,
    }


@router.post("/apply-patch")
async def apply_code_patch(req: ApplyPatchRequest):
    """Accepts a security patch and writes it directly to the workspace file."""
    workspace = Path(__file__).resolve().parent.parent.parent.parent
    clean_path = req.file_path.replace("\\", "/").lstrip("/")
    target_file = (workspace / clean_path).resolve()

    # Path traversal protection
    if not str(target_file).startswith(str(workspace)):
        raise HTTPException(status_code=400, detail="Path traversal forbidden.")

    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(req.patched_code, encoding="utf-8")
        logger.info("Applied security patch to %s", target_file)

        # Return refreshed file list
        files = []
        for p in workspace.rglob("*.py"):
            if not any(k in str(p) for k in ("__pycache__", ".git", "venv")):
                files.append(str(p.relative_to(workspace)).replace("\\", "/"))

        return {
            "status": "applied",
            "file": clean_path,
            "message": f"Successfully applied security patch to {clean_path}",
            "workspace_files": files,
        }
    except Exception as e:
        logger.error("Error writing patch to %s: %s", target_file, e)
        raise HTTPException(status_code=500, detail=str(e))


async def security_websocket_handler(websocket: WebSocket):
    """WebSocket endpoint for real-time security scan logs and Monaco diff streaming."""
    await websocket.accept()
    logger.info("Client connected to /ws/security streaming channel.")

    try:
        await websocket.send_json({
            "type": "init",
            "message": "Connected to TARA Security Agent WebSocket stream.",
            "tools": ["flake8", "bandit", "strix"],
        })

        while True:
            data = await websocket.receive_json()
            action = data.get("action", "scan")
            files = data.get("files", {})
            session_id = data.get("session_id", "security_stream")

            auto_patch = bool(data.get("auto_patch", False))
            target_dir = data.get("target_dir")
            workspace = Path(target_dir).resolve() if target_dir else Path(__file__).resolve().parent.parent.parent.parent

            if not files:
                # Load files from active workspace if none provided
                files = {}
                for py_file in workspace.rglob("*.py"):
                    if any(part in str(py_file) for part in ("__pycache__", ".pytest", "venv", ".git", "site-packages")):
                        continue
                    try:
                        rel = str(py_file.relative_to(workspace)).replace("\\", "/")
                        files[rel] = py_file.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        pass

            if not files:
                # Use default fallback file
                files = {"main.py": "import os\ndef test():\n    return 'clean'\n"}

            async def ws_callback(event: Dict[str, Any]):
                try:
                    await websocket.send_json(event)
                except Exception as ex:
                    logger.warning("Failed to send WebSocket event: %s", ex)

            # Stream scan and Monaco diffs
            await stream_security_scan_and_diffs(
                files=files,
                session_id=session_id,
                event_callback=ws_callback,
                write_to_disk=auto_patch,
                workspace_dir=workspace,
            )

    except WebSocketDisconnect:
        logger.info("Client disconnected from /ws/security.")
    except Exception as exc:
        logger.error("Error on /ws/security: %s", exc)


@router.websocket("/ws")
async def security_router_ws(websocket: WebSocket):
    """Routed at /api/security/ws."""
    await security_websocket_handler(websocket)


async def security_websocket_endpoint(websocket: WebSocket):
    """Root bound at /ws/security."""
    await security_websocket_handler(websocket)
