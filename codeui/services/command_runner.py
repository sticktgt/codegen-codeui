from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

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
        LOGGER.info("Running command: cwd=%s command=%s", effective_cwd, self._safe_command(command))
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
            LOGGER.error("Command timeout after %.2fs: %s", duration, self._safe_command(command))
            raise ApiError(
                "CODECOLLECTOR_TIMEOUT",
                "codecollector command timed out",
                status_code=504,
                details={"command": self._safe_command(command), "timeout_sec": timeout, "duration_sec": duration},
            ) from exc
        except OSError as exc:
            duration = time.monotonic() - start
            LOGGER.exception("Command failed to start after %.2fs: %s", duration, self._safe_command(command))
            raise ApiError(
                "CODECOLLECTOR_COMMAND_START_FAILED",
                "Failed to start codecollector command",
                status_code=500,
                details={"command": self._safe_command(command), "error": str(exc)},
            ) from exc

        duration = time.monotonic() - start
        LOGGER.info(
            "Command finished: returncode=%s duration=%.2fs stdout_chars=%s stderr_chars=%s command=%s",
            completed.returncode,
            duration,
            len(completed.stdout or ""),
            len(completed.stderr or ""),
            self._safe_command(command),
        )
        result = CommandResult(
            command=command,
            cwd=effective_cwd,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            duration_sec=duration,
        )
        if check_returncode and completed.returncode != 0:
            raise ApiError(
                "CODECOLLECTOR_COMMAND_FAILED",
                "codecollector command failed",
                status_code=502,
                details={
                    "command": self._safe_command(command),
                    "cwd": str(effective_cwd),
                    "returncode": completed.returncode,
                    "duration_sec": duration,
                    "stderr_tail": result.stderr[-4000:],
                    "stdout_tail": result.stdout[-4000:],
                },
            )
        return result

    @staticmethod
    def _safe_command(command: list[str]) -> list[str]:
        # Сейчас команды не содержат секретов. Метод оставлен как единая точка маскирования.
        return list(command)
