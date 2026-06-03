from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from codeui.dependencies import get_change_request_service, get_codecollector_client, get_project_lock_service, get_run_view_service
from codeui.errors import ApiError
from codeui.schemas.change_requests import (
    AnalyzeRequest,
    ChangeRequestCreate,
    ChangeRequestListResponse,
    ChangeRequestUpdate,
    ChangeRequestView,
    GenerateRequest,
    SelectTargetRequest,
)
from codeui.schemas.runs import RunListItem, RunListResponse
from codeui.services.change_request_service import ChangeRequestService
from codeui.services.codecollector_client import CodeCollectorClient
from codeui.services.run_view_service import RunViewService
from codeui.services.project_lock_service import ProjectOperationLockService

router = APIRouter(prefix="/api/change-requests", tags=["change-requests"])


@router.get("", response_model=ChangeRequestListResponse)
def list_change_requests(
    requirement_id: str | None = Query(default=None),
    service: ChangeRequestService = Depends(get_change_request_service),
) -> ChangeRequestListResponse:
    items = service.list_for_requirement(requirement_id) if requirement_id else service.list_change_requests()
    return ChangeRequestListResponse(items=items, count=len(items))


@router.post("", response_model=ChangeRequestView)
def create_change_request(
    payload: ChangeRequestCreate,
    service: ChangeRequestService = Depends(get_change_request_service),
) -> ChangeRequestView:
    return service.create_change_request(payload)


@router.get("/{cr_id}", response_model=ChangeRequestView)
def get_change_request(cr_id: str, service: ChangeRequestService = Depends(get_change_request_service)) -> ChangeRequestView:
    return service.get_change_request(cr_id)


@router.put("/{cr_id}", response_model=ChangeRequestView)
def update_change_request(
    cr_id: str,
    payload: ChangeRequestUpdate,
    service: ChangeRequestService = Depends(get_change_request_service),
) -> ChangeRequestView:
    return service.update_change_request(cr_id, payload)


@router.delete("/{cr_id}")
def delete_change_request(
    cr_id: str,
    service: ChangeRequestService = Depends(get_change_request_service),
) -> dict[str, str]:
    return service.delete_change_request(cr_id)


@router.get("/{cr_id}/runs", response_model=RunListResponse)
def list_change_request_runs(
    cr_id: str,
    service: ChangeRequestService = Depends(get_change_request_service),
    run_service: RunViewService = Depends(get_run_view_service),
) -> RunListResponse:
    cr = service.get_change_request(cr_id)
    items: list[RunListItem] = []
    for run_id in cr.run_ids:
        try:
            items.append(run_service.summary_as_list_item(run_id))
        except Exception:
            items.append(RunListItem(run_id=run_id, status="недоступен"))
    return RunListResponse(items=items, count=len(items))


@router.post("/{cr_id}/analyze")
def analyze_change_request(
    cr_id: str,
    payload: AnalyzeRequest,
    service: ChangeRequestService = Depends(get_change_request_service),
    client: CodeCollectorClient = Depends(get_codecollector_client),
) -> dict:
    payload_operation = getattr(payload, "operation", None)
    payload_insert_scope = getattr(payload, "insert_scope", None)
    cr = service.mark_processing(cr_id, "analyzing", requested_operation=payload_operation, insert_scope=payload_insert_scope)
    try:
        result = client.analyze_session(
            project_id=cr.project_id,
            title=cr.title,
            description=cr.description,
            constraints=cr.constraints,
            notes=cr.notes,
            operation=cr.requested_operation,
            insert_scope=cr.insert_scope,
            limit=getattr(payload, "limit", None),
        )
        updated = service.update_from_analyze_result(cr_id, result)
        return {"change_request": updated.model_dump(mode="json"), "analyze_result": result}
    except Exception as exc:
        service.mark_failed(cr_id, error=exc, fallback_status="analysis_failed")
        raise


