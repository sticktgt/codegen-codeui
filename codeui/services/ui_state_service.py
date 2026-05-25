from __future__ import annotations

from codeui.config import Settings
from codeui.logger import get_logger
from codeui.schemas.ui_state import UiStateUpdate, UiStateView
from codeui.services.json_io import read_json_file, write_json_file

LOGGER = get_logger(__name__)


class UiStateService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._path = settings.ui_state_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def get_state(self) -> UiStateView:
        if not self._path.exists():
            state = UiStateView(requirements_file_path=self._default_requirements_path())
            self.save_state(state)
            return state
        payload = read_json_file(self._path, error_code="UI_STATE_READ_ERROR")
        if not isinstance(payload, dict):
            payload = {}
        state = UiStateView.model_validate(payload)
        if not state.requirements_file_path:
            state.requirements_file_path = self._default_requirements_path()
        return state

    def update_state(self, update: UiStateUpdate) -> UiStateView:
        state = self.get_state()
        data = state.model_dump(mode="json")
        patch = update.model_dump(exclude_unset=True, mode="json")
        data.update(patch)
        updated = UiStateView.model_validate(data)
        self.save_state(updated)
        LOGGER.info(
            "UI state updated selected_project_id=%s requirements_file_path=%s",
            updated.selected_project_id,
            updated.requirements_file_path,
        )
        return updated

    def save_state(self, state: UiStateView) -> None:
        write_json_file(self._path, state.model_dump(mode="json"))

    def _default_requirements_path(self) -> str | None:
        for source in self._settings.requirements.sources:
            if source.enabled and source.type == "json_file":
                return str(self._settings.resolve_path(source.path))
        return None
