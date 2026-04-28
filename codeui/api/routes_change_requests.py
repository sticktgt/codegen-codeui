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
    cr = service.get_change_request(cr_id)
    service.mark_processing(cr_id, "analyzing")
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
    service.mark_processing(cr_id, "selecting_target")
    try:
        result = client.select_target(session_id=cr.session_id, selected_qualname=payload.selected_qualname)
        updated = service.update_from_select_result(cr_id, result)
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
    if not cr.session_id:
        raise ApiError("SESSION_NOT_CREATED", "Сначала выполните анализ запроса.", status_code=409)
    service.mark_processing(cr_id, "running")
    try:
        result = client.generate_session(
            session_id=cr.session_id,
            selected_qualname=payload.selected_qualname,
            operation=payload.operation,
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
    result = client.workspace_apply(cr.last_workspace_id)
    updated = service.mark_applied(cr_id, result)
    return {"change_request": updated.model_dump(mode="json"), "apply_result": result}
