from __future__ import annotations

import sys
from pathlib import Path

from codeui.config import CodeCollectorSettings, CommandTraceSettings, Settings
from codeui.services.command_runner import CommandRunner


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        codecollector=CodeCollectorSettings(root_dir=tmp_path),
        command_trace=CommandTraceSettings(storage_dir=Path("trace")),
        config_path=tmp_path / "config.yaml",
        base_dir=tmp_path,
    )


def test_command_runner_writes_only_stdout_and_stderr_trace(tmp_path: Path) -> None:
    runner = CommandRunner(make_settings(tmp_path))

    result = runner.run(
        [
            sys.executable,
            "-c",
            "import sys; print('stdout text'); print('stderr text', file=sys.stderr)",
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert result.stdout_trace_path is not None
    assert result.stderr_trace_path is not None
    assert result.stdout_trace_path.read_text(encoding="utf-8").strip() == "stdout text"
    assert result.stderr_trace_path.read_text(encoding="utf-8").strip() == "stderr text"
    assert not list((tmp_path / "trace").glob("*.meta.json"))


def test_command_runner_does_not_trace_projects_list(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    runner = CommandRunner(settings)

    result = runner.run(
        [
            sys.executable,
            "-c",
            "print('projects list')",
            "-m",
            settings.codecollector.module,
            "projects",
            "list",
        ],
        cwd=tmp_path,
        check_returncode=False,
    )

    assert result.stdout_trace_path is None
    assert result.stderr_trace_path is None
    assert not (tmp_path / "trace").exists()
