from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from codeui.config import Settings
from codeui.logger import get_logger
from codeui.services.command_runner import CommandRunner
from codeui.services.json_io import extract_json_from_stdout, write_json_file

LOGGER = get_logger(__name__)


class CodeCollectorClient:
    def __init__(self, settings: Settings, runner: CommandRunner | None = None) -> None:
        self._settings = settings
        self._runner = runner or CommandRunner(settings)

    def projects_list(self) -> Any:
        return self._run_json(["projects", "list"])

    def project_register(
        self,
        *,
        project_root: str,
        project_name: str | None = None,
        languages: list[str] | None = None,
        verification_commands: list[str] | None = None,
        index_excludes: list[str] | None = None,
        reference_library_paths: list[str] | None = None,
    ) -> Any:
        command = ["projects", "register", "--project-root", project_root]
        if project_name:
            command.extend(["--project-name", project_name])
        for language in languages or []:
            if language:
                command.extend(["--language", language])
        for item in verification_commands or []:
            if item:
                command.extend(["--verification-command", item])
        for item in index_excludes or []:
            if item:
                command.extend(["--index-exclude", item])
        for item in reference_library_paths or []:
            if item:
                command.extend(["--reference-library-path", item])
        return self._run_json(command)

    def sessions_list(self) -> Any:
        return self._run_json(["sessions", "list"])

    def session_get(self, session_id: str) -> Any:
        return self._run_json(["sessions", "get", "--session-id", session_id])

    def analyze_session(
        self,
        *,
        project_id: str,
        title: str,
        description: str,
        constraints: list[str],
        notes: list[str],
        operation: str | None = None,
        insert_scope: str | None = None,
        limit: int | None = None,
    ) -> Any:
        command = ["sessions", "analyze", "--project-id", project_id]
        if operation:
            command.extend(["--operation", operation])
        if insert_scope:
            command.extend(["--insert-scope", insert_scope])
        if limit is not None:
            command.extend(["--limit", str(limit)])

        # Через файл проще и безопаснее передавать длинные описания и будущие поля.
        payload = {"title": title, "description": description, "constraints": constraints, "notes": notes}
        with tempfile.TemporaryDirectory(prefix="codeui-cr-") as tmp:
            request_path = Path(tmp) / "change_request.json"
            write_json_file(request_path, payload)
            command.extend(["--change-request-file", str(request_path)])
            return self._run_json(command)

    def select_target(self, *, session_id: str, selected_qualname: str, operation: str | None = None, insert_scope: str | None = None) -> Any:
        command = ["sessions", "select-target", "--session-id", session_id, "--selected-qualname", selected_qualname]
        if operation:
            command.extend(["--operation", operation])
        if insert_scope:
            command.extend(["--insert-scope", insert_scope])
        return self._run_json(command)

    def generate_session(
        self,
        *,
        session_id: str,
        selected_qualname: str | None = None,
        operation: str | None = None,
        insert_scope: str | None = None,
        limit: int | None = None,
        disable_vector_search: bool = False,
    ) -> Any:
        command = ["sessions", "generate", "--session-id", session_id]
        if selected_qualname:
            command.extend(["--selected-qualname", selected_qualname])
        if operation:
            command.extend(["--operation", operation])
        if limit is not None:
            command.extend(["--limit", str(limit)])
        if disable_vector_search:
            command.append("--disable-vector-search")
        return self._run_json(command)

    def workspace_apply(self, workspace_id: str) -> Any:
        return self._run_json(["workspaces", "apply", "--workspace-id", workspace_id])

    def _run_json(self, args: list[str]) -> Any:
        command = [self._settings.codecollector.python, "-m", self._settings.codecollector.module, *args]
        result = self._runner.run(command, cwd=self._settings.codecollector_root)
        payload = extract_json_from_stdout(result.stdout)
        LOGGER.debug("codecollector command parsed JSON type=%s args=%s", type(payload).__name__, args)
        return payload
