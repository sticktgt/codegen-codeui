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

    def onboard_project(
        self,
        *,
        input_root: str,
        project_name: str,
        full: bool = True,
        skip_architecture_enrichment: bool = False,
    ) -> dict[str, Any]:
        command = ["projects", "onboard", "--input-root", input_root, "--project-name", project_name]
        if full:
            command.append("--full")
        if skip_architecture_enrichment:
            command.append("--skip-architecture-enrichment")
        payload = self._run_json(command, allow_nonzero_json=True)
        return payload if isinstance(payload, dict) else {"status": "failed", "message": "Unexpected codecollector response", "raw": payload}

    def delete_project(self, project_id: str) -> dict[str, Any]:
        payload = self._run_json(["projects", "delete", "--project-id", project_id], allow_nonzero_json=True)
        return payload if isinstance(payload, dict) else {"status": "failed", "message": "Unexpected codecollector response", "raw": payload}

    def reindex_project(self, project_id: str) -> dict[str, Any]:
        payload = self._run_json(["projects", "reindex", "--project-id", project_id, "--full"], allow_nonzero_json=True)
        return payload if isinstance(payload, dict) else {"status": "failed", "message": "Unexpected codecollector response", "raw": payload}

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
        if insert_scope and operation != "replace_symbol":
            command.extend(["--insert-scope", insert_scope])
        if limit is not None:
            command.extend(["--limit", str(limit)])
        if disable_vector_search:
            command.append("--disable-vector-search")
        return self._run_json(command)

    def workspace_apply(
        self,
        workspace_id: str,
        *,
        change_request_id: str | None = None,
        requirement_ids: list[str] | None = None,
    ) -> Any:
        command = ["workspaces", "apply", "--workspace-id", workspace_id]
        if change_request_id:
            command.extend(["--change-request-id", change_request_id])
        for requirement_id in requirement_ids or []:
            if requirement_id:
                command.extend(["--requirement-id", requirement_id])
        return self._run_json(command)

    def _run_json(self, args: list[str], *, allow_nonzero_json: bool = False) -> Any:
        command = [self._settings.codecollector.python, "-m", self._settings.codecollector.module, *args]
        result = self._runner.run(command, cwd=self._settings.codecollector_root, check_returncode=not allow_nonzero_json)
        payload = extract_json_from_stdout(result.stdout)
        if allow_nonzero_json and isinstance(payload, dict) and result.returncode != 0:
            payload.setdefault("status", "failed")
            payload.setdefault("error_type", "CodeCollectorCommandFailed")
            payload.setdefault("message", "codecollector command failed")
            payload.setdefault("_codeui_command", {})
            payload["_codeui_command"].update(
                {
                    "returncode": result.returncode,
                    "duration_sec": result.duration_sec,
                    "stderr_tail": result.stderr[-4000:],
                    "stdout_tail": result.stdout[-4000:],
                }
            )
        LOGGER.debug(
            "codecollector command parsed JSON type=%s returncode=%s args=%s",
            type(payload).__name__,
            result.returncode,
            args,
        )
        return payload
