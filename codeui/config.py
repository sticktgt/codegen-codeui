from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class AppSettings(BaseModel):
    name: str = "codeui"
    version: str = "0.2.37"


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8088
    reload: bool = False


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


class CommandTraceSettings(BaseModel):
    enabled: bool = True
    storage_dir: Path = Path(".trace/codecollector_cli")
    save_stdout: bool = True
    save_stderr: bool = True
    filename_label_max_chars: int = 80

    @field_validator("filename_label_max_chars")
    @classmethod
    def validate_filename_label_max_chars(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("filename_label_max_chars must be positive")
        return value




class ProjectLocksSettings(BaseModel):
    storage_dir: Path = Path("data/locks/projects")
    stale_after_sec: int = 3600

    @field_validator("stale_after_sec")
    @classmethod
    def validate_stale_after_sec(cls, value: int) -> int:
        if value < 0:
            raise ValueError("stale_after_sec must be non-negative")
        return value


class CodeCollectorSettings(BaseModel):
    root_dir: Path
    python: str = "python"
    module: str = "codecollector"
    command_timeout_sec: int = 900
    runs_dir: str = ".runs"
    state_dir: str = ".state"
    workspaces_dir: str = ".workspaces"

    @field_validator("command_timeout_sec")
    @classmethod
    def validate_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("command_timeout_sec must be positive")
        return value


class RequirementSourceSettings(BaseModel):
    id: str
    type: Literal["json_file", "json_dir"] = "json_file"
    path: Path
    enabled: bool = True


class RequirementsSettings(BaseModel):
    sources: list[RequirementSourceSettings] = Field(default_factory=list)


class ChangeRequestsSettings(BaseModel):
    storage_dir: Path = Path("data/change_requests")


class UiSettings(BaseModel):
    poll_interval_ms: int = 1500
    show_raw_json: bool = True
    show_debug_artifacts: bool = True
    state_file: Path = Path("data/ui_state.json")


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    codecollector: CodeCollectorSettings
    requirements: RequirementsSettings = Field(default_factory=RequirementsSettings)
    change_requests: ChangeRequestsSettings = Field(default_factory=ChangeRequestsSettings)
    command_trace: CommandTraceSettings = Field(default_factory=CommandTraceSettings)
    project_locks: ProjectLocksSettings = Field(default_factory=ProjectLocksSettings)
    ui: UiSettings = Field(default_factory=UiSettings)

    config_path: Path
    base_dir: Path

    def resolve_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return (self.base_dir / path).resolve()

    @property
    def codecollector_root(self) -> Path:
        return self.resolve_path(self.codecollector.root_dir)

    @property
    def runs_root(self) -> Path:
        return self.codecollector_root / self.codecollector.runs_dir

    @property
    def state_root(self) -> Path:
        return self.codecollector_root / self.codecollector.state_dir

    @property
    def workspaces_root(self) -> Path:
        return self.codecollector_root / self.codecollector.workspaces_dir

    @property
    def change_requests_root(self) -> Path:
        return self.resolve_path(self.change_requests.storage_dir)

    @property
    def ui_state_path(self) -> Path:
        return self.resolve_path(self.ui.state_file)

    @property
    def command_trace_root(self) -> Path:
        return self.resolve_path(self.command_trace.storage_dir)

    @property
    def project_locks_root(self) -> Path:
        return self.resolve_path(self.project_locks.storage_dir)


def _default_config_path() -> Path:
    env_path = os.environ.get("CODEUI_CONFIG")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return Path.cwd() / "config.yaml"


@lru_cache(maxsize=1)
def load_settings(config_path: str | None = None) -> Settings:
    path = Path(config_path).expanduser().resolve() if config_path else _default_config_path()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Config file must contain YAML mapping: {path}")
    return Settings(**payload, config_path=path, base_dir=path.parent)


def reset_settings_cache() -> None:
    load_settings.cache_clear()
