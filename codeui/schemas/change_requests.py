from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from codeui.schemas.common import InsertScope, PatchOperation


def normalize_insert_scope_value(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        return normalize_insert_scope_value(value.get("value") or value.get("insert_scope") or value.get("recommended_insert_scope"))
    if value in {"module_body", "class_body"}:
        return str(value)
    return None


class RequirementSnapshot(BaseModel):
    id: str
    title: str | None = None
    description: str = ""
    type: str | None = None
    status: str | None = None
    priority: str | None = None
    verification_status: str | None = None
    source_id: str | None = None
    missing: bool = False


class ChangeRequestCreate(BaseModel):
    project_id: str
    code: str | None = None
    requirement_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    requested_operation: PatchOperation | None = None
    insert_scope: InsertScope | None = None

    @field_validator("title", "description")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = str(value or "").strip()
        if not stripped:
            raise ValueError("Поле обязательно для заполнения")
        return stripped

    @field_validator("code")
    @classmethod
    def strip_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped or None

    @field_validator("insert_scope", mode="before")
    @classmethod
    def normalize_insert_scope(cls, value: Any) -> str | None:
        return normalize_insert_scope_value(value)

    @model_validator(mode="after")
    def normalize_requirement_ids(self) -> "ChangeRequestCreate":
        ids = list(self.requirement_ids)
        if self.requirement_id and self.requirement_id not in ids:
            ids.insert(0, self.requirement_id)
        self.requirement_ids = ids
        self.requirement_id = ids[0] if ids else self.requirement_id
        return self


class ChangeRequestUpdate(BaseModel):
    code: str | None = None
    requirement_id: str | None = None
    requirement_ids: list[str] | None = None
    title: str | None = None
    description: str | None = None
    constraints: list[str] | None = None
    notes: list[str] | None = None
    requested_operation: PatchOperation | None = None
    insert_scope: InsertScope | None = None
    status: str | None = None

    @field_validator("title", "description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("Поле не может быть пустым")
        return stripped

    @field_validator("code")
    @classmethod
    def strip_optional_update_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("Код запроса не может быть пустым")
        return stripped

    @field_validator("insert_scope", mode="before")
    @classmethod
    def normalize_insert_scope(cls, value: Any) -> str | None:
        return normalize_insert_scope_value(value)


class ChangeRequestView(BaseModel):
    cr_id: str
    code: str | None = None
    project_id: str
    requirement_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    requirements_snapshot: list[RequirementSnapshot] = Field(default_factory=list)
    title: str
    description: str
    constraints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    requested_operation: PatchOperation | None = None
    insert_scope: InsertScope | None = None
    status: str = "draft"
    session_id: str | None = None
    recommended_target: str | None = None
    selected_target: str | None = None
    run_ids: list[str] = Field(default_factory=list)
    last_run_id: str | None = None
    last_workspace_id: str | None = None
    applied_at: datetime | None = None
    applied_run_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("insert_scope", mode="before")
    @classmethod
    def normalize_view_insert_scope(cls, value: Any) -> str | None:
        return normalize_insert_scope_value(value)

    @model_validator(mode="before")
    @classmethod
    def normalize_old_payload(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("cr_code") and not data.get("code"):
                data["code"] = data.get("cr_code")

            requirement_id = data.get("requirement_id")
            requirement_ids = list(data.get("requirement_ids") or [])
            if requirement_id and requirement_id not in requirement_ids:
                requirement_ids.insert(0, requirement_id)
            data["requirement_ids"] = requirement_ids
            if not data.get("requirement_id") and requirement_ids:
                data["requirement_id"] = requirement_ids[0]

            run_ids = list(data.get("run_ids") or [])
            last_run_id = data.get("last_run_id")
            if last_run_id and last_run_id not in run_ids:
                run_ids.append(last_run_id)
            data["run_ids"] = run_ids
        return data


class ChangeRequestListResponse(BaseModel):
    items: list[ChangeRequestView]
    count: int


class AnalyzeRequest(BaseModel):
    limit: int | None = None
    operation: PatchOperation | None = None
    insert_scope: InsertScope | None = None

    @field_validator("insert_scope", mode="before")
    @classmethod
    def normalize_insert_scope(cls, value: Any) -> str | None:
        return normalize_insert_scope_value(value)


class SelectTargetRequest(BaseModel):
    selected_qualname: str
    operation: PatchOperation | None = None
    insert_scope: InsertScope | None = None

    @field_validator("insert_scope", mode="before")
    @classmethod
    def normalize_insert_scope(cls, value: Any) -> str | None:
        return normalize_insert_scope_value(value)


class GenerateRequest(BaseModel):
    selected_qualname: str | None = None
    operation: PatchOperation | None = None
    insert_scope: InsertScope | None = None
    limit: int | None = None
    disable_vector_search: bool = False

    @field_validator("insert_scope", mode="before")
    @classmethod
    def normalize_insert_scope(cls, value: Any) -> str | None:
        return normalize_insert_scope_value(value)
