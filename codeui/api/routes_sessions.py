from __future__ import annotations

from fastapi import APIRouter, Depends

from codeui.dependencies import get_codecollector_client
from codeui.services.codecollector_client import CodeCollectorClient

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
def list_sessions(client: CodeCollectorClient = Depends(get_codecollector_client)) -> dict:
    items = client.sessions_list()
    return {"items": items, "count": len(items) if isinstance(items, list) else None}


@router.get("/{session_id}")
def get_session(session_id: str, client: CodeCollectorClient = Depends(get_codecollector_client)) -> dict:
    return client.session_get(session_id)
