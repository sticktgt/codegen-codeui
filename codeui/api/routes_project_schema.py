from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from codeui.dependencies import get_codecollector_client, get_project_schema_service, get_ui_state_service
from codeui.errors import ApiError
from codeui.schemas.project_schema import ProjectSchemaResponse
from codeui.services.codecollector_client import CodeCollectorClient
from codeui.services.project_schema_service import ProjectSchemaService
from codeui.services.ui_state_service import UiStateService

router = APIRouter(prefix="/api/project-schema", tags=["project-schema"])


@router.get("", response_model=ProjectSchemaResponse)
def current_project_schema(
    ui_state_service: UiStateService = Depends(get_ui_state_service),
    client: CodeCollectorClient = Depends(get_codecollector_client),
    schema_service: ProjectSchemaService = Depends(get_project_schema_service),
) -> ProjectSchemaResponse:
    state = ui_state_service.get_state()
    if not state.selected_project_id:
        raise ApiError("PROJECT_SCHEMA_PROJECT_NOT_SELECTED", "Project is not selected", status_code=400)
    if not state.requirements_file_path:
        raise ApiError("PROJECT_SCHEMA_REQUIREMENTS_NOT_SELECTED", "Requirements file is not selected", status_code=400)
    project = _find_project(client.projects_list(), state.selected_project_id)
    if not project:
        raise ApiError("PROJECT_SCHEMA_PROJECT_NOT_FOUND", f"Project not found: {state.selected_project_id}", status_code=404)
    project_root = project.get("project_root") or project.get("root") or project.get("path")
    if not project_root:
        raise ApiError("PROJECT_SCHEMA_PROJECT_ROOT_MISSING", f"Project root is not available: {state.selected_project_id}", status_code=500)
    knowledge_path = Path(str(project_root)).expanduser().resolve() / ".codecollector" / "knowledge.yaml"
    return schema_service.build_from_files(
        knowledge_path=knowledge_path,
        requirements_path=state.requirements_file_path,
        project_id=state.selected_project_id,
        project_name=str(project.get("project_name") or project.get("name") or "") or None,
    )


def _find_project(items: Any, project_id: str) -> dict[str, Any] | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("project_id") == project_id:
            return item
    return None
