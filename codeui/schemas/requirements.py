from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RequirementView(BaseModel):
    id: str
    title: str
    description: str = ""
    type: str | None = None
    status: str | None = None
    priority: str | None = None
    project_id: str | None = None
    parent_id: str | None = None
    verification_status: str | None = None
    note: str | None = None
    created_at: str | None = None
    source_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class RequirementTreeNode(BaseModel):
    item: RequirementView
    children: list["RequirementTreeNode"] = Field(default_factory=list)


class RequirementListResponse(BaseModel):
    items: list[RequirementView]
    count: int


class RequirementTreeResponse(BaseModel):
    items: list[RequirementTreeNode]
    count: int
