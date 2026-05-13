from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from codeui.dependencies import get_codecollector_client
from codeui.logger import get_logger
from codeui.services.codecollector_client import CodeCollectorClient

LOGGER = get_logger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectRegisterRequest(BaseModel):
    project_root: str
    project_name: str | None = None
    languages: list[str] = Field(default_factory=lambda: ["python"])
    verification_commands: list[str] = Field(default_factory=list)
    index_excludes: list[str] = Field(default_factory=list)
    reference_library_paths: list[str] = Field(default_factory=list)


class ProjectOnboardRequest(BaseModel):
    input_root: str
    project_name: str
    full: bool = True
    skip_architecture_enrichment: bool = False


class ProjectDeleteRequest(BaseModel):
    project_id: str


@router.get("")
def list_projects(client: CodeCollectorClient = Depends(get_codecollector_client)) -> dict[str, Any]:
    items = client.projects_list()
    return {"items": items, "count": len(items) if isinstance(items, list) else None}


@router.post("/register")
def register_project(payload: ProjectRegisterRequest, client: CodeCollectorClient = Depends(get_codecollector_client)) -> dict[str, Any]:
    project = client.project_register(
        project_root=payload.project_root,
        project_name=payload.project_name,
        languages=payload.languages,
        verification_commands=payload.verification_commands,
        index_excludes=payload.index_excludes,
        reference_library_paths=payload.reference_library_paths,
    )
    return {"project": project}


@router.post("/onboard")
def onboard_project(payload: ProjectOnboardRequest, client: CodeCollectorClient = Depends(get_codecollector_client)) -> dict[str, Any]:
    result = client.onboard_project(
        input_root=payload.input_root,
        project_name=payload.project_name,
        full=payload.full,
        skip_architecture_enrichment=payload.skip_architecture_enrichment,
    )
    LOGGER.info("project onboarding response: status=%s error_type=%s project_id=%s", result.get("status"), result.get("error_type"), result.get("project_id"))
    if result.get("status") == "failed":
        return _controlled_project_response(result)
    return {"ok": True, "result": result}


@router.post("/delete")
def delete_project(payload: ProjectDeleteRequest, client: CodeCollectorClient = Depends(get_codecollector_client)) -> dict[str, Any]:
    return _delete_project(payload.project_id, client)


@router.delete("/{project_id}")
def delete_project_by_id(project_id: str, client: CodeCollectorClient = Depends(get_codecollector_client)) -> dict[str, Any]:
    return _delete_project(project_id, client)


def _delete_project(project_id: str, client: CodeCollectorClient) -> dict[str, Any]:
    result = client.delete_project(project_id)
    LOGGER.info("project delete response: deleted=%s error_type=%s project_id=%s", result.get("deleted"), result.get("error_type"), result.get("project_id"))
    if result.get("status") == "failed":
        return _controlled_project_response(result)
    return {"ok": True, "result": result}


def _controlled_project_response(result: dict[str, Any]) -> dict[str, Any]:
    details = result.get("details") if isinstance(result.get("details"), dict) else {}
    return {
        "ok": False,
        "status": result.get("status", "failed"),
        "error_type": result.get("error_type"),
        "message": result.get("message") or result.get("error") or "Операция с проектом завершилась ошибкой.",
        "details": details,
        "result": result,
    }
