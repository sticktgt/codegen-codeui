from __future__ import annotations

from typing import Any

from codeui.logger import get_logger
from codeui.schemas.runs import ArtifactView, CheckView, DiffView, RunListItem, RunSummaryView, StepUsageView, StepView
from codeui.services.run_artifact_service import RunArtifactService

LOGGER = get_logger(__name__)


class RunViewService:
    def __init__(self, artifacts: RunArtifactService) -> None:
        self._artifacts = artifacts

    def list_runs(self, limit: int | None = None) -> list[RunListItem]:
        items: list[RunListItem] = []
        run_ids = self._artifacts.list_run_ids()
        if limit is not None:
            run_ids = run_ids[:limit]
        for run_id in run_ids:
            try:
                payload = self._artifacts.read_pipeline_run(run_id)
                summary = self.summary(run_id)
                items.append(
                    RunListItem(
                        run_id=run_id,
                        run_label=payload.get("run_label"),
                        status=summary.status,
                        selected_target=summary.selected_target,
                        changed_files=summary.changed_files,
                        verification_passed=summary.verification_passed,
                        merge_ready=summary.merge_ready,
                        created_at=self._created_at_from_run_id(run_id),
                        run_dir=payload.get("run_dir"),
                    )
                )
            except Exception as exc:  # noqa: BLE001 - список запусков не должен падать из-за одного run.
                LOGGER.warning("Cannot build run list item: run_id=%s error=%s", run_id, exc, exc_info=True)
                items.append(RunListItem(run_id=run_id, status="artifact_error", created_at=self._created_at_from_run_id(run_id)))
        return items

    def summary_as_list_item(self, run_id: str) -> RunListItem:
        payload = self._artifacts.read_pipeline_run(run_id)
        summary = self.summary(run_id)
        return RunListItem(
            run_id=run_id,
            run_label=payload.get("run_label"),
            status=summary.status,
            selected_target=summary.selected_target,
            changed_files=summary.changed_files,
            verification_passed=summary.verification_passed,
            merge_ready=summary.merge_ready,
            created_at=self._created_at_from_run_id(run_id),
            run_dir=payload.get("run_dir"),
        )

    def summary(self, run_id: str) -> RunSummaryView:
        payload = self._artifacts.read_pipeline_run(run_id)
        execution = self._dict(payload.get("execution_summary"))
        merge_plan = self._dict(payload.get("merge_plan"))
        verification = self._dict(payload.get("verification_report"))
        generated_test_apply = self._dict(payload.get("generated_test_apply"))

        return RunSummaryView(
            run_id=str(payload.get("run_id") or run_id),
            run_label=payload.get("run_label"),
            status=execution.get("status") or verification.get("verdict") or self._status_from_steps(payload),
            selected_target=execution.get("selected_target") or payload.get("selected_target"),
            requested_operation=execution.get("requested_operation") or payload.get("requested_operation"),
            final_operation=execution.get("final_operation") or execution.get("requested_operation") or payload.get("requested_operation"),
            changed_files=self._list(execution.get("changed_files") or merge_plan.get("changed_files")),
            symbols_in_changed_files=self._list(execution.get("symbols_in_changed_files") or merge_plan.get("symbols_in_changed_files")),
            workspace_path=execution.get("workspace_path") or merge_plan.get("workspace_path"),
            verification_passed=execution.get("verification_passed") if "verification_passed" in execution else verification.get("passed"),
            has_generated_test=bool(execution.get("has_generated_test") or generated_test_apply.get("count")),
            generated_test_files=self._list(execution.get("generated_test_files") or generated_test_apply.get("applied_tests")),
            repair_used=bool(execution.get("repair_used") or self._dict(payload.get("repair_generation"))),
            merge_mode=execution.get("merge_mode") or merge_plan.get("mode"),
            merge_ready=execution.get("merge_ready") if "merge_ready" in execution else merge_plan.get("ready_for_manual_merge_review"),
            linked_requirements=self._list(execution.get("linked_requirements") or merge_plan.get("linked_requirements")),
            recommended_tests=self._list(execution.get("recommended_tests") or merge_plan.get("recommended_tests")),
            recommended_test_commands=self._list(execution.get("recommended_test_commands") or merge_plan.get("recommended_test_commands")),
            code_generation_usage=self._dict_or_none(execution.get("code_generation_usage")) or self._usage_from_generation(payload.get("external_code_generation")),
            test_generation_usage=self._dict_or_none(execution.get("test_generation_usage")) or self._usage_from_generation(payload.get("external_test_generation")),
            repair_generation_usage=self._dict_or_none(execution.get("repair_generation_usage")) or self._usage_from_generation(payload.get("repair_generation")),
            embedding_usage=self._dict_or_none(execution.get("embedding_usage")),
            primary_issue=self._primary_issue(verification),
            merge_plan_summary_lines=self._list(merge_plan.get("summary_lines")),
            warnings=self._list(payload.get("warnings")),
        )

    def steps(self, run_id: str) -> list[StepView]:
        payload = self._artifacts.read_pipeline_run(run_id)
        usage_by_step = self._usage_by_step(payload)
        steps_payload = self._list(payload.get("steps"))
        result: list[StepView] = []
        for item in steps_payload:
            if not isinstance(item, dict):
                continue
            step_name = str(item.get("step_name") or "unknown")
            usage = usage_by_step.get(step_name)
            result.append(
                StepView(
                    step_name=step_name,
                    status=str(item.get("status") or "unknown"),
                    started_at=item.get("started_at"),
                    finished_at=item.get("finished_at"),
                    duration_ms=item.get("duration_ms"),
                    summary=item.get("summary"),
                    error_type=item.get("error_type"),
                    error_message=item.get("error_message"),
                    exception_class=item.get("exception_class"),
                    usage=usage,
                )
            )
        return result

    def checks(self, run_id: str) -> list[CheckView]:
        payload = self._artifacts.read_pipeline_run(run_id)
        verification = self._dict(payload.get("verification_report"))
        blocks = self._list(verification.get("blocks"))
        checks: list[CheckView] = []
        for item in blocks:
            if not isinstance(item, dict):
                continue
            checks.append(
                CheckView(
                    name=str(item.get("name") or "unknown"),
                    ok=bool(item.get("ok")),
                    severity=item.get("severity"),
                    issues=self._list(item.get("issues")),
                    details=self._dict(item.get("details")),
                )
            )
        return checks

    def diff(self, run_id: str) -> DiffView:
        payload = self._artifacts.read_pipeline_run(run_id)
        apply_result = self._dict(payload.get("apply_result"))
        diff = self._dict(apply_result.get("diff"))
        return DiffView(changed_files=self._list(diff.get("changed_files")), unified_diff=str(diff.get("unified_diff") or ""))

    def code_artifact(self, run_id: str) -> ArtifactView:
        payload = self._artifacts.read_optional_json(run_id, "generation_result.json")
        if not payload:
            return ArtifactView(exists=False)
        return ArtifactView(
            exists=True,
            artifact=self._dict_or_none(payload.get("code_artifact")),
            planner_result=self._dict_or_none(payload.get("planner_result")),
            llm_usage=self._dict_or_none(payload.get("llm_usage")),
            warnings=self._list(payload.get("warnings")),
            raw=payload,
        )

    def test_artifact(self, run_id: str) -> ArtifactView:
        payload = self._artifacts.read_optional_json(run_id, "generation_test_result.json")
        if not payload:
            return ArtifactView(exists=False)
        return ArtifactView(
            exists=True,
            artifact=self._dict_or_none(payload.get("test_artifact")),
            planner_result=self._dict_or_none(payload.get("test_planner_result")),
            llm_usage=self._dict_or_none(payload.get("llm_usage")),
            warnings=self._list(payload.get("warnings")),
            raw=payload,
        )

    def raw(self, run_id: str) -> dict[str, Any]:
        return {
            "pipeline_run": self._artifacts.read_pipeline_run(run_id),
            "generation_result": self._artifacts.read_optional_json(run_id, "generation_result.json"),
            "generation_test_result": self._artifacts.read_optional_json(run_id, "generation_test_result.json"),
            "repair_result": self._artifacts.read_optional_json(run_id, "repair_result.json"),
        }

    @staticmethod
    def _usage_from_generation(payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        result_summary = payload.get("result_summary") if isinstance(payload.get("result_summary"), dict) else {}
        usage = result_summary.get("llm_usage")
        return usage if isinstance(usage, dict) else None

    def _usage_by_step(self, payload: dict[str, Any]) -> dict[str, StepUsageView]:
        result: dict[str, StepUsageView] = {}
        code_usage = self._usage_from_generation(payload.get("external_code_generation"))
        if code_usage:
            result["external_generate"] = StepUsageView(**code_usage, source="code_generation")
        test_usage = self._usage_from_generation(payload.get("external_test_generation"))
        if test_usage:
            result["external_generate_test"] = StepUsageView(**test_usage, source="test_generation")
        repair_usage = self._usage_from_generation(payload.get("repair_generation"))
        if repair_usage:
            result["external_repair"] = StepUsageView(**repair_usage, source="repair_generation")
        execution = self._dict(payload.get("execution_summary"))
        embedding_usage = self._dict_or_none(execution.get("embedding_usage"))
        if embedding_usage:
            result["reference_retrieval"] = StepUsageView(
                calls=embedding_usage.get("calls"),
                prompt_tokens=embedding_usage.get("prompt_tokens"),
                total_tokens=embedding_usage.get("prompt_tokens"),
                duration_sec=embedding_usage.get("total_duration_sec"),
                source="embedding_usage",
            )
        return result

    def _primary_issue(self, verification: dict[str, Any]) -> dict[str, Any] | None:
        for block in self._list(verification.get("blocks")):
            if not isinstance(block, dict) or bool(block.get("ok")):
                continue
            issues = self._list(block.get("issues"))
            if issues:
                first_issue = issues[0]
                if isinstance(first_issue, dict):
                    return {
                        "check_name": block.get("name"),
                        "severity": first_issue.get("severity") or block.get("severity"),
                        "code": first_issue.get("code"),
                        "message": first_issue.get("message") or first_issue.get("error_message") or first_issue.get("reason"),
                        "file_path": first_issue.get("file_path"),
                        "symbol": first_issue.get("symbol"),
                    }
                return {
                    "check_name": block.get("name"),
                    "severity": block.get("severity"),
                    "message": str(first_issue),
                }
            error_message = block.get("error_message")
            if error_message:
                return {
                    "check_name": block.get("name"),
                    "severity": block.get("severity"),
                    "message": str(error_message),
                }
        return None

    def _status_from_steps(self, payload: dict[str, Any]) -> str | None:
        steps = [item for item in self._list(payload.get("steps")) if isinstance(item, dict)]
        if not steps:
            return None
        if any(str(item.get("status") or "").lower() in {"failed", "error"} for item in steps):
            return "failed"
        if all(str(item.get("status") or "").lower() == "ok" for item in steps):
            return "completed"
        return "partial"

    @staticmethod
    def _dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _dict_or_none(value: Any) -> dict[str, Any] | None:
        return value if isinstance(value, dict) else None

    @staticmethod
    def _list(value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _created_at_from_run_id(run_id: str) -> str | None:
        # pipeline-20260427T182232.537841Z-ae02b5 -> 20260427T182232.537841Z
        parts = run_id.split("-")
        return parts[1] if len(parts) > 1 else None
