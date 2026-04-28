from __future__ import annotations

from fastapi import APIRouter, Depends

from codeui.config import Settings
from codeui.dependencies import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "app": settings.app.name, "version": settings.app.version}
