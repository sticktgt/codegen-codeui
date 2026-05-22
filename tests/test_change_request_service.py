
from codeui.services.change_request_service import ChangeRequestService
from codeui.schemas.change_requests import ChangeRequestCreate
from codeui.config import CodeCollectorSettings, Settings


def test_mark_applied_can_use_non_last_run_id(tmp_path):
    settings = Settings(codecollector=CodeCollectorSettings(root_dir=tmp_path / "codecollector"), config_path=tmp_path / "config.yaml", base_dir=tmp_path)
    service = ChangeRequestService(settings)
    cr = service.create_change_request(
        ChangeRequestCreate(
            project_id="proj-1",
            requirement_ids=[],
            title="Test",
            description="Test description",
        )
    )
    cr.run_ids.extend(["pipeline-old", "pipeline-new"])
    cr.last_run_id = "pipeline-new"
    cr.last_workspace_id = "workspace-new"
    service._save(cr)

    updated = service.mark_applied(
        cr.cr_id,
        {"applied_files": ["note.py"]},
        run_id="pipeline-old",
        workspace_id="workspace-old",
    )

    assert updated.status == "applied"
    assert updated.applied_run_id == "pipeline-old"
    assert updated.last_run_id == "pipeline-new"
    assert updated.raw["applied_workspace_id"] == "workspace-old"
