"""Unit and integration tests for SQLite persistent checkpointer and 24h TTL cleanup job."""

import os
import time
import zipfile
import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.cleanup import cleanup_expired_resources, start_cleanup_scheduler, stop_cleanup_scheduler
from app.core.session_manager import SessionManager, session_manager
from app.main import app

client = TestClient(app)

TEST_PRD = """# Persistent State Test PRD
Build a stateful verification module to test database serialization and 24-hour cleanup routines.
"""


def test_sqlite_persistence_across_manager_instances():
    """Verify that graph states persist in SQLite across restarts (simulated via new SessionManager instances)."""
    session_id = f"test-persist-{int(time.time())}"
    
    # 1. Start session with original manager
    snapshot = session_manager.start_session(
        session_id=session_id,
        prd_text=TEST_PRD,
        prd_filename="TestPersist.md"
    )
    assert snapshot["session_id"] == session_id
    assert snapshot["status"] == "awaiting_approval"
    assert snapshot["ceo_critique"] is not None
    
    # 2. Simulate server restart by creating a completely separate SessionManager reading the same SQLite DB
    restarted_manager = SessionManager()
    
    # 3. Check metadata was loaded from SQLite
    assert session_id in restarted_manager.session_meta
    assert restarted_manager.session_meta[session_id]["prd_filename"] == "TestPersist.md"
    
    # 4. Check state snapshot is reconstructed from SQLite checkpointer
    recovered_snap = restarted_manager.get_state_snapshot(session_id)
    assert recovered_snap["session_id"] == session_id
    assert recovered_snap["status"] == "awaiting_approval"
    assert recovered_snap["ceo_critique"] == snapshot["ceo_critique"]
    assert recovered_snap["is_interrupted"] is True
    
    # Clean up test session
    session_manager.delete_session(session_id)


def test_ttl_cleanup_expired_sessions_and_packages():
    """Verify that sessions, packages, and temp folders older than TTL are automatically purged."""
    now = time.time()
    expired_id = f"expired-sess-{int(now)}"
    active_id = f"active-sess-{int(now)}"
    
    # Insert mock metadata directly into SQLite: 1 expired (30h old) and 1 active (1h old)
    with session_manager.db_conn:
        session_manager.db_conn.execute("""
            INSERT OR REPLACE INTO session_metadata (session_id, prd_filename, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (expired_id, "Expired.md", "completed", now - 108000, now - 108000))
        
        session_manager.db_conn.execute("""
            INSERT OR REPLACE INTO session_metadata (session_id, prd_filename, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (active_id, "Active.md", "in_progress", now - 3600, now - 3600))
    
    # Create corresponding .zip files in storage/packages/
    packages_dir = settings.storage_dir / "packages"
    packages_dir.mkdir(parents=True, exist_ok=True)
    
    expired_pkg = packages_dir / f"tara-{expired_id}.zip"
    active_pkg = packages_dir / f"tara-{active_id}.zip"
    
    expired_pkg.write_text("dummy expired zip content")
    active_pkg.write_text("dummy active zip content")
    
    # Backdate the expired file's modification time to 30 hours ago
    past_time = now - 108000
    os.utime(str(expired_pkg), (past_time, past_time))
    
    # Run cleanup with 24h TTL (86400s)
    stats = cleanup_expired_resources(ttl_seconds=86400)
    
    assert stats["pruned_sessions"] >= 1
    assert stats["deleted_zip_packages"] >= 1
    
    # Expired session and package should be removed
    cursor = session_manager.db_conn.cursor()
    row = cursor.execute("SELECT session_id FROM session_metadata WHERE session_id = ?", (expired_id,)).fetchone()
    assert row is None
    assert not expired_pkg.exists()
    
    # Active session and package should be intact
    active_row = cursor.execute("SELECT session_id FROM session_metadata WHERE session_id = ?", (active_id,)).fetchone()
    assert active_row is not None
    assert active_pkg.exists()
    
    # Clean up active test files
    session_manager.delete_session(active_id)
    if active_pkg.exists():
        active_pkg.unlink()


def test_api_session_listing_and_cleanup_endpoints():
    """Verify GET /api/sessions, POST /api/sessions/cleanup, and DELETE /api/sessions/{session_id} endpoints."""
    # 1. Start a session
    sess_id = f"api-test-{int(time.time())}"
    start_res = client.post("/api/sessions/start", json={
        "session_id": sess_id,
        "prd_text": TEST_PRD,
        "prd_filename": "API_PRD.md"
    })
    assert start_res.status_code == 200
    
    # 2. Test GET /api/sessions
    list_res = client.get("/api/sessions")
    assert list_res.status_code == 200
    sessions = list_res.json().get("sessions", [])
    assert any(s["session_id"] == sess_id for s in sessions)
    
    # 3. Test POST /api/sessions/cleanup
    cleanup_res = client.post("/api/sessions/cleanup", json={"ttl_seconds": 86400})
    assert cleanup_res.status_code == 200
    clean_data = cleanup_res.json()
    assert clean_data["status"] == "success"
    assert "cleanup_stats" in clean_data
    
    # 4. Test DELETE /api/sessions/{session_id}
    del_res = client.delete(f"/api/sessions/{sess_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"
    
    # Confirm it is no longer in GET /api/sessions
    list_res2 = client.get("/api/sessions")
    sessions2 = list_res2.json().get("sessions", [])
    assert not any(s["session_id"] == sess_id for s in sessions2)


def test_cleanup_scheduler_lifecycle():
    """Verify APScheduler initialization and graceful shutdown."""
    sched = start_cleanup_scheduler()
    assert sched is not None
    assert sched.running is True
    
    # Check that the job is registered
    job = sched.get_job("tara_24h_cleanup_job")
    assert job is not None
    assert "24h Session & Package TTL Cleanup" in job.name
    
    # Stop scheduler
    stop_cleanup_scheduler()
    assert sched.running is False
