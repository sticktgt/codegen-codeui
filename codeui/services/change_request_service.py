from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from codeui.config import Settings
from codeui.errors import ApiError
from codeui.logger import get_logger
from codeui.schemas.change_requests import ChangeRequestCreate, ChangeRequestUpdate, ChangeRequestView, RequirementSnapshot
from codeui.schemas.requirements import RequirementView
from codeui.services.json_io import read_json_file, write_json_file
from codeui.services.requirements_service import RequirementsService

LOGGER = get_logger(__name__)

FINAL_STATUSES = {"applied"}
PROCESSING_STATUSES = {"analyzing", "running", "selecting_target"}


class ChangeRequestService:
    def __init__(self, settings: Settings, requirements_service: RequirementsService | None = None) -> None:
        self._settings = settings
        self._requirements_service = requirements_service
        self._root = settings.change_requests_root
        self._root.mkdir(parents=True, exist_ok=True)

    def list_change_requests(self) -> list[ChangeRequestView]:
        items: list[ChangeRequestView] = []
        for path in sorted(self._root.glob("cr-*.json")):
            payload = read_json_file(path, error_code="CHANGE_REQUEST_READ_ERROR")
            items.append(ChangeRequestView.model_validate(payload))
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def get_change_request(self, cr_id: str) -> ChangeRequestView:
        path = self._path(cr_id)
        payload = read_json_file(path, error_code="CHANGE_REQUEST_NOT_FOUND")
        return ChangeRequestView.model_validate(payload)

    def create_change_request(self, request: ChangeRequestCreate) -> ChangeRequestView:
        now = datetime.now(timezone.utc)
        cr_id = f"cr-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:6]}"
        requirement_ids = self._normalize_requirement_ids(request.requirement_ids, request.requirement_id)
        code = request.code or self._next_code()
        self._ensure_code_unique(code)
        view = ChangeRequestView(
            cr_id=cr_id,
            code=code,
            project_id=request.project_id,
            requirement_id=requirement_ids[0] if requirement_ids else None,
            requirement_ids=requirement_ids,
            requirements_snapshot=self._build_requirement_snapshot(requirement_ids),
            title=request.title.strip(),
            description=request.description.strip(),
            constraints=request.constraints,
            notes=request.notes,
            requested_operation=request.requested_operation,
            status="draft",
            created_at=now,
            updated_at=now,
        )
        self._save(view)
        LOGGER.info("Created change request cr_id=%s project_id=%s requirement_ids=%s", cr_id, view.project_id, view.requirement_ids)
        return view

    def update_change_request(self, cr_id: str, request: ChangeRequestUpdate) -> ChangeRequestView:
        view = self.get_change_request(cr_id)
        self._ensure_not_final_for_edit(view)
        if view.status in PROCESSING_STATUSES:
            raise ApiError(
                "CHANGE_REQUEST_BUSY",
                "Нельзя изменить запрос, пока по нему выполняется действие.",
                status_code=409,
                details={"cr_id": cr_id, "status": view.status},
            )

        data = view.model_dump()
        patch = request.model_dump(exclude_unset=True)
        pipeline_input_fields = {"title", "description", "constraints", "notes", "requested_operation", "requirement_id", "requirement_ids"}
        should_reset_pipeline_state = any(
            key in patch and patch.get(key) != getattr(view, key)
            for key in pipeline_input_fields
        )
        if "code" in patch and patch.get("code") is not None:
            self._ensure_code_unique(str(patch["code"]), current_cr_id=cr_id)

        data.update({key: value for key, value in patch.items() if value is not None})
        if "requirement_ids" in patch or "requirement_id" in patch:
            requirement_ids = self._normalize_requirement_ids(data.get("requirement_ids") or [], data.get("requirement_id"))
            data["requirement_ids"] = requirement_ids
            data["requirement_id"] = requirement_ids[0] if requirement_ids else None
            data["requirements_snapshot"] = [item.model_dump(mode="json") for item in self._build_requirement_snapshot(requirement_ids)]

        if should_reset_pipeline_state:
            self._reset_pipeline_state(data)

        data["updated_at"] = datetime.now(timezone.utc)
        updated = ChangeRequestView.model_validate(data)
        self._save(updated)
        LOGGER.info(
            "Updated change request cr_id=%s fields=%s reset_pipeline_state=%s",
            cr_id,
            sorted(patch.keys()),
            should_reset_pipeline_state,
        )
        return updated

    def delete_change_request(self, cr_id: str) -> dict[str, str]:
        view = self.get_change_request(cr_id)
        if self.is_final(view):
            raise ApiError(
                "CHANGE_REQUEST_FINAL",
                "Нельзя удалить запрос: результат уже применен к основному проекту.",
                status_code=409,
                details={"cr_id": cr_id, "status": view.status, "applied_at": view.applied_at.isoformat() if view.applied_at else None},
            )
        if view.status in PROCESSING_STATUSES:
            raise ApiError(
                "CHANGE_REQUEST_BUSY",
                "Нельзя удалить запрос, пока по нему выполняется действие.",
                status_code=409,
                details={"cr_id": cr_id, "status": view.status},
            )
        path = self._path(cr_id)
        path.unlink(missing_ok=True)
        LOGGER.info("Deleted change request cr_id=%s status=%s", cr_id, view.status)
        return {"status": "deleted", "cr_id": cr_id}

    def list_for_requirement(self, requirement_id: str) -> list[ChangeRequestView]:
        return [item for item in self.list_change_requests() if requirement_id in item.requirement_ids]

    def list_runs_for_change_request(self, cr_id: str) -> list[str]:
        view = self.get_change_request(cr_id)
        return list(view.run_ids)

    def mark_processing(self, cr_id: str, status: str) -> ChangeRequestView:
        if status not in PROCESSING_STATUSES:
            raise ApiError("INVALID_PROCESSING_STATUS", f"Unsupported processing status: {status}", status_code=500)
        view = self.get_change_request(cr_id)
        if self.is_final(view):
            raise ApiError(
                "CHANGE_REQUEST_FINAL",
                "Запрос уже применен к основному проекту. Анализ, выбор места изменения и повторный запуск недоступны.",
                status_code=409,
                details={"cr_id": cr_id, "status": view.status, "applied_run_id": view.applied_run_id},
            )
        if view.status in PROCESSING_STATUSES:
            raise ApiError(
                "CHANGE_REQUEST_BUSY",
                "По этому запросу уже выполняется действие. Дождитесь завершения текущей операции.",
                status_code=409,
                details={"cr_id": cr_id, "status": view.status},
            )
        view.status = status
        view.updated_at = datetime.now(timezone.utc)
        self._save(view)
        return view

    def mark_failed(self, cr_id: str, *, error: Exception, fallback_status: str = "failed") -> ChangeRequestView:
        view = self.get_change_request(cr_id)
        view.status = fallback_status
        view.updated_at = datetime.now(timezone.utc)
        view.raw["last_error"] = {"type": error.__class__.__name__, "message": str(error)}
        self._save(view)
        LOGGER.warning("Marked change request as failed cr_id=%s error=%s", cr_id, error)
        return view

    def mark_applied(self, cr_id: str, result: dict[str, Any]) -> ChangeRequestView:
        view = self.get_change_request(cr_id)
        if self.is_final(view):
            raise ApiError(
                "CHANGE_REQUEST_FINAL",
                "Запрос уже применен к основному проекту.",
                status_code=409,
                details={"cr_id": cr_id, "status": view.status, "applied_run_id": view.applied_run_id},
            )
        if not view.last_run_id:
            raise ApiError("RUN_NOT_SELECTED", "У запроса нет последнего запуска для применения.", status_code=409)
        view.status = "applied"
        view.applied_at = datetime.now(timezone.utc)
        view.applied_run_id = view.last_run_id
        view.updated_at = datetime.now(timezone.utc)
        view.raw["last_apply_result"] = result
        self._save(view)
        return view

    def update_from_analyze_result(self, cr_id: str, result: dict[str, Any]) -> ChangeRequestView:
        view = self.get_change_request(cr_id)
        view.status = str(result.get("result_summary", {}).get("status") or result.get("status") or "analyzed")
        view.session_id = str(result.get("session_id")) if result.get("session_id") else view.session_id
        view.recommended_target = str(result.get("recommended_target")) if result.get("recommended_target") else view.recommended_target
        view.updated_at = datetime.now(timezone.utc)
        view.raw.pop("last_error", None)
        view.raw["last_analyze_result"] = result
        self._save(view)
        return view

    def update_from_select_result(self, cr_id: str, result: dict[str, Any]) -> ChangeRequestView:
        view = self.get_change_request(cr_id)
        summary = result.get("result_summary", {}) if isinstance(result.get("result_summary"), dict) else {}
        view.status = str(summary.get("status") or result.get("status") or "target_selected")
        view.selected_target = str(result.get("selected_target") or summary.get("selected_target") or view.selected_target)
        view.recommended_target = str(summary.get("recommended_target") or view.recommended_target) if summary.get("recommended_target") else view.recommended_target
        view.updated_at = datetime.now(timezone.utc)
        view.raw.pop("last_error", None)
        view.raw["last_select_result"] = result
        self._save(view)
        return view

    def update_from_generate_result(self, cr_id: str, result: dict[str, Any]) -> ChangeRequestView:
        view = self.get_change_request(cr_id)
        session = result.get("session") if isinstance(result.get("session"), dict) else {}
        summary = result.get("result_summary") if isinstance(result.get("result_summary"), dict) else {}
        view.status = str(session.get("status") or summary.get("status") or "generated")
        view.selected_target = str(result.get("selected_target") or summary.get("selected_target") or view.selected_target)
        run_id = result.get("run_id") or session.get("last_run_id") or view.last_run_id
        workspace_id = result.get("workspace_id") or session.get("last_workspace_id") or view.last_workspace_id
        view.last_run_id = str(run_id) if run_id else None
        view.last_workspace_id = str(workspace_id) if workspace_id else None
        if view.last_run_id and view.last_run_id not in view.run_ids:
            view.run_ids.append(view.last_run_id)
        view.updated_at = datetime.now(timezone.utc)
        view.raw.pop("last_error", None)
        view.raw["last_generate_result"] = result
        self._save(view)
        return view

    @staticmethod
    def is_final(view: ChangeRequestView) -> bool:
        return bool(view.applied_at or view.applied_run_id or str(view.status).lower() in FINAL_STATUSES)

    @staticmethod
    def _reset_pipeline_state(data: dict[str, Any]) -> None:
        """Reset analysis/selection/run state after editing CR input fields."""
        data["status"] = "draft"
        data["session_id"] = None
        data["recommended_target"] = None
        data["selected_target"] = None
        data["run_ids"] = []
        data["last_run_id"] = None
        data["last_workspace_id"] = None
        raw = data.get("raw") if isinstance(data.get("raw"), dict) else {}
        for key in (
            "last_analyze_result",
            "last_select_result",
            "last_generate_result",
            "last_error",
        ):
            raw.pop(key, None)
        raw["pipeline_state_reset_at"] = datetime.now(timezone.utc).isoformat()
        raw["pipeline_state_reset_reason"] = "change_request_fields_updated"
        data["raw"] = raw

    def _next_code(self) -> str:
        max_number = 0
        for path in self._root.glob("cr-*.json"):
            try:
                payload = read_json_file(path, error_code="CHANGE_REQUEST_READ_ERROR")
            except Exception:
                continue
            code = str(payload.get("code") or payload.get("cr_code") or "").strip()
            if not code.upper().startswith("CR-"):
                continue
            suffix = code[3:]
            if suffix.isdigit():
                max_number = max(max_number, int(suffix))
        return f"CR-{max_number + 1:06d}"

    def _ensure_code_unique(self, code: str, current_cr_id: str | None = None) -> None:
        normalized = code.strip().lower()
        for path in self._root.glob("cr-*.json"):
            try:
                payload = read_json_file(path, error_code="CHANGE_REQUEST_READ_ERROR")
            except Exception:
                continue
            if current_cr_id and payload.get("cr_id") == current_cr_id:
                continue
            existing = str(payload.get("code") or payload.get("cr_code") or "").strip().lower()
            if existing and existing == normalized:
                raise ApiError(
                    "CHANGE_REQUEST_CODE_EXISTS",
                    f"Код запроса уже используется: {code}",
                    status_code=409,
                    details={"code": code, "existing_cr_id": payload.get("cr_id")},
                )

    def _build_requirement_snapshot(self, requirement_ids: list[str]) -> list[RequirementSnapshot]:
        if not requirement_ids:
            return []
        found: dict[str, RequirementView] = {}
        if self._requirements_service is not None:
            try:
                found = {item.id: item for item in self._requirements_service.get_many_existing(requirement_ids)}
            except Exception as exc:  # noqa: BLE001 - CR should remain creatable even when requirement source is unavailable.
                LOGGER.warning("Cannot build full requirements snapshot: %s", exc)
        result: list[RequirementSnapshot] = []
        for item_id in requirement_ids:
            item = found.get(item_id)
            if item is None:
                result.append(RequirementSnapshot(id=item_id, title=item_id, missing=True))
            else:
                result.append(
                    RequirementSnapshot(
                        id=item.id,
                        title=item.title,
                        description=item.description,
                        type=item.type,
                        status=item.status,
                        priority=item.priority,
                        verification_status=item.verification_status,
                        source_id=item.source_id,
                        missing=False,
                    )
                )
        return result

    @staticmethod
    def _normalize_requirement_ids(requirement_ids: list[str], requirement_id: str | None) -> list[str]:
        result: list[str] = []
        for item_id in ([requirement_id] if requirement_id else []) + list(requirement_ids or []):
            if item_id and item_id not in result:
                result.append(str(item_id))
        return result

    def _ensure_not_final_for_edit(self, view: ChangeRequestView) -> None:
        if self.is_final(view):
            raise ApiError("CHANGE_REQUEST_FINAL", "Нельзя изменить запрос: результат уже применен к основному проекту.", status_code=409, details={"cr_id": view.cr_id, "status": view.status})

    def _save(self, view: ChangeRequestView) -> None:
        write_json_file(self._path(view.cr_id), view.model_dump(mode="json"))

    def _path(self, cr_id: str) -> Path:
        if "/" in cr_id or ".." in cr_id:
            raise ApiError("INVALID_CHANGE_REQUEST_ID", f"Invalid change request id: {cr_id}", status_code=400)
        return self._root / f"{cr_id}.json"
