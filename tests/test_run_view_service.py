from __future__ import annotations

import json
from pathlib import Path

from codeui.config import CodeCollectorSettings, Settings
from codeui.services.run_artifact_service import RunArtifactService
from codeui.services.run_view_service import RunViewService


def make_service(tmp_path: Path, payload: dict, *, review_artifact: dict | None = None) -> RunViewService:
    codecollector_root = tmp_path / "codecollector"
    run_dir = codecollector_root / ".runs" / "pipeline-20260514T120000.000000Z-test"
    run_dir.mkdir(parents=True)
    (run_dir / "pipeline_run_20260514T120000.000000Z.json").write_text(json.dumps(payload), encoding="utf-8")
    if review_artifact is not None:
        (run_dir / "generated_test_review_result.json").write_text(json.dumps(review_artifact), encoding="utf-8")
    settings = Settings(
        codecollector=CodeCollectorSettings(root_dir=codecollector_root),
        config_path=tmp_path / "config.yaml",
        base_dir=tmp_path,
    )
    return RunViewService(RunArtifactService(settings))


def test_summary_reads_generated_test_failure_review_and_preserves_excluded_file_casing(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        {
            "run_id": "pipeline-20260514T120000.000000Z-test",
            "result_summary": {
                "status": "generated_test_verification_failed",
                "has_generated_test": True,
                "generated_test_files": ["tests/test_generated_generate_test_Note.py"],
            },
            "generated_test_apply": {
                "verification_failed": True,
                "merge_recommended": False,
                "excluded_files": ["tests/test_generated_generate_test_Note.py"],
            },
            "generated_test_failure_review": {
                "review": {
                    "verdict": "production_likely_ok_test_likely_bad",
                    "confidence": 0.85,
                    "recommended_action": "keep_production_exclude_test",
                }
            },
        },
    )

    summary = service.summary("pipeline-20260514T120000.000000Z-test")

    assert summary.status == "generated_test_verification_failed"
    assert summary.generated_test_failure_review_verdict == "production_likely_ok_test_likely_bad"
    assert summary.generated_test_excluded_files == ["tests/test_generated_generate_test_Note.py"]
    assert summary.excluded_files == ["tests/test_generated_generate_test_Note.py"]


def test_steps_place_generated_test_failure_review_after_verification(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        {
            "steps": [
                {"step_name": "generated_test_failure_review", "status": "ok", "summary": "advisory"},
                {"step_name": "verification", "status": "ok"},
                {"step_name": "merge_dry_run", "status": "ok"},
            ]
        },
    )

    steps = service.steps("pipeline-20260514T120000.000000Z-test")

    assert [step.step_name for step in steps] == ["verification", "generated_test_failure_review", "merge_dry_run"]


def test_diff_keeps_workspace_changed_files_and_excluded_files_separate(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        {
            "result_summary": {
                "changed_files": ["note/note_model.py"],
                "generated_test_files": ["tests/test_generated_generate_test_Note.py"],
                "excluded_files": ["tests/test_generated_generate_test_Note.py"],
            },
            "apply_result": {
                "diff": {
                    "changed_files": ["note/note_model.py", "tests/test_generated_generate_test_Note.py"],
                    "unified_diff": "diff --git a/note/note_model.py b/note/note_model.py\n",
                }
            },
        },
    )

    diff = service.diff("pipeline-20260514T120000.000000Z-test")

    assert diff.changed_files == ["note/note_model.py", "tests/test_generated_generate_test_Note.py"]
    assert diff.merge_changed_files == ["note/note_model.py"]
    assert diff.generated_test_files == ["tests/test_generated_generate_test_Note.py"]
    assert diff.excluded_files == ["tests/test_generated_generate_test_Note.py"]


def test_generated_test_review_alias_usage_is_shown_on_review_step(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        {
            "steps": [
                {"step_name": "verification", "status": "ok"},
                {"step_name": "generated_test_failure_review", "status": "ok"},
            ],
            "generated_test_review": {
                "status": "ok",
                "review": {"verdict": "production_likely_ok_test_likely_bad"},
                "llm_usage": {
                    "calls": 1,
                    "prompt_tokens": 7049.0,
                    "output_tokens": 445.0,
                    "total_tokens": 7494.0,
                    "duration_sec": 5.2,
                },
            },
        },
    )

    summary = service.summary("pipeline-20260514T120000.000000Z-test")
    steps = service.steps("pipeline-20260514T120000.000000Z-test")

    assert summary.generated_test_failure_review_verdict == "production_likely_ok_test_likely_bad"
    assert summary.generated_test_review_usage is not None
    assert summary.generated_test_review_usage["total_tokens"] == 7494.0
    assert steps[1].step_name == "generated_test_failure_review"
    assert steps[1].usage is not None
    assert steps[1].usage.total_tokens == 7494.0


def test_repair_generation_usage_is_shown_on_external_repair_step(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        {
            "steps": [
                {"step_name": "patch_static_semantics", "status": "failed"},
                {"step_name": "external_repair_after_patch_static_semantics", "status": "ok"},
            ],
            "repair_generation": {
                "result_summary": {
                    "llm_usage": {
                        "calls": 2,
                        "prompt_tokens": 8198.0,
                        "output_tokens": 875.0,
                        "total_tokens": 9073.0,
                        "duration_sec": 11.15,
                    }
                }
            },
        },
    )

    steps = service.steps("pipeline-20260514T120000.000000Z-test")

    repair_step = next(step for step in steps if step.step_name == "external_repair_after_patch_static_semantics")
    assert repair_step.usage is not None
    assert repair_step.usage.total_tokens == 9073.0

def test_repair_usage_is_not_shown_on_repair_static_semantics_followup_step(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        {
            "steps": [
                {"step_name": "external_repair_after_patch_static_semantics", "status": "ok"},
                {"step_name": "external_repair_after_patch_static_semantics_static_semantics", "status": "ok"},
            ],
            "repair_generation": {
                "result_summary": {
                    "llm_usage": {
                        "calls": 2,
                        "prompt_tokens": 8198.0,
                        "output_tokens": 875.0,
                        "total_tokens": 9073.0,
                        "duration_sec": 11.15,
                    }
                }
            },
        },
    )

    steps = service.steps("pipeline-20260514T120000.000000Z-test")

    repair_step = next(step for step in steps if step.step_name == "external_repair_after_patch_static_semantics")
    followup_step = next(
        step for step in steps if step.step_name == "external_repair_after_patch_static_semantics_static_semantics"
    )

    assert repair_step.usage is not None
    assert repair_step.usage.total_tokens == 9073.0
    assert followup_step.usage is None


def test_summary_extracts_workspace_id_from_top_level_or_workspace_path(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        {
            "workspace_path": "/home/stickt/llm/codecollector/.workspaces/src-20260514T124459.362849Z-a752a8",
            "result_summary": {"status": "ready_for_merge_review"},
            "merge_plan": {"ready_for_manual_merge_review": True},
        },
    )

    summary = service.summary("pipeline-20260514T120000.000000Z-test")

    assert summary.workspace_id == "src-20260514T124459.362849Z-a752a8"
    assert summary.merge_ready is True
