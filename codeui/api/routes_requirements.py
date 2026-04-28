from __future__ import annotations

from fastapi import APIRouter, Depends

from codeui.dependencies import get_requirements_service
from codeui.schemas.requirements import RequirementListResponse, RequirementTreeResponse, RequirementView
from codeui.services.requirements_service import RequirementsService

router = APIRouter(prefix="/api/requirements", tags=["requirements"])


@router.get("", response_model=RequirementListResponse)
def list_requirements(service: RequirementsService = Depends(get_requirements_service)) -> RequirementListResponse:
    items = service.list_requirements()
    return RequirementListResponse(items=items, count=len(items))


@router.get("/tree", response_model=RequirementTreeResponse)
def requirement_tree(service: RequirementsService = Depends(get_requirements_service)) -> RequirementTreeResponse:
    roots = service.tree()
    flat_count = len(service.list_requirements())
    return RequirementTreeResponse(items=roots, count=flat_count)


@router.get("/{requirement_id}", response_model=RequirementView)
def get_requirement(requirement_id: str, service: RequirementsService = Depends(get_requirements_service)) -> RequirementView:
    return service.get_requirement(requirement_id)
