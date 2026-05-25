from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from codeui.config import Settings
from codeui.errors import ApiError
from codeui.logger import get_logger

LOGGER = get_logger(__name__)


class ProjectOperationLockService:
    """Simple file-based lock for project-level destructive operations.

    The lock is intentionally process-safe and volume-friendly: it uses O_EXCL
    creation of a lock file under a configurable directory. This is enough for
    one-container and shared-volume deployments without introducing users or a
    job queue.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._root = settings.project_locks_root
        self._root.mkdir(parents=True, exist_ok=True)
        self._stale_after_sec = settings.project_locks.stale_after_sec

    @contextmanager
    def acquire(self, project_id: str, operation: str, *, details: dict | None = None) -> Iterator[None]:
        project_key = self._project_key(project_id)
        lock_path = self._root / f"{project_key}.lock"
        payload = {
            "project_id": project_id,
            "operation": operation,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "details": details or {},
        }
        self._remove_stale_lock(lock_path)
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            existing = self._read_lock(lock_path)
            raise ApiError(
                "PROJECT_OPERATION_BUSY",
                "Проект сейчас занят другой операцией. Повторите действие позже.",
                status_code=409,
                details={"project_id": project_id, "requested_operation": operation, "lock": existing},
            ) from exc

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            LOGGER.info("Project operation lock acquired project_id=%s operation=%s path=%s", project_id, operation, lock_path)
            yield
        finally:
            try:
                lock_path.unlink(missing_ok=True)
                LOGGER.info("Project operation lock released project_id=%s operation=%s path=%s", project_id, operation, lock_path)
            except Exception as exc:  # pragma: no cover - best effort cleanup
                LOGGER.warning("Project operation lock cleanup failed path=%s error=%s", lock_path, exc)

    def _remove_stale_lock(self, lock_path: Path) -> None:
        if self._stale_after_sec <= 0 or not lock_path.exists():
            return
        try:
            age_sec = time.time() - lock_path.stat().st_mtime
        except FileNotFoundError:
            return
        if age_sec <= self._stale_after_sec:
            return
        existing = self._read_lock(lock_path)
        lock_path.unlink(missing_ok=True)
        LOGGER.warning("Removed stale project operation lock path=%s age_sec=%.2f lock=%s", lock_path, age_sec, existing)

    @staticmethod
    def _read_lock(lock_path: Path) -> dict:
        try:
            payload = json.loads(lock_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {"raw": payload}
        except Exception:
            return {"path": str(lock_path), "read_error": True}

    @staticmethod
    def _project_key(project_id: str) -> str:
        value = str(project_id or "unknown")
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
        return safe or "unknown"
