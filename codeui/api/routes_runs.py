from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from codeui.dependencies import get_run_view_service
from codeui.schemas.runs import ArtifactView, CheckView, DiffView, RunListResponse, RunSummaryView, StepView
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


@router.get("/{run_id}/raw")
def get_run_raw(run_id: str, service: RunViewService = Depends(get_run_view_service)) -> dict:
    return service.raw(run_id)
