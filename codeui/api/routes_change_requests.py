from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from codeui.dependencies import get_change_request_service, get_codecollector_client, get_run_view_service, get_ui_state_service
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
from codeui.schemas.ui_state import UiStateUpdate
from codeui.services.change_request_service import ChangeRequestService
from codeui.services.codecollector_client import CodeCollectorClient
from codeui.services.run_view_service import RunViewService
from codeui.services.ui_state_service import UiStateService

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
    ui_state: UiStateService = Depends(get_ui_state_service),
) -> ChangeRequestView:
    created = service.create_change_request(payload)
    ui_state.update_state(UiStateUpdate(selected_change_request_id=created.cr_id))
    return created


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
    ui_state: UiStateService = Depends(get_ui_state_service),
) -> dict[str, str]:
    deleted = service.delete_change_request(cr_id)
    current = ui_state.get_state()
    if current.selected_change_request_id == cr_id:
        ui_state.update_state(UiStateUpdate(selected_change_request_id=None))
    return deleted


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
    cr = service.mark_processing(cr_id, "analyzing", requested_operation=payload.operation)
    try:
        result = client.analyze_session(
            project_id=cr.project_id,
            title=cr.title,
            description=cr.description,
            constraints=cr.constraints,
            notes=cr.notes,
            operation=cr.requested_operation,
            limit=payload.limit,
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
    operation = payload.operation or service.effective_operation(cr)
    if not operation:
        raise ApiError(
            "OPERATION_NOT_SELECTED",
            "Операция изменения не выбрана надежно. Выберите операцию вручную.",
            status_code=409,
            details={"cr_id": cr_id},
        )
    service.mark_processing(cr_id, "selecting_target")
    try:
        result = client.select_target(session_id=cr.session_id, selected_qualname=payload.selected_qualname, operation=operation)
        updated = service.update_from_select_result(cr_id, result, operation=operation)
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
    block_result = service.generation_block_result(cr, operation_override=payload.operation)
    if block_result is not None:
        updated = service.update_from_generate_result(cr_id, block_result)
        return {"change_request": updated.model_dump(mode="json"), "generate_result": block_result}

    operation = payload.operation or service.effective_operation(cr)
    selected_qualname = payload.selected_qualname or cr.selected_target or cr.recommended_target

    # A codecollector session becomes unsuitable for a repeated generate after a
    # completed run (for example verification_failed or ready_for_merge_review).
    # For UI repeat-run action we create a fresh analyze session for the current
    # CR fields, then select the known/recommended target before generation.
    reusable_session_statuses = {"analyzed", "needs_user_decision", "target_selected"}
    if not cr.session_id or cr.status not in reusable_session_statuses:
        service.mark_processing(cr_id, "analyzing", requested_operation=operation)
        try:
            analyze_result = client.analyze_session(
                project_id=cr.project_id,
                title=cr.title,
                description=cr.description,
                constraints=cr.constraints,
                notes=cr.notes,
                operation=operation,
                limit=None,
            )
            cr = service.update_from_analyze_result(cr_id, analyze_result)
        except Exception as exc:
            service.mark_failed(cr_id, error=exc, fallback_status="analysis_failed")
            raise

        block_result = service.generation_block_result(cr, operation_override=operation)
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
        service.mark_processing(cr_id, "selecting_target")
        try:
            select_result = client.select_target(session_id=cr.session_id, selected_qualname=selected_qualname, operation=operation)
            cr = service.update_from_select_result(cr_id, select_result, operation=operation)
        except Exception as exc:
            service.mark_failed(cr_id, error=exc, fallback_status="target_selection_failed")
            raise

    service.mark_processing(cr_id, "running", requested_operation=operation)
    try:
        result = client.generate_session(
            session_id=cr.session_id,
            selected_qualname=selected_qualname,
            operation=operation,
            limit=payload.limit,
            disable_vector_search=payload.disable_vector_search,
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
    if summary.merge_ready is not True:
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
    result = client.workspace_apply(cr.last_workspace_id)
    updated = service.mark_applied(cr_id, result)
    return {"change_request": updated.model_dump(mode="json"), "apply_result": result}
