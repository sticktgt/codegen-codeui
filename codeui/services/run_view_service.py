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
                        excluded_files=summary.excluded_files,
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
            excluded_files=summary.excluded_files,
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
        verification_summary = self._dict(verification.get("summary"))
        result_summary = self._dict(payload.get("result_summary"))

        excluded_files = self._unique_list(
            self._list(result_summary.get("excluded_files"))
            + self._list(execution.get("excluded_files"))
            + self._list(merge_plan.get("excluded_files"))
            + self._list(generated_test_apply.get("excluded_files"))
            + self._list(verification_summary.get("generated_test_excluded_files"))
        )
        changed_files = self._unique_list(
            self._list(result_summary.get("changed_files"))
            or self._list(execution.get("changed_files"))
            or self._list(merge_plan.get("changed_files"))
        )
        if excluded_files:
            changed_files = [item for item in changed_files if not self._matches_any_path(item, excluded_files)]
        applied_files = self._unique_list(self._list(result_summary.get("applied_files")) or changed_files)

        # Для review/apply главным источником считается merge_plan/result_summary.
        # execution_summary.verification_passed может быть false при generated_test_verification_failed,
        # но merge_plan.ready_for_manual_merge_review=true означает, что production-код можно рассматривать
        # для применения с исключением проблемного generated test.
        merge_ready = (
            result_summary.get("merge_ready")
            if "merge_ready" in result_summary
            else merge_plan.get("ready_for_manual_merge_review")
            if "ready_for_manual_merge_review" in merge_plan
            else execution.get("merge_ready")
        )

        generation_result = self._artifacts.read_optional_json(run_id, "generation_result.json") or {}
        repair_result = self._artifacts.read_optional_json(run_id, "repair_result.json") or {}
        generation_code_artifact = self._dict(generation_result.get("code_artifact"))
        repair_code_artifact = self._dict(repair_result.get("code_artifact"))
        apply_result = self._dict(payload.get("apply_result"))
        apply_artifact = self._dict(apply_result.get("artifact"))
        code_artifact = repair_code_artifact or generation_code_artifact or apply_artifact
        import_changes = self._list(
            result_summary.get("import_changes")
            or execution.get("import_changes")
            or apply_result.get("import_changes")
            or apply_artifact.get("import_changes")
            or code_artifact.get("import_changes")
        )
        insert_scope = self._normalize_insert_scope(
            result_summary.get("insert_scope"),
            execution.get("insert_scope"),
            payload.get("insert_scope"),
            apply_artifact.get("insert_scope"),
            code_artifact.get("insert_scope"),
        )
        requested_operation = execution.get("requested_operation") or result_summary.get("requested_operation") or payload.get("requested_operation") or code_artifact.get("operation")
        final_operation = execution.get("final_operation") or result_summary.get("final_operation") or requested_operation
        parent_qualname = result_summary.get("parent_qualname") or execution.get("parent_qualname") or apply_artifact.get("parent_qualname") or code_artifact.get("parent_qualname")
        expected_new_symbol_kind = result_summary.get("expected_new_symbol_kind") or execution.get("expected_new_symbol_kind") or apply_artifact.get("expected_new_symbol_kind") or code_artifact.get("expected_new_symbol_kind")
        target_role = result_summary.get("target_role") or execution.get("target_role") or self._infer_target_role(final_operation, insert_scope, parent_qualname)
        repair_generation = self._dict(payload.get("repair_generation"))
        repair_summary = self._dict_or_none(repair_generation.get("result_summary"))
        run_artifacts = self._run_artifacts_summary(payload, generation_result, repair_result)

        return RunSummaryView(
            run_id=str(payload.get("run_id") or run_id),
            run_label=payload.get("run_label"),
            run_dir=payload.get("run_dir"),
            status=execution.get("status") or result_summary.get("status") or verification.get("verdict") or self._status_from_steps(payload),
            selected_target=execution.get("selected_target") or result_summary.get("selected_target") or payload.get("selected_target"),
            target_role=target_role,
            parent_qualname=parent_qualname,
            expected_new_symbol_kind=expected_new_symbol_kind,
            requested_operation=requested_operation,
            final_operation=final_operation,
            insert_scope=insert_scope,
            import_changes=import_changes,
            changed_files=changed_files,
            excluded_files=excluded_files,
            applied_files=applied_files,
            symbols_in_changed_files=self._list(execution.get("symbols_in_changed_files") or merge_plan.get("symbols_in_changed_files")),
            workspace_path=execution.get("workspace_path") or merge_plan.get("workspace_path"),
            verification_passed=execution.get("verification_passed") if "verification_passed" in execution else verification.get("passed"),
            has_generated_test=bool(execution.get("has_generated_test") or generated_test_apply.get("count") or generated_test_apply.get("applied_tests")),
            generated_test_files=self._unique_list(self._list(execution.get("generated_test_files")) + self._list(generated_test_apply.get("applied_tests"))),
            generated_test_merge_recommended=generated_test_apply.get("merge_recommended") if "merge_recommended" in generated_test_apply else None,
            generated_test_verification_failed=generated_test_apply.get("verification_failed") if "verification_failed" in generated_test_apply else None,
            generated_test_failed_files=self._unique_list(self._list(verification_summary.get("generated_test_failed_files"))),
            generated_test_excluded_files=self._unique_list(self._list(verification_summary.get("generated_test_excluded_files")) + self._list(generated_test_apply.get("excluded_files"))),
            production_failed=verification_summary.get("production_failed") if "production_failed" in verification_summary else None,
            generated_test_failed=verification_summary.get("generated_test_failed") if "generated_test_failed" in verification_summary else None,
            repair_used=bool(execution.get("repair_used") or repair_generation),
            repair_summary=repair_summary,
            merge_mode=execution.get("merge_mode") or merge_plan.get("mode"),
            merge_ready=merge_ready,
            linked_requirements=self._list(execution.get("linked_requirements") or merge_plan.get("linked_requirements")),
            recommended_tests=self._list(execution.get("recommended_tests") or merge_plan.get("recommended_tests")),
            recommended_test_commands=self._list(execution.get("recommended_test_commands") or merge_plan.get("recommended_test_commands")),
            code_generation_usage=self._dict_or_none(execution.get("code_generation_usage")) or self._usage_from_generation(payload.get("external_code_generation")),
            test_generation_usage=self._dict_or_none(execution.get("test_generation_usage")) or self._usage_from_generation(payload.get("external_test_generation")),
            repair_generation_usage=self._dict_or_none(execution.get("repair_generation_usage")) or self._usage_from_generation(payload.get("repair_generation")),
            embedding_usage=self._dict_or_none(execution.get("embedding_usage")),
            primary_issue=self._primary_issue(verification),
            merge_plan_summary_lines=self._list(merge_plan.get("summary_lines")),
            generated_test_apply=generated_test_apply if generated_test_apply else None,
            run_artifacts=run_artifacts,
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
        summary = self.summary(run_id)
        unified_diff = self._filter_unified_diff(str(diff.get("unified_diff") or ""), summary.excluded_files)
        changed_files = summary.changed_files or self._list(diff.get("changed_files"))
        return DiffView(changed_files=changed_files, excluded_files=summary.excluded_files, unified_diff=unified_diff)

    def code_artifact(self, run_id: str) -> ArtifactView:
        generation_payload = self._artifacts.read_optional_json(run_id, "generation_result.json") or {}
        repair_payload = self._artifacts.read_optional_json(run_id, "repair_result.json") or {}

        repair_artifact = self._dict_or_none(repair_payload.get("code_artifact"))
        generation_artifact = self._dict_or_none(generation_payload.get("code_artifact"))
        if repair_artifact:
            return ArtifactView(
                exists=True,
                source="repair_result",
                artifact=repair_artifact,
                planner_result=self._dict_or_none(repair_payload.get("planner_result")) or self._dict_or_none(repair_payload.get("repair_planner_result")),
                llm_usage=self._dict_or_none(repair_payload.get("llm_usage")),
                warnings=self._list(repair_payload.get("warnings")),
                raw={"final_result": repair_payload, "primary_generation_result": generation_payload or None},
            )
        if generation_artifact:
            return ArtifactView(
                exists=True,
                source="generation_result",
                artifact=generation_artifact,
                planner_result=self._dict_or_none(generation_payload.get("planner_result")),
                llm_usage=self._dict_or_none(generation_payload.get("llm_usage")),
                warnings=self._list(generation_payload.get("warnings")),
                raw=generation_payload,
            )
        return ArtifactView(exists=False)

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


    @classmethod
    def _unique_list(cls, values: list[Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value is None:
                continue
            text = str(value)
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    @classmethod
    def _matches_any_path(cls, path: str, candidates: list[str]) -> bool:
        return any(cls._same_path(path, candidate) for candidate in candidates)

    @staticmethod
    def _same_path(left: str, right: str) -> bool:
        left_norm = str(left).replace("\\", "/")
        right_norm = str(right).replace("\\", "/")
        return left_norm == right_norm or left_norm.endswith("/" + right_norm) or right_norm.endswith("/" + left_norm)

    @classmethod
    def _filter_unified_diff(cls, unified_diff: str, excluded_files: list[str]) -> str:
        if not unified_diff or not excluded_files:
            return unified_diff
        result: list[str] = []
        current: list[str] = []
        current_file: str | None = None

        def flush() -> None:
            nonlocal current, current_file
            if current and not (current_file and cls._matches_any_path(current_file, excluded_files)):
                result.extend(current)
            current = []
            current_file = None

        for line in unified_diff.splitlines(keepends=True):
            if line.startswith("--- ") and current:
                flush()
            current.append(line)
            if line.startswith("+++ "):
                current_file = line[4:].strip()
        flush()
        return "".join(result)


    @classmethod
    def _normalize_insert_scope(cls, *values: Any) -> str | None:
        for value in values:
            if value in {"module_body", "class_body"}:
                return str(value)
            if isinstance(value, dict):
                nested = cls._normalize_insert_scope(value.get("value"), value.get("insert_scope"), value.get("recommended_insert_scope"))
                if nested:
                    return nested
        return None

    @staticmethod
    def _infer_target_role(operation: Any, insert_scope: Any, parent_qualname: Any) -> str | None:
        if operation == "replace_symbol":
            return "target"
        if operation == "insert_after_symbol" and insert_scope == "class_body":
            return "parent_class" if parent_qualname else "parent_class"
        if operation == "insert_after_symbol":
            return "anchor"
        return None

    def _run_artifacts_summary(self, payload: dict[str, Any], generation_result: dict[str, Any], repair_result: dict[str, Any]) -> dict[str, Any]:
        def external_summary(name: str) -> dict[str, Any] | None:
            item = self._dict(payload.get(name))
            if not item:
                return None
            return {
                "mode": item.get("mode"),
                "request_path": item.get("request_path"),
                "result_path": item.get("result_path"),
                "trace_path": item.get("trace_path"),
                "status": self._dict(item.get("result_summary")).get("status"),
                "error_type": self._dict(item.get("result_summary")).get("error_type"),
                "message": self._dict(item.get("result_summary")).get("message"),
            }

        result = {
            "run_dir": payload.get("run_dir"),
            "external_code_generation": external_summary("external_code_generation"),
            "external_test_generation": external_summary("external_test_generation"),
            "repair_generation": external_summary("repair_generation"),
        }
        if generation_result:
            result["generation_result_status"] = generation_result.get("status")
            result["generation_trace_path"] = generation_result.get("trace_path")
        if repair_result:
            result["repair_result_status"] = repair_result.get("status")
            result["repair_trace_path"] = repair_result.get("trace_path")
        return {key: value for key, value in result.items() if value}

    @staticmethod
    def _created_at_from_run_id(run_id: str) -> str | None:
        # pipeline-20260427T182232.537841Z-ae02b5 -> 20260427T182232.537841Z
        parts = run_id.split("-")
        return parts[1] if len(parts) > 1 else None