@router.post("/{cr_id}/select-target")
def select_target(
    cr_id: str,
    payload: SelectTargetRequest,
    service: ChangeRequestService = Depends(get_change_request_service),
    client: CodeCollectorClient = Depends(get_codecollector_client),
) -> dict:
    cr = service.get_change_request(cr_id)
    if not cr.session_id:
        raise ApiError("SESSION_NOT_CREATED", "Сначала выполните анализ запроса.", status_code=409)
    if service.request_quality_status(cr) == "insufficient":
        raise ApiError(
            "REQUEST_INSUFFICIENT",
            "Запрос недостаточно конкретный. Измените название, описание или ограничения и выполните анализ заново.",
            status_code=409,
            details={"cr_id": cr_id, "request_quality_status": "insufficient"},
        )
    payload_operation = getattr(payload, "operation", None)
    payload_insert_scope = getattr(payload, "insert_scope", None)
    operation = payload_operation or service.effective_operation(cr)
    if not operation:
        raise ApiError(
            "OPERATION_NOT_SELECTED",
            "Операция изменения не выбрана надежно. Выберите операцию вручную.",
            status_code=409,
            details={"cr_id": cr_id},
        )
    insert_scope = payload_insert_scope or service.effective_insert_scope(cr)
    if operation == "insert_after_symbol" and not insert_scope:
        raise ApiError(
            "INSERT_SCOPE_NOT_SELECTED",
            "Область вставки не выбрана. Для добавления кода выберите область вставки.",
            status_code=409,
            details={"cr_id": cr_id, "operation": operation},
        )
    service.mark_processing(cr_id, "selecting_target", insert_scope=insert_scope)
    try:
        result = client.select_target(session_id=cr.session_id, selected_qualname=payload.selected_qualname, operation=operation, insert_scope=insert_scope)
        updated = service.update_from_select_result(cr_id, result, operation=operation, insert_scope=insert_scope)
        return {"change_request": updated.model_dump(mode="json"), "select_result": result}
    except Exception as exc:
        service.mark_failed(cr_id, error=exc, fallback_status="target_selection_failed")
        raise


