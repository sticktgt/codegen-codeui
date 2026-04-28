from __future__ import annotations

from pathlib import Path
from typing import Any

from codeui.config import Settings
from codeui.errors import ApiError
from codeui.logger import get_logger
from codeui.services.json_io import read_json_file

LOGGER = get_logger(__name__)


class RunArtifactService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._runs_root = settings.runs_root

    def list_run_ids(self) -> list[str]:
        if not self._runs_root.exists():
            return []
        run_ids = [path.name for path in self._runs_root.iterdir() if path.is_dir() and path.name.startswith("pipeline-")]
        return sorted(run_ids, reverse=True)

    def get_run_dir(self, run_id: str) -> Path:
        self._validate_run_id(run_id)
        run_dir = self._runs_root / run_id
        if not run_dir.exists() or not run_dir.is_dir():
            raise ApiError("RUN_NOT_FOUND", f"Run not found: {run_id}", status_code=404, details={"run_id": run_id})
        return run_dir

    def read_pipeline_run(self, run_id: str) -> dict[str, Any]:
        run_dir = self.get_run_dir(run_id)
        matches = sorted(run_dir.glob("pipeline_run_*.json"))
        if not matches:
            raise ApiError("RUN_ARTIFACT_NOT_FOUND", f"pipeline_run JSON not found for run: {run_id}", status_code=404)
        payload = read_json_file(matches[-1])
        if not isinstance(payload, dict):
            raise ApiError("RUN_ARTIFACT_INVALID", f"pipeline_run JSON must be object for run: {run_id}", status_code=500)
        return payload

    def read_optional_json(self, run_id: str, file_name: str) -> dict[str, Any] | None:
        run_dir = self.get_run_dir(run_id)
        path = run_dir / file_name
        if not path.exists():
            return None
        payload = read_json_file(path)
        if not isinstance(payload, dict):
            raise ApiError("RUN_ARTIFACT_INVALID", f"JSON artifact must be object: {path}", status_code=500)
        return payload

    def read_text_artifact(self, run_id: str, file_name: str) -> str | None:
        run_dir = self.get_run_dir(run_id)
        path = run_dir / file_name
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ApiError("ARTIFACT_READ_ERROR", f"Cannot read artifact: {path}", status_code=500, details={"error": str(exc)}) from exc

    @staticmethod
    def _validate_run_id(run_id: str) -> None:
        if not run_id.startswith("pipeline-") or "/" in run_id or ".." in run_id:
            raise ApiError("INVALID_RUN_ID", f"Invalid run id: {run_id}", status_code=400)
