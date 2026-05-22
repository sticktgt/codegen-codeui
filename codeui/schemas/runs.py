from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunListItem(BaseModel):
    run_id: str
    run_label: str | None = None
    status: str | None = None
    selected_target: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    excluded_files: list[str] = Field(default_factory=list)
    verification_passed: bool | None = None
    merge_ready: bool | None = None
    created_at: str | None = None
    run_dir: str | None = None


class RunListResponse(BaseModel):
    items: list[RunListItem]
    count: int


class StepUsageView(BaseModel):
    calls: float | int | None = None
    prompt_tokens: float | int | None = None
    output_tokens: float | int | None = None
    total_tokens: float | int | None = None
    duration_sec: float | None = None
    source: str | None = None


class StepView(BaseModel):
    step_name: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    summary: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    exception_class: str | None = None
    usage: StepUsageView | None = None


class CheckView(BaseModel):
    name: str
    ok: bool
    severity: str | None = None
    issues: list[Any] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class RunSummaryView(BaseModel):
    run_id: str
    run_label: str | None = None
    run_dir: str | None = None
    status: str | None = None
    selected_target: str | None = None
    target_role: str | None = None
    parent_qualname: str | None = None
    expected_new_symbol_kind: str | None = None
    requested_operation: str | None = None
    final_operation: str | None = None
    insert_scope: str | None = None
    import_changes: list[Any] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    excluded_files: list[str] = Field(default_factory=list)
    applied_files: list[str] = Field(default_factory=list)
    symbols_in_changed_files: list[str] = Field(default_factory=list)
    workspace_id: str | None = None
    workspace_path: str | None = None
    verification_passed: bool | None = None
    has_generated_test: bool = False
    generated_test_files: list[str] = Field(default_factory=list)
    generated_test_merge_recommended: bool | None = None
    generated_test_verification_failed: bool | None = None
    generated_test_failed_files: list[str] = Field(default_factory=list)
    generated_test_excluded_files: list[str] = Field(default_factory=list)
    production_failed: bool | None = None
    generated_test_failed: bool | None = None
    repair_used: bool = False
    repair_summary: dict[str, Any] | None = None
    merge_mode: str | None = None
    merge_ready: bool | None = None
    linked_requirements: list[str] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)
    recommended_test_commands: list[str] = Field(default_factory=list)
    code_generation_usage: dict[str, Any] | None = None
    test_generation_usage: dict[str, Any] | None = None
    repair_generation_usage: dict[str, Any] | None = None
    generated_test_review_usage: dict[str, Any] | None = None
    embedding_usage: dict[str, Any] | None = None
    primary_issue: dict[str, Any] | None = None
    merge_plan_summary_lines: list[str] = Field(default_factory=list)
    generated_test_apply: dict[str, Any] | None = None
    run_artifacts: dict[str, Any] = Field(default_factory=dict)
    generated_test_failure_review: dict[str, Any] | None = None
    generated_test_failure_review_verdict: str | None = None
    warnings: list[Any] = Field(default_factory=list)


class DiffView(BaseModel):
    changed_files: list[str] = Field(default_factory=list)
    merge_changed_files: list[str] = Field(default_factory=list)
    generated_test_files: list[str] = Field(default_factory=list)
    excluded_files: list[str] = Field(default_factory=list)
    unified_diff: str = ""


class ArtifactView(BaseModel):
    exists: bool
    source: str | None = None
    artifact: dict[str, Any] | None = None
    planner_result: dict[str, Any] | None = None
    llm_usage: dict[str, Any] | None = None
    warnings: list[Any] = Field(default_factory=list)
    raw: dict[str, Any] | None = None
