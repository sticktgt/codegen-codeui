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
        pipeline_input_fields = {"title", "description", "constraints", "notes", "requested_operation", "insert_scope", "requirement_id", "requirement_ids"}
        should_reset_pipeline_state = any(
            key in patch and patch.get(key) != getattr(view, key)
            for key in pipeline_input_fields
        )
        if "code" in patch and patch.get("code") is not None:
            self._ensure_code_unique(str(patch["code"]), current_cr_id=cr_id)

        
        nullable_clear_fields = {"requested_operation", "insert_scope"}
        for key, value in patch.items():
            if value is not None or key in nullable_clear_fields:
                data[key] = value
        
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

    _UNSET = object()

    def mark_processing(self, cr_id: str, status: str, *, requested_operation: str | None | object = _UNSET, insert_scope: str | None | object = _UNSET) -> ChangeRequestView:
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
        if requested_operation is not self._UNSET:
            view.requested_operation = str(requested_operation) if requested_operation else None
            if view.raw is None or not isinstance(view.raw, dict):
                view.raw = {}
            view.raw["operation_selection_source"] = "user" if requested_operation else "none"
        if insert_scope is not self._UNSET:
            normalized_insert_scope = self._normalize_insert_scope(insert_scope)
            view.insert_scope = normalized_insert_scope
            if view.raw is None or not isinstance(view.raw, dict):
                view.raw = {}
            view.raw["insert_scope_selection_source"] = "user" if normalized_insert_scope else "none"
        if status == "analyzing":
            self._clear_analysis_state(view)
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

    def mark_applied(
        self,
        cr_id: str,
        result: dict[str, Any],
        *,
        run_id: str | None = None,
        workspace_id: str | None = None,
    ) -> ChangeRequestView:
        view = self.get_change_request(cr_id)
        if self.is_final(view):
            raise ApiError(
                "CHANGE_REQUEST_FINAL",
                "Запрос уже применен к основному проекту.",
                status_code=409,
                details={"cr_id": cr_id, "status": view.status, "applied_run_id": view.applied_run_id},
            )
        applied_run_id = run_id or view.last_run_id
        if not applied_run_id:
            raise ApiError("RUN_NOT_SELECTED", "У запроса нет запуска для применения.", status_code=409)
        view.status = "applied"
        view.applied_at = datetime.now(timezone.utc)
        view.applied_run_id = applied_run_id
        view.updated_at = datetime.now(timezone.utc)
        view.raw["last_apply_result"] = result
        view.raw["applied_run_id"] = applied_run_id
        if workspace_id:
            view.raw["applied_workspace_id"] = workspace_id
        self._save(view)
        return view

    def update_from_analyze_result(self, cr_id: str, result: dict[str, Any]) -> ChangeRequestView:
        view = self.get_change_request(cr_id)
        summary = result.get("result_summary") if isinstance(result.get("result_summary"), dict) else {}
        quality = result.get("request_quality") if isinstance(result.get("request_quality"), dict) else {}
        recommendation = result.get("target_recommendation") if isinstance(result.get("target_recommendation"), dict) else {}

        result_status = str(summary.get("status") or result.get("status") or "analyzed")
        quality_status = str(summary.get("request_quality_status") or quality.get("status") or "").strip()
        if quality_status == "insufficient":
            view.status = "analysis_insufficient"
        elif result_status == "needs_user_decision":
            view.status = "needs_user_decision"
        else:
            view.status = result_status

        view.session_id = str(result.get("session_id")) if result.get("session_id") else view.session_id
        recommended_target = result.get("recommended_target") or summary.get("recommended_target") or recommendation.get("recommended_target")
        view.recommended_target = str(recommended_target) if recommended_target else None
        view.selected_target = None

        operation = result.get("requested_operation") or summary.get("requested_operation") or recommendation.get("recommended_operation")
        operation_source = str(result.get("operation_source") or summary.get("operation_source") or "")
        if operation in {"replace_symbol", "insert_after_symbol"} and operation_source != "fallback":
            view.requested_operation = str(operation)
            view.raw["operation_selection_source"] = "user" if operation_source == "user" else "analysis"
        else:
            view.requested_operation = None
            view.raw["operation_selection_source"] = "fallback" if operation_source == "fallback" else "none"

        search_plan = result.get("search_plan") if isinstance(result.get("search_plan"), dict) else {}
        post_processing = recommendation.get("post_processing") if isinstance(recommendation.get("post_processing"), dict) else {}
        insert_scope = self._normalize_insert_scope(
            result.get("insert_scope"),
            summary.get("insert_scope"),
            recommendation.get("insert_scope"),
            search_plan.get("insert_scope"),
            post_processing.get("insert_scope"),
        )
        if insert_scope:
            view.insert_scope = insert_scope
            view.raw["insert_scope_selection_source"] = "analysis"
        elif view.requested_operation != "insert_after_symbol":
            view.insert_scope = None
            view.raw["insert_scope_selection_source"] = "none"

        view.updated_at = datetime.now(timezone.utc)
        view.raw.pop("last_error", None)
        view.raw.pop("last_select_result", None)
        view.raw["last_analyze_result"] = result
        self._save(view)
        return view

    def update_from_select_result(self, cr_id: str, result: dict[str, Any], *, operation: str | None = None, insert_scope: str | None = None) -> ChangeRequestView:
        view = self.get_change_request(cr_id)
        summary = result.get("result_summary", {}) if isinstance(result.get("result_summary"), dict) else {}
        view.status = str(summary.get("status") or result.get("status") or "target_selected")
        view.selected_target = str(result.get("selected_target") or summary.get("selected_target") or view.selected_target)
        view.recommended_target = str(summary.get("recommended_target") or view.recommended_target) if summary.get("recommended_target") else view.recommended_target
        if operation:
            view.requested_operation = operation  # operation confirmed for this target selection
            view.raw["operation_selection_source"] = "user"
        select_summary = result.get("result_summary") if isinstance(result.get("result_summary"), dict) else {}
        result_insert_scope = self._normalize_insert_scope(insert_scope, result.get("insert_scope"), select_summary.get("insert_scope"))
        if result_insert_scope:
            view.insert_scope = result_insert_scope
            view.raw["insert_scope_selection_source"] = "user" if insert_scope else "codecollector"
        elif operation != "insert_after_symbol":
            view.insert_scope = None
            view.raw["insert_scope_selection_source"] = "none"
        view.updated_at = datetime.now(timezone.utc)
        view.raw.pop("last_error", None)
        view.raw["last_select_result"] = result
        self._save(view)
        return view

    def update_from_generate_result(self, cr_id: str, result: dict[str, Any]) -> ChangeRequestView:
        view = self.get_change_request(cr_id)
        session = result.get("session") if isinstance(result.get("session"), dict) else {}
        summary = result.get("result_summary") if isinstance(result.get("result_summary"), dict) else {}
        if summary.get("generation_blocked"):
            view.status = str(summary.get("status") or "generation_blocked")
            view.raw["last_generate_result"] = result
            view.updated_at = datetime.now(timezone.utc)
            self._save(view)
            return view

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

    def request_quality_status(self, view: ChangeRequestView) -> str | None:
        analyze = self._last_analyze_result(view)
        summary = analyze.get("result_summary") if isinstance(analyze.get("result_summary"), dict) else {}
        quality = analyze.get("request_quality") if isinstance(analyze.get("request_quality"), dict) else {}
        status = summary.get("request_quality_status") or quality.get("status")
        return str(status) if status else None

    def effective_operation(self, view: ChangeRequestView) -> str | None:
        if view.requested_operation:
            return view.requested_operation
        analyze = self._last_analyze_result(view)
        operation = analyze.get("requested_operation")
        source = str(analyze.get("operation_source") or "")
        if operation in {"replace_symbol", "insert_after_symbol"} and source != "fallback":
            return str(operation)
        return None

    def effective_insert_scope(self, view: ChangeRequestView) -> str | None:
        if view.insert_scope:
            return view.insert_scope
        analyze = self._last_analyze_result(view)
        summary = analyze.get("result_summary") if isinstance(analyze.get("result_summary"), dict) else {}
        recommendation = analyze.get("target_recommendation") if isinstance(analyze.get("target_recommendation"), dict) else {}
        post_processing = recommendation.get("post_processing") if isinstance(recommendation.get("post_processing"), dict) else {}
        search_plan = analyze.get("search_plan") if isinstance(analyze.get("search_plan"), dict) else {}
        return self._normalize_insert_scope(
            analyze.get("insert_scope"),
            summary.get("insert_scope"),
            recommendation.get("insert_scope"),
            search_plan.get("insert_scope"),
            post_processing.get("insert_scope"),
        )

    @staticmethod
    def _normalize_insert_scope(*values: Any) -> str | None:
        """Return canonical insert_scope from strings or analyzer objects.

        codecollector may return insert_scope either as a plain string
        ("module_body" / "class_body") or as an object like
        {"value": "class_body", "confidence": 0.9, "reason": "..."}.
        UI state stores only the canonical string.
        """
        allowed = {"module_body", "class_body"}
        for value in values:
            candidate = value
            if isinstance(candidate, dict):
                candidate = candidate.get("value")
            if isinstance(candidate, str):
                normalized = candidate.strip()
                if normalized in allowed:
                    return normalized
        return None

    def generation_block_result(self, view: ChangeRequestView, *, operation_override: str | None = None, insert_scope_override: str | None = None) -> dict[str, Any] | None:
        quality_status = self.request_quality_status(view)
        analyze = self._last_analyze_result(view)
        quality = analyze.get("request_quality") if isinstance(analyze.get("request_quality"), dict) else {}
        if quality_status == "insufficient":
            summary = {
                "status": "needs_user_decision",
                "generation_blocked": True,
                "block_reason": "insufficient_request",
                "message": "Запрос недостаточно конкретный. Измените название, описание или ограничения и выполните анализ заново.",
                "request_quality_status": "insufficient",
                "missing_information": list(quality.get("missing_information") or []),
                "recommended_action": "rewrite_request_and_run_analyze_again",
                "selected_target": view.selected_target,
                "requested_operation": self.effective_operation(view),
            }
            return {"pipeline_result": None, "result_summary": summary}

        effective_operation = operation_override or self.effective_operation(view)
        if not effective_operation:
            summary = {
                "status": "needs_user_decision",
                "generation_blocked": True,
                "block_reason": "operation_not_selected",
                "message": "Операция изменения не выбрана. Выберите операцию и выполните выбор места изменения.",
                "request_quality_status": quality_status,
                "missing_information": [],
                "recommended_action": "select_operation_and_target",
                "selected_target": view.selected_target,
                "requested_operation": None,
            }
            return {"pipeline_result": None, "result_summary": summary}
        effective_insert_scope = insert_scope_override or self.effective_insert_scope(view)
        if effective_operation == "insert_after_symbol" and not effective_insert_scope:
            summary = {
                "status": "needs_user_decision",
                "generation_blocked": True,
                "block_reason": "insert_scope_not_selected",
                "message": "Область вставки не выбрана. Для добавления кода выберите область вставки: модуль или тело класса.",
                "request_quality_status": quality_status,
                "missing_information": ["область вставки: module_body или class_body"],
                "recommended_action": "select_insert_scope_and_target",
                "selected_target": view.selected_target,
                "requested_operation": effective_operation,
                "insert_scope": None,
            }
            return {"pipeline_result": None, "result_summary": summary}
        return None


    @staticmethod
    def _clear_analysis_state(view: ChangeRequestView) -> None:
        """Clear stale analysis/selection/current run before a new analyze call.

        Historical run_ids are kept as CR history, but the last run/workspace is
        cleared so an old result cannot be applied after a new analysis starts.
        """
        view.session_id = None
        view.recommended_target = None
        view.selected_target = None
        view.last_run_id = None
        view.last_workspace_id = None
        raw = view.raw if isinstance(view.raw, dict) else {}
        for key in (
            "last_analyze_result",
            "last_select_result",
            "last_generate_result",
            "last_error",
        ):
            raw.pop(key, None)
        raw["analysis_state_cleared_at"] = datetime.now(timezone.utc).isoformat()
        raw["analysis_state_clear_reason"] = "new_analyze_started"
        view.raw = raw

    @staticmethod
    def _last_analyze_result(view: ChangeRequestView) -> dict[str, Any]:
        value = view.raw.get("last_analyze_result") if isinstance(view.raw, dict) else None
        return value if isinstance(value, dict) else {}

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
