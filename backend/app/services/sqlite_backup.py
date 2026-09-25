"""Consistent SQLite snapshots for single-replica deployments."""

import logging
import os
import shutil
import sqlite3
import threading
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)
_lock = threading.Lock()


def sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    return Path(database_url.removeprefix(prefix)) if database_url.startswith(prefix) else None


def backup_sqlite_database():
    cfg = get_settings()
    source_path = sqlite_path(cfg.database_url)
    if not source_path or not cfg.sqlite_backup_path or not source_path.exists():
        return False
    target = Path(cfg.sqlite_backup_path)
    local_snapshot = Path(f"/tmp/techsignal-snapshot-{threading.get_ident()}.db")
    remote_pending = target.with_suffix(target.suffix + ".pending")
    try:
        with _lock:
            with sqlite3.connect(source_path, timeout=30) as source, sqlite3.connect(local_snapshot) as destination:
                source.backup(destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local_snapshot, remote_pending)
            os.replace(remote_pending, target)
        return True
    except (OSError, sqlite3.Error):
        logger.exception("SQLite backup failed")
        return False
    finally:
        local_snapshot.unlink(missing_ok=True)
