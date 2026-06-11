from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectSchemaRequirement(BaseModel):
    id: str
    title: str = ""
    description: str = ""
    type: str | None = None
    status: str | None = None


class ProjectSchemaNode(BaseModel):
    id: str
    kind: str
    label: str
    title: str = ""
    description: str = ""
    parent_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)


class ProjectSchemaLink(BaseModel):
    requirement_id: str
    target_id: str


class ProjectSchemaSummary(BaseModel):
    modules_count: int = 0
    symbols_count: int = 0
    nodes_count: int = 0
    requirements_count: int = 0
    linked_requirements_count: int = 0
    links_count: int = 0


class ProjectSchemaResponse(BaseModel):
    project_id: str | None = None
    project_name: str | None = None
    knowledge_path: str
    requirements_path: str
    nodes: list[ProjectSchemaNode]
    requirements: list[ProjectSchemaRequirement]
    links: list[ProjectSchemaLink]
    summary: ProjectSchemaSummary
