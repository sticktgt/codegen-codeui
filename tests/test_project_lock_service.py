from pathlib import Path

import pytest

from codeui.config import CodeCollectorSettings, ProjectLocksSettings, Settings
from codeui.errors import ApiError
from codeui.services.project_lock_service import ProjectOperationLockService


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        codecollector=CodeCollectorSettings(root_dir=tmp_path / "codecollector"),
        project_locks=ProjectLocksSettings(storage_dir=Path("locks"), stale_after_sec=3600),
        config_path=tmp_path / "config.yaml",
        base_dir=tmp_path,
    )


def test_project_operation_lock_blocks_same_project(tmp_path: Path) -> None:
    service = ProjectOperationLockService(make_settings(tmp_path))

    with service.acquire("proj-1", "apply_workspace"):
        with pytest.raises(ApiError) as exc_info:
            with service.acquire("proj-1", "reindex_project"):
                pass

    assert exc_info.value.code == "PROJECT_OPERATION_BUSY"
    assert exc_info.value.status_code == 409
    assert exc_info.value.details["project_id"] == "proj-1"


def test_project_operation_lock_allows_different_projects(tmp_path: Path) -> None:
    service = ProjectOperationLockService(make_settings(tmp_path))

    with service.acquire("proj-1", "apply_workspace"):
        with service.acquire("proj-2", "reindex_project"):
            assert True

    assert not list((tmp_path / "locks").glob("*.lock"))