@router.post("/{cr_id}/run")
def run_change_request(
    cr_id: str,
    payload: GenerateRequest,
    service: ChangeRequestService = Depends(get_change_request_service),
    client: CodeCollectorClient = Depends(get_codecollector_client),
) -> dict:
    cr = service.get_change_request(cr_id)
    payload_operation = getattr(payload, "operation", None)
    payload_insert_scope = getattr(payload, "insert_scope", None)
    block_result = service.generation_block_result(cr, operation_override=payload_operation, insert_scope_override=payload_insert_scope)
    if block_result is not None:
        updated = service.update_from_generate_result(cr_id, block_result)
        return {"change_request": updated.model_dump(mode="json"), "generate_result": block_result}

    operation = payload_operation or service.effective_operation(cr)
    insert_scope = payload_insert_scope or service.effective_insert_scope(cr)
    selected_qualname = getattr(payload, "selected_qualname", None) or cr.selected_target or cr.recommended_target

    # A codecollector session becomes unsuitable for a repeated generate after a
    # completed run (for example verification_failed or ready_for_merge_review).
    # For UI repeat-run action we create a fresh analyze session for the current
    # CR fields, then select the known/recommended target before generation.
    reusable_session_statuses = {"analyzed", "needs_user_decision", "target_selected"}
    if not cr.session_id or cr.status not in reusable_session_statuses:
        service.mark_processing(cr_id, "analyzing", requested_operation=operation, insert_scope=insert_scope)
        try:
            analyze_result = client.analyze_session(
                project_id=cr.project_id,
                title=cr.title,
                description=cr.description,
                constraints=cr.constraints,
                notes=cr.notes,
                operation=operation,
                insert_scope=insert_scope,
                limit=None,
            )
            cr = service.update_from_analyze_result(cr_id, analyze_result)
        except Exception as exc:
            service.mark_failed(cr_id, error=exc, fallback_status="analysis_failed")
            raise

        block_result = service.generation_block_result(cr, operation_override=operation, insert_scope_override=insert_scope)
        if block_result is not None:
            updated = service.update_from_generate_result(cr_id, block_result)
            return {"change_request": updated.model_dump(mode="json"), "generate_result": block_result}
        selected_qualname = selected_qualname or cr.selected_target or cr.recommended_target

    if not selected_qualname:
        raise ApiError(
            "TARGET_NOT_SELECTED",
            "Место изменения не выбрано. Выберите кандидата или заполните место изменения вручную.",
            status_code=409,
            details={"cr_id": cr_id, "status": cr.status},
        )

    if cr.status != "target_selected":
        if operation == "insert_after_symbol" and not insert_scope:
            raise ApiError(
                "INSERT_SCOPE_NOT_SELECTED",
                "Область вставки не выбрана. Для добавления кода выберите область вставки.",
                status_code=409,
                details={"cr_id": cr_id, "operation": operation},
            )
        service.mark_processing(cr_id, "selecting_target", insert_scope=insert_scope)
        try:
            select_result = client.select_target(session_id=cr.session_id, selected_qualname=selected_qualname, operation=operation, insert_scope=insert_scope)
            cr = service.update_from_select_result(cr_id, select_result, operation=operation, insert_scope=insert_scope)
        except Exception as exc:
            service.mark_failed(cr_id, error=exc, fallback_status="target_selection_failed")
            raise

    service.mark_processing(cr_id, "running", requested_operation=operation, insert_scope=insert_scope)
    try:
        result = client.generate_session(
            session_id=cr.session_id,
            selected_qualname=selected_qualname,
            operation=operation,
            insert_scope=insert_scope,
            limit=getattr(payload, "limit", None),
            disable_vector_search=getattr(payload, "disable_vector_search", False),
        )
        updated = service.update_from_generate_result(cr_id, result)
        return {"change_request": updated.model_dump(mode="json"), "generate_result": result}
    except Exception as exc:
        service.mark_failed(cr_id, error=exc, fallback_status="run_failed")
        raise


@router.post("/{cr_id}/apply-last-run")
def apply_last_run(
    cr_id: str,
    service: ChangeRequestService = Depends(get_change_request_service),
    run_service: RunViewService = Depends(get_run_view_service),
    client: CodeCollectorClient = Depends(get_codecollector_client),
    locks: ProjectOperationLockService = Depends(get_project_lock_service),
) -> dict:
    cr = service.get_change_request(cr_id)
    if service.is_final(cr):
        raise ApiError(
            "CHANGE_REQUEST_FINAL",
            "Запрос уже применен к основному проекту.",
            status_code=409,
            details={"cr_id": cr_id, "status": cr.status, "applied_run_id": cr.applied_run_id},
        )
    if not cr.last_workspace_id or not cr.last_run_id:
        raise ApiError("WORKSPACE_NOT_SELECTED", "У запроса нет последнего результата для применения.", status_code=409)
    summary = run_service.summary(cr.last_run_id)
    manual_review_statuses = {"generated_test_generation_failed"}
    if summary.merge_ready is not True and str(summary.status or "").lower() not in manual_review_statuses:
        raise ApiError(
            "RUN_NOT_READY_FOR_APPLY",
            "Последний результат не готов к применению. Проверьте план применения и проверки запуска.",
            status_code=409,
            details={
                "cr_id": cr_id,
                "run_id": cr.last_run_id,
                "status": summary.status,
                "merge_ready": summary.merge_ready,
                "verification_passed": summary.verification_passed,
            },
        )
    with locks.acquire(cr.project_id, "apply_workspace", details={"cr_id": cr_id, "run_id": cr.last_run_id, "workspace_id": cr.last_workspace_id}):
        result = client.workspace_apply(cr.last_workspace_id)
    updated = service.mark_applied(cr_id, result)
    return {"change_request": updated.model_dump(mode="json"), "apply_result": result}
