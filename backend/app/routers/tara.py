"""FastAPI router for TARA Antigravity agentic file execution and diff streaming.

Provides:
- POST /api/tara/edit: Non-blocking asynchronous (and optional synchronous) code edit endpoint.
- GET /api/tara/jobs/{job_id}: Job status and diff retrieval.
- GET /api/tara/status: Antigravity SDK availability and runtime diagnostics.
- WebSocket /ws/tara (and /api/tara/ws): Bidirectional prompt submission and real-time line-by-line diff streaming to Monaco.
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

from app.agents.tara_agent import (
    TaraAgentOrchestrator,
    compute_line_diff,
    is_antigravity_installed,
    resolve_workspace_tools,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tara", tags=["tara"])


class TaraEditRequest(BaseModel):
    prompt: str = Field(..., min_length=3, description="User instruction or prompt for the agent")
    target_file: Optional[str] = Field(default=None, description="Optional target file to inspect or modify")
    workspace: Optional[str] = Field(default=None, description="Optional workspace root directory")
    sync: Optional[bool] = Field(default=False, description="Wait for synchronous execution completion")
    capabilities: Optional[List[str]] = Field(
        default=None,
        description="Optional list of capabilities (e.g. ['READ_FILE', 'WRITE_FILE', 'LIST_DIR'])",
    )


class TaraEditResponse(BaseModel):
    job_id: str
    status: str
    message: str
    workspace: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


# In-memory registry of active and completed agent background tasks
active_jobs: Dict[str, Dict[str, Any]] = {}


@router.get("/status")
async def get_tara_status():
    """Returns Antigravity SDK availability, enabled capabilities, and active background job count."""
    installed = is_antigravity_installed()
    available_tools = [str(t) for t in resolve_workspace_tools()] if installed else []
    return {
        "antigravity_sdk_installed": installed,
        "available_workspace_tools": available_tools,
        "active_jobs_count": len(active_jobs),
    }


@router.post("/edit", response_model=TaraEditResponse)
async def agentic_edit_endpoint(req: TaraEditRequest):
    """Executes a code inspection, edit, or refactoring task using Antigravity Agent.

    Runs asynchronously in the background by default to prevent blocking the Uvicorn event loop.
    """
    if not is_antigravity_installed():
        raise HTTPException(
            status_code=503,
            detail="google-antigravity SDK is not installed in the environment."
        )

    job_id = f"job-{uuid.uuid4().hex[:8]}"
    orchestrator = TaraAgentOrchestrator(workspace_dir=req.workspace)

    active_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "prompt": req.prompt,
        "target_file": req.target_file,
        "workspace": str(orchestrator.workspace_path),
        "result": None,
        "error": None,
    }

    async def run_task():
        active_jobs[job_id]["status"] = "in_progress"
        try:
            res = await orchestrator.execute_edit(
                prompt=req.prompt,
                target_file=req.target_file,
            )
            active_jobs[job_id]["status"] = "completed"
            active_jobs[job_id]["result"] = res
        except Exception as e:
            active_jobs[job_id]["status"] = "failed"
            active_jobs[job_id]["error"] = str(e)
            logger.error("Error in background agent edit task %s: %s", job_id, e)

    # 1. Synchronous execution: awaited without blocking the event loop
    if req.sync:
        await run_task()
        job_data = active_jobs[job_id]
        return TaraEditResponse(
            job_id=job_id,
            status=job_data["status"],
            message="Edit completed synchronously.",
            workspace=job_data["workspace"],
            result=job_data.get("result"),
        )

    # 2. Non-blocking asynchronous background execution
    asyncio.create_task(run_task())

    return TaraEditResponse(
        job_id=job_id,
        status="queued",
        message="Agent task queued asynchronously. Connect to /ws/tara for live diff stream.",
        workspace=str(orchestrator.workspace_path),
    )


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Checks the progress, results, and streamed diffs of an asynchronous agent job."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job ID not found.")
    return active_jobs[job_id]


async def tara_websocket_handler(websocket: WebSocket, default_workspace: Optional[str] = None):
    """Shared WebSocket handler for bidirectional prompt execution and line-by-line diff streaming."""
    await websocket.accept()
    logger.info("Monaco client connected to TARA WebSocket stream.")

    orchestrator = TaraAgentOrchestrator(workspace_dir=default_workspace)

    try:
        await websocket.send_json({
            "type": "init",
            "message": "Connected to TARA Antigravity Agent runtime.",
            "sdk_ready": is_antigravity_installed(),
            "workspace": str(orchestrator.workspace_path),
        })

        while True:
            data = await websocket.receive_json()
            prompt = data.get("prompt", "")
            target_file = data.get("target_file")
            workspace = data.get("workspace")

            if not prompt:
                await websocket.send_json({
                    "type": "error",
                    "error": "No prompt provided in message payload.",
                })
                continue

            if workspace:
                orchestrator = TaraAgentOrchestrator(workspace_dir=workspace)

            # Callback forwarding real-time tokens, thoughts, tool invocations, and line diffs to Monaco
            async def ws_event_callback(event: Dict[str, Any]):
                try:
                    await websocket.send_json(event)
                except Exception as ex:
                    logger.warning("Failed to send WebSocket event to Monaco client: %s", ex)

            await websocket.send_json({
                "type": "status",
                "status": "processing_prompt",
                "workspace": str(orchestrator.workspace_path),
                "target_file": target_file,
            })

            # Execute agent non-blockingly on the event loop
            try:
                result = await orchestrator.execute_edit(
                    prompt=prompt,
                    target_file=target_file,
                    event_callback=ws_event_callback,
                )
            except Exception as err:
                await websocket.send_json({
                    "type": "error",
                    "error": str(err),
                })

    except WebSocketDisconnect:
        logger.info("Monaco client disconnected from TARA WebSocket stream.")
    except Exception as exc:
        logger.error("Unexpected error on TARA WebSocket: %s", exc)


@router.websocket("/ws")
async def router_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint routed at /api/tara/ws."""
    await tara_websocket_handler(websocket)


async def tara_websocket_endpoint(websocket: WebSocket):
    """Standalone WebSocket endpoint bound to /ws/tara."""
    await tara_websocket_handler(websocket)
