from __future__ import annotations

from fastapi import APIRouter, Depends

from codeui.dependencies import get_codecollector_client
from codeui.services.codecollector_client import CodeCollectorClient

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("/{workspace_id}/apply")
def apply_workspace(workspace_id: str, client: CodeCollectorClient = Depends(get_codecollector_client)) -> dict:
    return client.workspace_apply(workspace_id)
