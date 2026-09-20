"""Session manager for orchestrating LangGraph runs and WebSocket broadcasts."""

import asyncio
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set
# pyrefly: ignore [missing-import]
from fastapi import WebSocket
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.core.config import settings
from app.graph.state import create_initial_state
from app.graph.workflow import create_tara_workflow

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages persistent LangGraph SQLite checkpointers, execution threads, and WebSocket event subscribers."""

    def __init__(self):
        db_path = settings.storage_dir / "tara_sessions.db"
        self.db_conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30.0)
        try:
            self.db_conn.execute("PRAGMA journal_mode=WAL;")
            self.db_conn.execute("PRAGMA busy_timeout=10000;")
        except Exception:
            pass
        self._init_metadata_table()
        self.checkpointer = SqliteSaver(self.db_conn)
        self.checkpointer.setup()
        self.app = create_tara_workflow(checkpointer=self.checkpointer)
        self.active_websockets: Dict[str, Set[WebSocket]] = {}
        self.session_meta: Dict[str, Dict[str, Any]] = self._load_persisted_meta()

    def _init_metadata_table(self):
        with self.db_conn:
            self.db_conn.execute("""
                CREATE TABLE IF NOT EXISTS session_metadata (
                    session_id TEXT PRIMARY KEY,
                    prd_filename TEXT,
                    status TEXT,
                    created_at REAL,
                    updated_at REAL
                )
            """)

    def _load_persisted_meta(self) -> Dict[str, Dict[str, Any]]:
        meta = {}
        try:
            cursor = self.db_conn.cursor()
            rows = cursor.execute("SELECT session_id, prd_filename, status, created_at, updated_at FROM session_metadata").fetchall()
            for row in rows:
                meta[row[0]] = {
                    "prd_filename": row[1],
                    "status": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                }
        except Exception as e:
            logger.warning("Error loading session metadata: %s", e)
        return meta

    def delete_session(self, session_id: str) -> bool:
        """Removes a session's checkpoints, writes, metadata, and cleans up sandbox processes."""
        try:
            try:
                from app.sandbox.runner import cleanup_session_sandbox
                cleanup_session_sandbox(session_id)
            except Exception as sb_e:
                logger.warning("Sandbox cleanup error on session delete %s: %s", session_id, sb_e)

            with self.db_conn:
                self.db_conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (session_id,))
                self.db_conn.execute("DELETE FROM writes WHERE thread_id = ?", (session_id,))
                self.db_conn.execute("DELETE FROM session_metadata WHERE session_id = ?", (session_id,))
            self.session_meta.pop(session_id, None)
            if session_id in self.active_websockets:
                self.active_websockets.pop(session_id, None)
            return True
        except Exception as exc:
            logger.error("Failed to delete session %s: %s", session_id, exc)
            return False

    def prune_expired_sessions(self, ttl_seconds: int = 86400) -> int:
        """Deletes sessions older than the TTL limit (default 24h)."""
        cutoff = time.time() - ttl_seconds
        cursor = self.db_conn.cursor()
        rows = cursor.execute("SELECT session_id FROM session_metadata WHERE updated_at < ?", (cutoff,)).fetchall()
        expired_ids = [r[0] for r in rows]
        for sid in expired_ids:
            self.delete_session(sid)
        return len(expired_ids)

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
        now = time.time()
        self.session_meta[session_id] = {
            "prd_filename": prd_filename,
            "status": "in_progress",
            "created_at": now,
            "updated_at": now,
        }
        with self.db_conn:
            self.db_conn.execute("""
                INSERT OR REPLACE INTO session_metadata (session_id, prd_filename, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, prd_filename, "in_progress", now, now))
        
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
        """Resumes workflow from interrupt with the human decision and launches live sandbox server."""
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

                    # If code was generated or refactored/hardened, sync into live sandbox
                    if node_name in ("dev_qa_node", "security_node"):
                        try:
                            from app.sandbox.runner import get_or_create_session_sandbox
                            from app.routers.preview import broadcast_preview_reload_sync

                            stage_files = (
                                current_snap.get("security_patches")
                                or current_snap.get("qa_refactored_files")
                                or current_snap.get("dev_code_files")
                                or {}
                            )
                            if stage_files:
                                sb = get_or_create_session_sandbox(session_id, stage_files)
                                if sb.is_server_alive():
                                    sb.restart_server()
                                else:
                                    sb.start_server()

                                routes = sb.discover_openapi_routes()
                                version_tag = (
                                    "Build v2 (Security Patched)" if node_name == "security_node"
                                    else "Build v1 (Dev/QA)"
                                )
                                proxy_url = f"/api/preview/proxy/{session_id}"
                                target_f = "index.html" if "index.html" in stage_files else "main.py"
                                broadcast_preview_reload_sync(
                                    files=stage_files,
                                    target_file=target_f,
                                    trigger=node_name,
                                    url=proxy_url,
                                    session_id=session_id,
                                    version_tag=version_tag,
                                    routes=routes,
                                    proxy_url=proxy_url,
                                )
                        except Exception as sandbox_err:
                            logger.warning("Sandbox startup error during %s: %s", node_name, sandbox_err)
            
        snapshot = self.get_state_snapshot(session_id)
        now = time.time()
        new_status = snapshot.get("status", "running")
        if session_id in self.session_meta:
            self.session_meta[session_id]["status"] = new_status
            self.session_meta[session_id]["updated_at"] = now
        else:
            self.session_meta[session_id] = {
                "prd_filename": "unknown",
                "status": new_status,
                "created_at": now,
                "updated_at": now,
            }
        try:
            with self.db_conn:
                self.db_conn.execute(
                    "UPDATE session_metadata SET status = ?, updated_at = ? WHERE session_id = ?",
                    (new_status, now, session_id)
                )
        except Exception as exc:
            logger.warning("Failed to update session_metadata for %s: %s", session_id, exc)

        self.broadcast_sync(session_id, "node_update", {
            "node": "pipeline_complete",
            "snapshot": snapshot,
        })

        try:
            from app.sandbox.runner import get_or_create_session_sandbox
            from app.routers.preview import broadcast_preview_reload_sync
            final_files = snapshot.get("security_patches") or snapshot.get("qa_refactored_files") or snapshot.get("dev_code_files", {})
            if final_files:
                sb = get_or_create_session_sandbox(session_id, final_files)
                if not sb.is_server_alive():
                    sb.start_server()
                routes = sb.discover_openapi_routes()
                version_tag = (
                    "Build v2 (Security Hardened)" if snapshot.get("security_patches")
                    else "Build v1 (Dev/QA)"
                )
                proxy_url = f"/api/preview/proxy/{session_id}"
                broadcast_preview_reload_sync(
                    files=final_files,
                    target_file="index.html" if "index.html" in final_files else "main.py",
                    trigger="pipeline_complete",
                    url=proxy_url,
                    session_id=session_id,
                    version_tag=version_tag,
                    routes=routes,
                    proxy_url=proxy_url,
                )
        except Exception as err:
            logger.debug("Preview reload broadcast on pipeline completion error: %s", err)

        return snapshot

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Returns a list of all active/persisted sessions in SQLite."""
        try:
            cursor = self.db_conn.cursor()
            rows = cursor.execute(
                "SELECT session_id, prd_filename, status, created_at, updated_at FROM session_metadata ORDER BY updated_at DESC"
            ).fetchall()
            return [
                {
                    "session_id": r[0],
                    "prd_filename": r[1],
                    "status": r[2],
                    "created_at": r[3],
                    "updated_at": r[4],
                }
                for r in rows
            ]
        except Exception as exc:
            logger.warning("Failed to list sessions: %s", exc)
            return []

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
