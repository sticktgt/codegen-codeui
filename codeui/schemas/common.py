from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PatchOperation = Literal["replace_symbol", "insert_after_symbol"]
InsertScope = Literal["module_body", "class_body"]


class ErrorResponse(BaseModel):
    error: dict[str, Any]


class CommandSummary(BaseModel):
    command: list[str]
    cwd: str
    returncode: int
    duration_sec: float
    stdout_chars: int
    stderr_chars: int


class JsonObjectResponse(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
