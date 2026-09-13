"""FastAPI API endpoints for session lifecycle, HITL decisions, and package download."""

import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Response
from pydantic import BaseModel, Field

from app.core.session_manager import session_manager
from app.sandbox.packaging import create_release_zip

router = APIRouter(prefix="/sessions", tags=["sessions"])


class StartSessionRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="Optional custom session identifier")
    prd_text: str = Field(..., min_length=10, description="Raw PRD / BRD markdown or text")
    prd_filename: Optional[str] = Field(default="PRD.md", description="Original filename")


class DecisionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|request_changes|reject)$")
    notes: Optional[str] = Field(default="", description="Optional feedback notes for revision loop")


@router.post("/start")
async def start_session_endpoint(req: StartSessionRequest):
    """Initializes a new TARA run and executes until the Human Approval Gate."""
    session_id = req.session_id or f"tara-{uuid.uuid4().hex[:8]}"
    try:
        snapshot = session_manager.start_session(
            session_id=session_id,
            prd_text=req.prd_text,
            prd_filename=req.prd_filename or "PRD.md"
        )
        return snapshot
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{session_id}")
async def get_session_endpoint(session_id: str):
    """Retrieves the latest state snapshot, including current stage, logs, and artifacts."""
    snapshot = session_manager.get_state_snapshot(session_id)
    if snapshot.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Session not found")
    return snapshot


@router.post("/{session_id}/decide")
async def submit_decision_endpoint(session_id: str, req: DecisionRequest):
    """Submits the human decision to resume execution from the approval gate."""
    snapshot = session_manager.get_state_snapshot(session_id)
    if snapshot.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Session not found")
        
    if not snapshot.get("is_interrupted"):
        raise HTTPException(
            status_code=400,
            detail=f"Session is not awaiting approval (Current status: {snapshot.get('status')})"
        )

    try:
        updated_snapshot = session_manager.submit_decision(
            session_id=session_id,
            action=req.action,
            notes=req.notes or ""
        )
        return updated_snapshot
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{session_id}/download")
async def download_package_endpoint(session_id: str):
    """Downloads the final compiled release package as a .zip file."""
    snapshot = session_manager.get_state_snapshot(session_id)
    if snapshot.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Session not found")

    code_files = snapshot.get("security_patches") or snapshot.get("qa_refactored_files") or snapshot.get("dev_code_files", {})
    if not code_files:
        raise HTTPException(
            status_code=400,
            detail="No code artifacts generated for this session yet."
        )

    patches = snapshot.get("security_patches", {})
    audit = snapshot.get("audit_summary")
    
    zip_bytes = create_release_zip(
        code_files=code_files,
        patches=patches,
        audit_summary=audit,
        session_id=session_id
    )

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=tara-{session_id}.zip"
        }
    )


@router.websocket("/{session_id}/stream")
async def session_stream_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for live agent logging and state updates."""
    await websocket.accept()
    await session_manager.register_websocket(session_id, websocket)
    
    # Send initial current snapshot
    try:
        snapshot = session_manager.get_state_snapshot(session_id)
        await websocket.send_json({"type": "init", "session_id": session_id, "data": snapshot})
        
        while True:
            # Keep socket alive and accept ping/pong or client messages
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await session_manager.unregister_websocket(session_id, websocket)
