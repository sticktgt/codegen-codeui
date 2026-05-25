from __future__ import annotations

from functools import lru_cache

from codeui.config import Settings, load_settings
from codeui.services.change_request_service import ChangeRequestService
from codeui.services.codecollector_client import CodeCollectorClient
from codeui.services.command_runner import CommandRunner
from codeui.services.requirements_service import RequirementsService
from codeui.services.run_artifact_service import RunArtifactService
from codeui.services.run_view_service import RunViewService
from codeui.services.project_lock_service import ProjectOperationLockService
from codeui.services.ui_state_service import UiStateService


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def get_codecollector_client() -> CodeCollectorClient:
    settings = get_settings()
    return CodeCollectorClient(settings, CommandRunner(settings))


def get_requirements_service() -> RequirementsService:
    settings = get_settings()
    return RequirementsService(settings, UiStateService(settings).get_state())


def get_change_request_service() -> ChangeRequestService:
    settings = get_settings()
    ui_state = UiStateService(settings).get_state()
    return ChangeRequestService(settings, RequirementsService(settings, ui_state))


def get_run_artifact_service() -> RunArtifactService:
    return RunArtifactService(get_settings())


def get_run_view_service() -> RunViewService:
    return RunViewService(get_run_artifact_service())


def get_ui_state_service() -> UiStateService:
    return UiStateService(get_settings())


def get_project_lock_service() -> ProjectOperationLockService:
    return ProjectOperationLockService(get_settings())
