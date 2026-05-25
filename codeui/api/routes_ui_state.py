from __future__ import annotations

from fastapi import APIRouter, Depends

from codeui.dependencies import get_ui_state_service
from codeui.schemas.ui_state import SelectProjectRequest, SetRequirementsFileRequest, UiStateUpdate, UiStateView
from codeui.services.ui_state_service import UiStateService

router = APIRouter(prefix="/api/ui-state", tags=["ui-state"])


@router.get("", response_model=UiStateView)
def get_ui_state(service: UiStateService = Depends(get_ui_state_service)) -> UiStateView:
    return service.get_state()


@router.put("", response_model=UiStateView)
def update_ui_state(payload: UiStateUpdate, service: UiStateService = Depends(get_ui_state_service)) -> UiStateView:
    return service.update_state(payload)


@router.post("/select-project", response_model=UiStateView)
def select_project(payload: SelectProjectRequest, service: UiStateService = Depends(get_ui_state_service)) -> UiStateView:
    return service.update_state(UiStateUpdate(selected_project_id=payload.project_id))


@router.post("/requirements-file", response_model=UiStateView)
def set_requirements_file(payload: SetRequirementsFileRequest, service: UiStateService = Depends(get_ui_state_service)) -> UiStateView:
    return service.update_state(UiStateUpdate(requirements_file_path=payload.path))
