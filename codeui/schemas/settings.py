from __future__ import annotations

from pydantic import BaseModel


class SettingsView(BaseModel):
    app_name: str
    app_version: str
    codecollector_root: str
    runs_root: str
    state_root: str
    workspaces_root: str
    change_requests_root: str
    ui_state_path: str
    requirements_sources: list[dict]
    ui: dict
