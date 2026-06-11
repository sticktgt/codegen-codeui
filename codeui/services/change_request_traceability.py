from __future__ import annotations

from codeui.schemas.change_requests import ChangeRequestView


def change_request_traceability_id(change_request: ChangeRequestView) -> str:
    """Вернуть внешний код CR для записи трассировки, с fallback на внутренний id."""

    code = str(change_request.code or "").strip()
    return code or change_request.cr_id
