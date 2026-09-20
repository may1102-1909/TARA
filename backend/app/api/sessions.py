"""FastAPI API endpoints for session lifecycle, HITL decisions, and package download."""

import io
import uuid
from typing import Optional, List
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Response, UploadFile, File, Query
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.core.config import settings
from app.core.cleanup import cleanup_expired_resources
from app.core.session_manager import session_manager
from app.sandbox.packaging import create_release_zip
from app.sandbox.runner import get_sandbox

router = APIRouter(prefix="/sessions", tags=["sessions"])


def extract_text_from_upload(filename: str, content_bytes: bytes) -> tuple[str, str, int]:
    """Extracts raw text from an uploaded document (PDF, Markdown, or plain text).
    
    Returns:
        tuple: (extracted_text, file_type, page_count)
    """
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        file_type = "pdf"
        try:
            reader = PdfReader(io.BytesIO(content_bytes))
            page_count = len(reader.pages)
            pages_text = []
            for page in reader.pages:
                page_str = page.extract_text() or ""
                if page_str.strip():
                    pages_text.append(page_str.strip())
            extracted_text = "\n\n".join(pages_text)
            if not extracted_text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="PDF contains no extractable text (it may be scanned/image-only or encrypted)."
                )
            return extracted_text, file_type, page_count
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF document: {exc}")

    file_type = "markdown" if lower_name.endswith(".md") else "text"
    try:
        extracted_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            extracted_text = content_bytes.decode("latin-1")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to decode document text: {exc}")

    return extracted_text, file_type, 1


class ExecuteCodeRequest(BaseModel):
    entrypoint: Optional[str] = Field(default="main.py", description="Target file to execute in sandbox")
    custom_args: Optional[List[str]] = Field(default=[], description="Optional CLI arguments")


class StartSessionRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="Optional custom session identifier")
    prd_text: str = Field(..., min_length=10, description="Raw PRD / BRD markdown or text")
    prd_filename: Optional[str] = Field(default="PRD.md", description="Original filename")


class DecisionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|request_changes|reject)$")
    notes: Optional[str] = Field(default="", description="Optional feedback notes for revision loop")


class DirectGraphRunRequest(BaseModel):
    prd_text: str = Field(..., min_length=10, description="Raw PRD content")


class CleanupRequest(BaseModel):
    ttl_seconds: Optional[int] = Field(default=86400, description="Time-to-live threshold in seconds (default 24h)")


@router.get("")
async def list_sessions_endpoint():
    """Lists all active and persisted sessions from the SQLite database."""
    return {"sessions": session_manager.list_sessions()}


@router.post("/cleanup")
async def trigger_cleanup_endpoint(req: Optional[CleanupRequest] = None):
    """Manually triggers TTL cleanup job for expired sessions, zip packages, and sandbox folders."""
    ttl = req.ttl_seconds if req and req.ttl_seconds is not None else 86400
    stats = cleanup_expired_resources(ttl_seconds=ttl)
    return {"status": "success", "cleanup_stats": stats}


@router.post("/upload")
async def upload_document_endpoint(
    file: UploadFile = File(...),
    start_session: bool = Query(default=False, description="Automatically launch TARA session with extracted text")
):
    """Parses .pdf, .md, or .txt specification documents into raw text for PRD generation."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    extracted_text, file_type, page_count = extract_text_from_upload(file.filename, content)

    if len(extracted_text.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Extracted document content is too short (minimum 10 characters required)."
        )

    response_data = {
        "filename": file.filename,
        "file_type": file_type,
        "page_count": page_count,
        "char_count": len(extracted_text),
        "extracted_text": extracted_text,
    }

    if start_session:
        session_id = f"tara-{uuid.uuid4().hex[:8]}"
        snapshot = session_manager.start_session(
            session_id=session_id,
            prd_text=extracted_text,
            prd_filename=file.filename
        )
        response_data["session"] = snapshot
        response_data["session_id"] = session_id

    return response_data


@router.post("/graph/run")
async def run_direct_graph(req: DirectGraphRunRequest):
    """Executes the full sequential multi-agent graph (CEO -> Dev -> QA -> Security) directly."""
    from app.graph.builder import graph
    from app.graph.state import create_initial_state
    session_id = f"graph-{uuid.uuid4().hex[:8]}"
    try:
        initial_state = create_initial_state(session_id=session_id, prd_text=req.prd_text)
        result = graph.invoke(initial_state)
        return {"session_id": session_id, "status": "completed", "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


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

    # Persist release artifact on disk in packages directory for 24h TTL tracking
    try:
        packages_dir = settings.storage_dir / "packages"
        packages_dir.mkdir(parents=True, exist_ok=True)
        pkg_file = packages_dir / f"tara-{session_id}.zip"
        pkg_file.write_bytes(zip_bytes)
    except Exception:
        pass

    # Teardown sandbox background process and release port upon release export
    try:
        from app.sandbox.runner import cleanup_session_sandbox
        cleanup_session_sandbox(session_id)
    except Exception as e:
        logger.warning("Sandbox cleanup on download package error for %s: %s", session_id, e)

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=tara-{session_id}.zip"
        }
    )


@router.delete("/{session_id}")
async def delete_session_endpoint(session_id: str):
    """Deletes a session and its persistent checkpointer data from SQLite."""
    deleted = session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session could not be deleted or not found.")

    pkg_file = settings.storage_dir / "packages" / f"tara-{session_id}.zip"
    if pkg_file.exists():
        try:
            pkg_file.unlink()
        except Exception:
            pass

    return {"status": "deleted", "session_id": session_id}


@router.post("/{session_id}/run")
async def run_sandboxed_code(session_id: str, req: ExecuteCodeRequest = ExecuteCodeRequest()):
    """Executes generated and hardened codebase inside the isolated sandbox."""
    snapshot = session_manager.get_state_snapshot(session_id)
    if snapshot.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Session not found")

    code_files = snapshot.get("security_patches") or snapshot.get("qa_refactored_files") or snapshot.get("dev_code_files", {})
    if not code_files:
        raise HTTPException(status_code=400, detail="No code files available to execute in sandbox.")

    entrypoint = req.entrypoint or "main.py"
    if entrypoint not in code_files:
        candidates = [k for k in code_files.keys() if k.endswith("main.py") or k.endswith("app.py") or k.endswith(".py")]
        entrypoint = candidates[0] if candidates else list(code_files.keys())[0]

    with get_sandbox(f"{session_id}_run") as sb:
        sb.write_files(code_files)
        cmd = ["python", entrypoint] + (req.custom_args or [])
        res = sb.run_command(cmd, timeout=15)

        return {
            "session_id": session_id,
            "entrypoint": entrypoint,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.exit_code,
            "duration_ms": res.duration_ms,
            "sandbox_tier": res.sandbox_tier,
        }


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
