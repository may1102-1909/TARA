"""Automated TTL cleanup job for expired session checkpointers, .zip release packages, and temp dirs."""

import asyncio
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# pyrefly: ignore [missing-import]
from apscheduler.schedulers.background import BackgroundScheduler
# pyrefly: ignore [missing-import]
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings

logger = logging.getLogger(__name__)

# Default Time-To-Live: 24 hours (86,400 seconds)
DEFAULT_TTL_SECONDS = 24 * 3600

scheduler: Optional[BackgroundScheduler] = None


def cleanup_expired_resources(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Dict[str, Any]:
    """Cleans up expired session checkpointers, .zip release packages, and orphaned temp sandboxes."""
    from app.core.session_manager import session_manager

    now = time.time()
    cutoff_time = now - ttl_seconds

    stats = {
        "pruned_sessions": 0,
        "deleted_zip_packages": 0,
        "cleaned_temp_dirs": 0,
        "freed_bytes": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": ttl_seconds,
    }

    # 1. Prune expired session checkpointers and metadata from SQLite
    try:
        pruned_count = session_manager.prune_expired_sessions(ttl_seconds=ttl_seconds)
        stats["pruned_sessions"] = pruned_count
    except Exception as exc:
        logger.error("Error pruning expired sessions: %s", exc)

    # 2. Clean up old .zip packages in storage directory
    packages_dir = settings.storage_dir / "packages"
    if packages_dir.exists():
        for zip_file in packages_dir.glob("*.zip"):
            try:
                mtime = zip_file.stat().st_mtime
                if mtime < cutoff_time:
                    size = zip_file.stat().st_size
                    zip_file.unlink()
                    stats["deleted_zip_packages"] += 1
                    stats["freed_bytes"] += size
            except Exception as e:
                logger.warning("Failed to delete old package %s: %s", zip_file, e)

    # 3. Clean up any leftover temporary sandbox directories older than 2 hours
    temp_cutoff = now - (2 * 3600)  # 2 hours
    system_temp = Path(tempfile.gettempdir())
    for prefix in ("tara_sandbox_", "tara_docker_"):
        for temp_folder in system_temp.glob(f"{prefix}*"):
            if temp_folder.is_dir():
                try:
                    if temp_folder.stat().st_mtime < temp_cutoff:
                        shutil.rmtree(temp_folder, ignore_errors=True)
                        stats["cleaned_temp_dirs"] += 1
                except Exception:
                    pass

    logger.info(
        "TTL Cleanup completed: %d sessions pruned, %d packages deleted, %d temp dirs removed (freed %d bytes)",
        stats["pruned_sessions"],
        stats["deleted_zip_packages"],
        stats["cleaned_temp_dirs"],
        stats["freed_bytes"],
    )
    return stats


def run_cleanup_job():
    """Scheduled task invoked by APScheduler."""
    try:
        cleanup_expired_resources()
    except Exception as exc:
        logger.error("Error running automated cleanup job: %s", exc)


def start_cleanup_scheduler() -> BackgroundScheduler:
    """Initializes and starts the background TTL cleanup scheduler."""
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler()
        # Schedule to run hourly
        scheduler.add_job(
            run_cleanup_job,
            trigger=IntervalTrigger(hours=1),
            id="tara_24h_cleanup_job",
            name="Automated 24h Session & Package TTL Cleanup",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("APScheduler initialized: 24h TTL cleanup job running hourly.")
    return scheduler


def stop_cleanup_scheduler():
    """Gracefully shuts down the cleanup scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("APScheduler stopped.")
