from __future__ import annotations

from codeui.schemas.change_requests import ChangeRequestView
from codeui.services.change_request_traceability import change_request_traceability_id


def test_change_request_traceability_id_prefers_external_code() -> None:
    change_request = ChangeRequestView(
        cr_id="cr-20260605T125728553703Z-50e5b2",
        code="CR-D17",
        project_id="proj-1",
        title="Заголовок",
        description="Описание",
    )

    assert change_request_traceability_id(change_request) == "CR-D17"


def test_change_request_traceability_id_falls_back_to_internal_id() -> None:
    change_request = ChangeRequestView(
        cr_id="cr-20260605T125728553703Z-50e5b2",
        code=None,
        project_id="proj-1",
        title="Заголовок",
        description="Описание",
    )

    assert change_request_traceability_id(change_request) == "cr-20260605T125728553703Z-50e5b2"
