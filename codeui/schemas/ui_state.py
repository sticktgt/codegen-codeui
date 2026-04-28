from __future__ import annotations

from pydantic import BaseModel, Field


class UiStateView(BaseModel):
    selected_project_id: str | None = None
    requirements_file_path: str | None = None
    selected_requirement_ids: list[str] = Field(default_factory=list)
    selected_change_request_id: str | None = None


class UiStateUpdate(BaseModel):
    selected_project_id: str | None = None
    requirements_file_path: str | None = None
    selected_requirement_ids: list[str] | None = None
    selected_change_request_id: str | None = None


class SelectProjectRequest(BaseModel):
    project_id: str


class SetRequirementsFileRequest(BaseModel):
    path: str
