from __future__ import annotations

from fastapi import APIRouter, Depends

from codeui.config import Settings
from codeui.dependencies import get_settings
from codeui.schemas.settings import SettingsView

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsView)
def get_settings_view(settings: Settings = Depends(get_settings)) -> SettingsView:
    return SettingsView(
        app_name=settings.app.name,
        app_version=settings.app.version,
        codecollector_root=str(settings.codecollector_root),
        runs_root=str(settings.runs_root),
        state_root=str(settings.state_root),
        workspaces_root=str(settings.workspaces_root),
        change_requests_root=str(settings.change_requests_root),
        ui_state_path=str(settings.ui_state_path),
        requirements_sources=[item.model_dump(mode="json") for item in settings.requirements.sources],
        ui=settings.ui.model_dump(mode="json"),
    )
