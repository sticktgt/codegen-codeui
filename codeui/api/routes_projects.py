from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from codeui.dependencies import get_codecollector_client
from codeui.services.codecollector_client import CodeCollectorClient

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectRegisterRequest(BaseModel):
    project_root: str
    project_name: str | None = None
    languages: list[str] = Field(default_factory=lambda: ["python"])
    verification_commands: list[str] = Field(default_factory=list)
    index_excludes: list[str] = Field(default_factory=list)
    reference_library_paths: list[str] = Field(default_factory=list)


@router.get("")
def list_projects(client: CodeCollectorClient = Depends(get_codecollector_client)) -> dict:
    items = client.projects_list()
    return {"items": items, "count": len(items) if isinstance(items, list) else None}


@router.post("/register")
def register_project(payload: ProjectRegisterRequest, client: CodeCollectorClient = Depends(get_codecollector_client)) -> dict:
    project = client.project_register(
        project_root=payload.project_root,
        project_name=payload.project_name,
        languages=payload.languages,
        verification_commands=payload.verification_commands,
        index_excludes=payload.index_excludes,
        reference_library_paths=payload.reference_library_paths,
    )
    return {"project": project}
