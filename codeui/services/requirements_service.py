from __future__ import annotations

from pathlib import Path
from typing import Any

from codeui.config import Settings
from codeui.errors import ApiError
from codeui.logger import get_logger
from codeui.schemas.requirements import RequirementTreeNode, RequirementView
from codeui.schemas.ui_state import UiStateView
from codeui.services.json_io import read_json_file

LOGGER = get_logger(__name__)


class RequirementsService:
    def __init__(self, settings: Settings, ui_state: UiStateView | None = None) -> None:
        self._settings = settings
        self._ui_state = ui_state

    def list_requirements(self) -> list[RequirementView]:
        items: list[RequirementView] = []
        seen: set[str] = set()
        sources = self._sources_from_state_or_config()
        for source_id, source_type, path in sources:
            source_items = self._load_source(source_id, source_type, path)
            for item in source_items:
                view = self._to_requirement_view(source_id, item)
                if view.id in seen:
                    raise ApiError(
                        "REQUIREMENTS_DUPLICATE_ID",
                        f"Duplicate requirement id: {view.id}",
                        status_code=500,
                        details={"requirement_id": view.id, "source_id": source_id},
                    )
                seen.add(view.id)
                items.append(view)
        return sorted(items, key=lambda item: item.id)

    def get_requirement(self, requirement_id: str) -> RequirementView:
        for item in self.list_requirements():
            if item.id == requirement_id:
                return item
        raise ApiError("REQUIREMENT_NOT_FOUND", f"Requirement not found: {requirement_id}", status_code=404)

    def get_many_existing(self, requirement_ids: list[str]) -> list[RequirementView]:
        by_id = {item.id: item for item in self.list_requirements()}
        return [by_id[item_id] for item_id in requirement_ids if item_id in by_id]

    def tree(self) -> list[RequirementTreeNode]:
        items = self.list_requirements()
        nodes = {item.id: RequirementTreeNode(item=item) for item in items}
        roots: list[RequirementTreeNode] = []
        for item in items:
            node = nodes[item.id]
            parent_id = item.parent_id
            if parent_id and parent_id in nodes and parent_id != item.id:
                nodes[parent_id].children.append(node)
            else:
                roots.append(node)
        self._sort_nodes(roots)
        return roots

    def _sources_from_state_or_config(self) -> list[tuple[str, str, Path]]:
        if self._ui_state and self._ui_state.requirements_file_path:
            return [("selected", "json_file", Path(self._ui_state.requirements_file_path).expanduser().resolve())]
        result: list[tuple[str, str, Path]] = []
        for source in self._settings.requirements.sources:
            if not source.enabled:
                continue
            result.append((source.id, source.type, self._settings.resolve_path(source.path)))
        return result

    def _load_source(self, source_id: str, source_type: str, path: Path) -> list[dict[str, Any]]:
        LOGGER.info("Loading requirements source id=%s type=%s path=%s", source_id, source_type, path)
        if source_type == "json_file":
            payload = read_json_file(path, error_code="REQUIREMENTS_SOURCE_ERROR")
            return self._normalize_payload(payload, source_id, str(path))
        if source_type == "json_dir":
            if not path.exists() or not path.is_dir():
                raise ApiError("REQUIREMENTS_SOURCE_ERROR", f"Requirements directory not found: {path}", status_code=500)
            items: list[dict[str, Any]] = []
            for json_path in sorted(path.glob("*.json")):
                payload = read_json_file(json_path, error_code="REQUIREMENTS_SOURCE_ERROR")
                items.extend(self._normalize_payload(payload, source_id, str(json_path)))
            return items
        raise ApiError("REQUIREMENTS_SOURCE_ERROR", f"Unsupported requirements source type: {source_type}", status_code=500)

    @staticmethod
    def _normalize_payload(payload: Any, source_id: str, path: str) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            raw_items = payload
        elif isinstance(payload, dict) and isinstance(payload.get("requirements"), list):
            raw_items = payload["requirements"]
        elif isinstance(payload, dict):
            raw_items = [payload]
        else:
            raise ApiError(
                "REQUIREMENTS_SOURCE_ERROR",
                "Requirements JSON must be an object, list, or object with requirements list",
                status_code=500,
                details={"source_id": source_id, "path": path},
            )
        result: list[dict[str, Any]] = []
        for index, item in enumerate(raw_items):
            if not isinstance(item, dict):
                raise ApiError(
                    "REQUIREMENTS_SOURCE_ERROR",
                    "Requirement item must be JSON object",
                    status_code=500,
                    details={"source_id": source_id, "path": path, "index": index},
                )
            result.append(item)
        return result

    @staticmethod
    def _to_requirement_view(source_id: str, raw: dict[str, Any]) -> RequirementView:
        requirement_id = raw.get("id") or raw.get("requirement_id") or raw.get("code")
        if not requirement_id:
            raise ApiError(
                "REQUIREMENTS_SOURCE_ERROR",
                "Requirement must contain id",
                status_code=500,
                details={"source_id": source_id, "raw_keys": sorted(raw.keys())},
            )
        description = str(raw.get("description") or raw.get("text") or "")
        title = raw.get("title") or raw.get("name") or RequirementsService._make_title(str(requirement_id), description)
        parent = raw.get("parent_id")
        return RequirementView(
            id=str(requirement_id),
            title=str(title),
            description=description,
            type=str(raw["type"]) if raw.get("type") is not None else None,
            status=str(raw["status"]) if raw.get("status") is not None else None,
            priority=str(raw["priority"]) if raw.get("priority") is not None else None,
            project_id=str(raw["project_id"]) if raw.get("project_id") is not None else None,
            parent_id=str(parent) if parent not in (None, "") else None,
            verification_status=str(raw["verification_status"]) if raw.get("verification_status") is not None else None,
            note=str(raw["note"]) if raw.get("note") is not None else None,
            created_at=str(raw["created_at"]) if raw.get("created_at") is not None else None,
            source_id=source_id,
            raw=raw,
        )

    @staticmethod
    def _make_title(requirement_id: str, description: str) -> str:
        text = " ".join(description.split())
        if not text:
            return requirement_id
        return text[:96] + ("…" if len(text) > 96 else "")

    @classmethod
    def _sort_nodes(cls, nodes: list[RequirementTreeNode]) -> None:
        nodes.sort(key=lambda node: node.item.id)
        for node in nodes:
            cls._sort_nodes(node.children)
