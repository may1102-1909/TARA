"""Session manager for orchestrating LangGraph runs and WebSocket broadcasts."""

import asyncio
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph.state import create_initial_state
from app.graph.workflow import create_tara_workflow


class SessionManager:
    """Manages LangGraph checkpointers, execution threads, and WebSocket event subscribers."""

    def __init__(self):
        self.checkpointer = MemorySaver()
        self.app = create_tara_workflow(checkpointer=self.checkpointer)
        self.active_websockets: Dict[str, Set[WebSocket]] = {}
        self.session_meta: Dict[str, Dict[str, Any]] = {}

    def get_config(self, session_id: str) -> Dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    async def register_websocket(self, session_id: str, ws: WebSocket) -> None:
        if session_id not in self.active_websockets:
            self.active_websockets[session_id] = set()
        self.active_websockets[session_id].add(ws)

    async def unregister_websocket(self, session_id: str, ws: WebSocket) -> None:
        if session_id in self.active_websockets:
            self.active_websockets[session_id].discard(ws)
            if not self.active_websockets[session_id]:
                del self.active_websockets[session_id]

    async def broadcast_event(self, session_id: str, event_type: str, data: Any) -> None:
        payload = {"type": event_type, "session_id": session_id, "data": data}
        if session_id in self.active_websockets:
            dead_sockets = set()
            for ws in self.active_websockets[session_id]:
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead_sockets.add(ws)
            for ws in dead_sockets:
                self.active_websockets[session_id].discard(ws)

    def broadcast_sync(self, session_id: str, event_type: str, data: Any) -> None:
        """Helper to broadcast WebSocket events synchronously from graph stream loops."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast_event(session_id, event_type, data))
        except RuntimeError:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.broadcast_event(session_id, event_type, data))
                loop.close()
            except Exception:
                pass

    def start_session(
        self,
        session_id: str,
        prd_text: str,
        prd_filename: str = "PRD.md"
    ) -> Dict[str, Any]:
        """Initializes state and runs workflow up to the human approval gate."""
        config = self.get_config(session_id)
        initial_state = create_initial_state(session_id, prd_text, prd_filename)
        self.session_meta[session_id] = {
            "prd_filename": prd_filename,
            "status": "in_progress"
        }
        
        # Run graph until interrupt at human_approval_gate, broadcasting updates live
        for chunk in self.app.stream(initial_state, config=config):
            if isinstance(chunk, dict):
                for node_name in chunk.keys():
                    current_snap = self.get_state_snapshot(session_id)
                    self.broadcast_sync(session_id, "node_update", {
                        "node": node_name,
                        "snapshot": current_snap,
                    })
            
        final_snap = self.get_state_snapshot(session_id)
        self.broadcast_sync(session_id, "node_update", {
            "node": "approval_gate",
            "snapshot": final_snap,
        })
        return final_snap

    def submit_decision(
        self,
        session_id: str,
        action: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Resumes workflow from interrupt with the human decision."""
        config = self.get_config(session_id)
        resume_payload = {"action": action, "notes": notes}
        cmd = Command(resume=resume_payload)
        
        # Stream resume execution with real-time intermediate broadcasts
        for chunk in self.app.stream(cmd, config=config):
            if isinstance(chunk, dict):
                for node_name in chunk.keys():
                    current_snap = self.get_state_snapshot(session_id)
                    self.broadcast_sync(session_id, "node_update", {
                        "node": node_name,
                        "snapshot": current_snap,
                    })
            
        snapshot = self.get_state_snapshot(session_id)
        if snapshot["status"] == "completed":
            self.session_meta.setdefault(session_id, {})["status"] = "completed"
        self.broadcast_sync(session_id, "node_update", {
            "node": "pipeline_complete",
            "snapshot": snapshot,
        })
        return snapshot

    def get_state_snapshot(self, session_id: str) -> Dict[str, Any]:
        """Extracts serializable snapshot of the current state and interrupt info."""
        config = self.get_config(session_id)
        graph_state = self.app.get_state(config)
        
        if not graph_state or not graph_state.values:
            return {"status": "not_found", "session_id": session_id}
            
        values = graph_state.values
        is_interrupted = len(graph_state.tasks) > 0 and any(t.interrupts for t in graph_state.tasks)
        interrupt_payload = None
        if is_interrupted:
            for task in graph_state.tasks:
                if task.interrupts:
                    interrupt_payload = task.interrupts[0].value
                    break

        status = "awaiting_approval" if is_interrupted else (
            "completed" if len(graph_state.tasks) == 0 else "running"
        )
        
        return {
            "session_id": session_id,
            "status": status,
            "is_interrupted": is_interrupted,
            "interrupt_payload": interrupt_payload,
            "current_stage": values.get("current_stage", "unknown"),
            "revision_count": values.get("revision_count", 0),
            "ceo_critique": values.get("ceo_critique"),
            "user_action": values.get("user_action"),
            "human_feedback_notes": values.get("human_feedback_notes", []),
            "dev_code_files": values.get("dev_code_files", {}),
            "qa_refactored_files": values.get("qa_refactored_files", {}),
            "qa_changelog": values.get("qa_changelog", []),
            "security_patches": values.get("security_patches", {}),
            "security_findings": values.get("security_findings", []),
            "audit_summary": values.get("audit_summary"),
            "logs": values.get("logs", []),
        }


session_manager = SessionManager()
