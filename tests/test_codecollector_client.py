from __future__ import annotations

from pathlib import Path

import pytest

from codeui.config import CodeCollectorSettings, Settings
from codeui.errors import ApiError
from codeui.services.codecollector_client import CodeCollectorClient
from codeui.services.command_runner import CommandResult


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        timeout_sec: int | None = None,
        check_returncode: bool = True,
    ) -> CommandResult:
        self.commands.append(command)
        return CommandResult(
            command=command,
            cwd=cwd or Path.cwd(),
            returncode=0,
            stdout='{"ok": true}',
            stderr="",
            duration_sec=0.01,
        )


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        codecollector=CodeCollectorSettings(root_dir=tmp_path),
        config_path=tmp_path / "config.yaml",
        base_dir=tmp_path,
    )


def test_generate_session_passes_explicit_insert_scope_for_insert_after_symbol(tmp_path: Path) -> None:
    runner = RecordingRunner()
    client = CodeCollectorClient(make_settings(tmp_path), runner=runner)  # type: ignore[arg-type]

    client.generate_session(
        session_id="session-1",
        selected_qualname="sample.Repository",
        operation="insert_after_symbol",
        insert_scope="class_body",
    )

    command = runner.commands[-1]
    assert command == [
        "python",
        "-m",
        "codecollector",
        "sessions",
        "generate",
        "--session-id",
        "session-1",
        "--selected-qualname",
        "sample.Repository",
        "--operation",
        "insert_after_symbol",
        "--insert-scope",
        "class_body",
    ]


def test_generate_session_omits_insert_scope_for_replace_symbol(tmp_path: Path) -> None:
    runner = RecordingRunner()
    client = CodeCollectorClient(make_settings(tmp_path), runner=runner)  # type: ignore[arg-type]

    client.generate_session(
        session_id="session-1",
        selected_qualname="sample.Repository.save",
        operation="replace_symbol",
        insert_scope="class_body",
    )

    command = runner.commands[-1]
    assert "--insert-scope" not in command
    assert "class_body" not in command


def test_onboard_project_uses_new_projects_onboard_command(tmp_path: Path) -> None:
    runner = RecordingRunner()
    client = CodeCollectorClient(make_settings(tmp_path), runner=runner)  # type: ignore[arg-type]

    client.onboard_project(
        input_root="/repo/example",
        project_name="example_project",
        full=True,
        skip_architecture_enrichment=True,
    )

    assert runner.commands[-1] == [
        "python",
        "-m",
        "codecollector",
        "projects",
        "onboard",
        "--input-root",
        "/repo/example",
        "--project-name",
        "example_project",
        "--full",
        "--skip-architecture-enrichment",
    ]


def test_delete_project_uses_projects_delete_command(tmp_path: Path) -> None:
    runner = RecordingRunner()
    client = CodeCollectorClient(make_settings(tmp_path), runner=runner)  # type: ignore[arg-type]

    client.delete_project("proj-1")

    assert runner.commands[-1] == [
        "python",
        "-m",
        "codecollector",
        "projects",
        "delete",
        "--project-id",
        "proj-1",
    ]


def test_reindex_project_uses_projects_reindex_full_command(tmp_path: Path) -> None:
    runner = RecordingRunner()
    client = CodeCollectorClient(make_settings(tmp_path), runner=runner)  # type: ignore[arg-type]

    client.reindex_project("proj-1")

    assert runner.commands[-1] == [
        "python",
        "-m",
        "codecollector",
        "projects",
        "reindex",
        "--project-id",
        "proj-1",
        "--full",
    ]


def test_workspace_apply_passes_traceability_ids(tmp_path: Path) -> None:
    runner = RecordingRunner()
    client = CodeCollectorClient(make_settings(tmp_path), runner=runner)  # type: ignore[arg-type]

    client.workspace_apply(
        "workspace-1",
        change_request_id="CR-001",
        requirement_ids=["REQ-001", "REQ-002"],
    )

    assert runner.commands[-1] == [
        "python",
        "-m",
        "codecollector",
        "workspaces",
        "apply",
        "--workspace-id",
        "workspace-1",
        "--change-request-id",
        "CR-001",
        "--requirement-id",
        "REQ-001",
        "--requirement-id",
        "REQ-002",
    ]


class StaticRunner:
    def __init__(self, result: CommandResult) -> None:
        self.result = result
        self.commands: list[list[str]] = []

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        timeout_sec: int | None = None,
        check_returncode: bool = True,
    ) -> CommandResult:
        self.commands.append(command)
        return self.result


def test_workspace_apply_conflict_raises_409_api_error(tmp_path: Path) -> None:
    stdout = '{"status":"failed","error_type":"WorkspaceApplyConflictError","message":"blocked","details":{"guard":"workspace_base_hash","status":"blocked","reason":"project_changed_after_workspace_creation","workspace_id":"ws-1","conflicts":[{"file":"editor/editor_window.py","expected_sha256":"aaaabbbbccccdddd","actual_sha256":"eeeeffff11112222"}]}}'
    runner = StaticRunner(
        CommandResult(
            command=[],
            cwd=tmp_path,
            returncode=1,
            stdout=stdout,
            stderr="",
            duration_sec=0.01,
        )
    )
    client = CodeCollectorClient(make_settings(tmp_path), runner=runner)  # type: ignore[arg-type]

    with pytest.raises(ApiError) as exc_info:
        client.workspace_apply("ws-1")

    exc = exc_info.value
    assert exc.code == "WORKSPACE_APPLY_CONFLICT"
    assert exc.status_code == 409
    assert exc.details["guard"] == "workspace_base_hash"
    assert exc.details["conflicts"][0]["file"] == "editor/editor_window.py"
    assert exc.details["recommended_action"]


def test_workspace_apply_non_conflict_failure_still_raises_command_error(tmp_path: Path) -> None:
    runner = StaticRunner(
        CommandResult(
            command=[],
            cwd=tmp_path,
            returncode=1,
            stdout='{"status":"failed","error_type":"OtherError","message":"boom"}',
            stderr="boom",
            duration_sec=0.01,
        )
    )
    client = CodeCollectorClient(make_settings(tmp_path), runner=runner)  # type: ignore[arg-type]

    with pytest.raises(ApiError) as exc_info:
        client.workspace_apply("ws-1")

    assert exc_info.value.code == "CODECOLLECTOR_COMMAND_FAILED"
    assert exc_info.value.status_code == 502
