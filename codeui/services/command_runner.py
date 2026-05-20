from __future__ import annotations

import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codeui.config import Settings
from codeui.errors import ApiError
from codeui.logger import get_logger

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str
    duration_sec: float
    stdout_trace_path: Path | None = None
    stderr_trace_path: Path | None = None


@dataclass(frozen=True)
class CommandTracePaths:
    stdout: Path | None = None
    stderr: Path | None = None


class CommandRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        timeout_sec: int | None = None,
        check_returncode: bool = True,
    ) -> CommandResult:
        effective_cwd = cwd or self._settings.codecollector_root
        timeout = timeout_sec or self._settings.codecollector.command_timeout_sec
        start = time.monotonic()
        safe_command = self._safe_command(command)
        LOGGER.info("Running command: cwd=%s command=%s", effective_cwd, safe_command)
        try:
            completed = subprocess.run(
                command,
                cwd=str(effective_cwd),
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            stdout = self._normalize_process_output(exc.stdout)
            stderr = self._normalize_process_output(exc.stderr)
            trace_paths = self._write_command_trace(
                command=safe_command,
                cwd=effective_cwd,
                returncode=None,
                duration_sec=duration,
                stdout=stdout,
                stderr=stderr,
                error_type="timeout",
                error_message=f"Command timed out after {timeout} seconds",
            )
            LOGGER.error(
                "Command timeout after %.2fs: %s trace=%s",
                duration,
                safe_command,
                self._trace_paths_for_log(trace_paths),
            )
            raise ApiError(
                "CODECOLLECTOR_TIMEOUT",
                "codecollector command timed out",
                status_code=504,
                details={
                    "command": safe_command,
                    "timeout_sec": timeout,
                    "duration_sec": duration,
                    "stdout_trace_path": str(trace_paths.stdout) if trace_paths.stdout else None,
                    "stderr_trace_path": str(trace_paths.stderr) if trace_paths.stderr else None,
                },
            ) from exc
        except OSError as exc:
            duration = time.monotonic() - start
            trace_paths = self._write_command_trace(
                command=safe_command,
                cwd=effective_cwd,
                returncode=None,
                duration_sec=duration,
                stdout="",
                stderr="",
                error_type="start_failed",
                error_message=str(exc),
            )
            LOGGER.exception(
                "Command failed to start after %.2fs: %s trace=%s",
                duration,
                safe_command,
                self._trace_paths_for_log(trace_paths),
            )
            raise ApiError(
                "CODECOLLECTOR_COMMAND_START_FAILED",
                "Failed to start codecollector command",
                status_code=500,
                details={
                    "command": safe_command,
                    "error": str(exc),
                },
            ) from exc

        duration = time.monotonic() - start
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        trace_paths = self._write_command_trace(
            command=safe_command,
            cwd=effective_cwd,
            returncode=completed.returncode,
            duration_sec=duration,
            stdout=stdout,
            stderr=stderr,
        )
        LOGGER.info(
            "Command finished: returncode=%s duration=%.2fs stdout_chars=%s stderr_chars=%s trace=%s command=%s",
            completed.returncode,
            duration,
            len(stdout),
            len(stderr),
            self._trace_paths_for_log(trace_paths),
            safe_command,
        )
        result = CommandResult(
            command=command,
            cwd=effective_cwd,
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            duration_sec=duration,
            stdout_trace_path=trace_paths.stdout,
            stderr_trace_path=trace_paths.stderr,
        )
        if check_returncode and completed.returncode != 0:
            raise ApiError(
                "CODECOLLECTOR_COMMAND_FAILED",
                "codecollector command failed",
                status_code=502,
                details={
                    "command": safe_command,
                    "cwd": str(effective_cwd),
                    "returncode": completed.returncode,
                    "duration_sec": duration,
                    "stderr_tail": result.stderr[-4000:],
                    "stdout_tail": result.stdout[-4000:],
                    "stdout_trace_path": str(result.stdout_trace_path) if result.stdout_trace_path else None,
                    "stderr_trace_path": str(result.stderr_trace_path) if result.stderr_trace_path else None,
                },
            )
        return result

    def _write_command_trace(
        self,
        *,
        command: list[str],
        cwd: Path,
        returncode: int | None,
        duration_sec: float,
        stdout: str,
        stderr: str,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> CommandTracePaths:
        trace_settings = self._settings.command_trace
        if not trace_settings.enabled or self._is_untraced_command(command):
            return CommandTracePaths()

        trace_root = self._settings.command_trace_root
        trace_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        label = self._command_label(command)
        base_name = f"{timestamp}_{label}_{uuid.uuid4().hex[:8]}"

        stdout_path: Path | None = None
        stderr_path: Path | None = None
        if trace_settings.save_stdout:
            stdout_path = trace_root / f"{base_name}.stdout.txt"
            stdout_path.write_text(stdout, encoding="utf-8")
        if trace_settings.save_stderr:
            stderr_path = trace_root / f"{base_name}.stderr.txt"
            stderr_path.write_text(stderr, encoding="utf-8")
        return CommandTracePaths(stdout=stdout_path, stderr=stderr_path)

    def _is_untraced_command(self, command: list[str]) -> bool:
        try:
            module_index = command.index("-m")
        except ValueError:
            return False

        after_module = command[module_index + 1 :]
        return len(after_module) >= 3 and after_module[:3] == [
            self._settings.codecollector.module,
            "projects",
            "list",
        ]

    def _command_label(self, command: list[str]) -> str:
        parts = self._command_label_parts(command)
        raw_label = "-".join(parts) if parts else "command"
        sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw_label).strip("-._") or "command"
        max_chars = self._settings.command_trace.filename_label_max_chars
        return sanitized[:max_chars].strip("-._") or "command"

    def _command_label_parts(self, command: list[str]) -> list[str]:
        try:
            module_index = command.index("-m")
        except ValueError:
            return [Path(command[0]).name] if command else ["command"]

        after_module = command[module_index + 2 :]
        parts: list[str] = []
        for item in after_module:
            if item.startswith("-"):
                break
            parts.append(item)
            if len(parts) >= 2:
                break
        return parts or ["command"]

    @staticmethod
    def _trace_paths_for_log(trace_paths: CommandTracePaths) -> dict[str, str]:
        return {
            key: str(value)
            for key, value in {
                "stdout": trace_paths.stdout,
                "stderr": trace_paths.stderr,
            }.items()
            if value is not None
        }

    @staticmethod
    def _normalize_process_output(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    @staticmethod
    def _safe_command(command: list[str]) -> list[str]:
        # Сейчас команды не содержат секретов. Метод оставлен как единая точка маскирования.
        return list(command)
