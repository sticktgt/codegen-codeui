from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from codeui.dependencies import get_change_request_service, get_codecollector_client, get_run_view_service
from codeui.errors import ApiError
from codeui.schemas.runs import ArtifactView, CheckView, DiffView, RunListResponse, RunSummaryView, StepView
from codeui.services.change_request_service import ChangeRequestService
from codeui.services.codecollector_client import CodeCollectorClient
from codeui.services.run_view_service import RunViewService

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=RunListResponse)
def list_runs(
    limit: int | None = Query(default=50, ge=1, le=5000),
    include_all: bool = Query(default=False, alias="all"),
    service: RunViewService = Depends(get_run_view_service),
) -> RunListResponse:
    items = service.list_runs(limit=None if include_all else limit)
    return RunListResponse(items=items, count=len(items))


@router.get("/{run_id}/summary", response_model=RunSummaryView)
def get_run_summary(run_id: str, service: RunViewService = Depends(get_run_view_service)) -> RunSummaryView:
    return service.summary(run_id)


@router.get("/{run_id}/steps", response_model=list[StepView])
def get_run_steps(run_id: str, service: RunViewService = Depends(get_run_view_service)) -> list[StepView]:
    return service.steps(run_id)


@router.get("/{run_id}/checks", response_model=list[CheckView])
def get_run_checks(run_id: str, service: RunViewService = Depends(get_run_view_service)) -> list[CheckView]:
    return service.checks(run_id)


@router.get("/{run_id}/diff", response_model=DiffView)
def get_run_diff(run_id: str, service: RunViewService = Depends(get_run_view_service)) -> DiffView:
    return service.diff(run_id)


@router.get("/{run_id}/code", response_model=ArtifactView)
def get_run_code(run_id: str, service: RunViewService = Depends(get_run_view_service)) -> ArtifactView:
    return service.code_artifact(run_id)


@router.get("/{run_id}/test", response_model=ArtifactView)
def get_run_test(run_id: str, service: RunViewService = Depends(get_run_view_service)) -> ArtifactView:
    return service.test_artifact(run_id)




@router.post("/{run_id}/apply")
def apply_run(
    run_id: str,
    service: RunViewService = Depends(get_run_view_service),
    change_requests: ChangeRequestService = Depends(get_change_request_service),
    client: CodeCollectorClient = Depends(get_codecollector_client),
) -> dict:
    summary = service.summary(run_id)
    if summary.merge_ready is not True:
        raise ApiError(
            "RUN_NOT_READY_FOR_APPLY",
            "Выбранный запуск не готов к применению. Проверьте план применения и проверки запуска.",
            status_code=409,
            details={
                "run_id": run_id,
                "status": summary.status,
                "merge_ready": summary.merge_ready,
                "verification_passed": summary.verification_passed,
            },
        )
    if not summary.workspace_id:
        raise ApiError(
            "WORKSPACE_NOT_SELECTED",
            "У выбранного запуска нет workspace-id для применения.",
            status_code=409,
            details={"run_id": run_id, "workspace_path": summary.workspace_path},
        )

    linked_cr = next(
        (item for item in change_requests.list_change_requests() if run_id in item.run_ids or item.last_run_id == run_id),
        None,
    )
    if linked_cr and change_requests.is_final(linked_cr):
        raise ApiError(
            "CHANGE_REQUEST_FINAL",
            "Связанный запрос уже применен к основному проекту.",
            status_code=409,
            details={
                "cr_id": linked_cr.cr_id,
                "status": linked_cr.status,
                "applied_run_id": linked_cr.applied_run_id,
            },
        )

    result = client.workspace_apply(summary.workspace_id)
    response: dict = {"run_id": run_id, "workspace_id": summary.workspace_id, "apply_result": result}
    if linked_cr:
        updated = change_requests.mark_applied(
            linked_cr.cr_id,
            result,
            run_id=run_id,
            workspace_id=summary.workspace_id,
        )
        response["change_request"] = updated.model_dump(mode="json")
    return response


@router.get("/{run_id}/raw")
def get_run_raw(run_id: str, service: RunViewService = Depends(get_run_view_service)) -> dict:
    return service.raw(run_id)
