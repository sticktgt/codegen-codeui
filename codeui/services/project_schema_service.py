from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from codeui.errors import ApiError
from codeui.schemas.project_schema import (
    ProjectSchemaLink,
    ProjectSchemaNode,
    ProjectSchemaRequirement,
    ProjectSchemaResponse,
    ProjectSchemaSummary,
)


class ProjectSchemaService:
    """Build a requirement-to-project-structure view from knowledge.yaml and requirements.json.

    The service is intentionally file-oriented and does not depend on codeui project state.
    This makes the same transformation usable from another application later.
    """

    def build_from_files(
        self,
        *,
        knowledge_path: str | Path,
        requirements_path: str | Path,
        project_id: str | None = None,
        project_name: str | None = None,
    ) -> ProjectSchemaResponse:
        knowledge_file = Path(knowledge_path).expanduser().resolve()
        requirements_file = Path(requirements_path).expanduser().resolve()
        knowledge = self._read_yaml_mapping(knowledge_file)
        requirements = self._load_requirements(requirements_file)
        nodes = self._build_nodes(knowledge)
        links = self._build_links(nodes)
        linked_requirement_ids = {link.requirement_id for link in links}
        modules_count = len(knowledge.get("modules") or {}) if isinstance(knowledge.get("modules"), dict) else 0
        symbols_count = len(knowledge.get("symbols") or {}) if isinstance(knowledge.get("symbols"), dict) else 0
        return ProjectSchemaResponse(
            project_id=project_id,
            project_name=project_name,
            knowledge_path=str(knowledge_file),
            requirements_path=str(requirements_file),
            nodes=nodes,
            requirements=requirements,
            links=links,
            summary=ProjectSchemaSummary(
                modules_count=modules_count,
                symbols_count=symbols_count,
                nodes_count=len(nodes),
                requirements_count=len(requirements),
                linked_requirements_count=len(linked_requirement_ids),
                links_count=len(links),
            ),
        )

    def _read_yaml_mapping(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ApiError("PROJECT_SCHEMA_KNOWLEDGE_NOT_FOUND", f"knowledge.yaml not found: {path}", status_code=404)
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001
            raise ApiError("PROJECT_SCHEMA_KNOWLEDGE_READ_ERROR", f"Cannot read knowledge.yaml: {path}", status_code=500) from exc
        if not isinstance(payload, dict):
            raise ApiError("PROJECT_SCHEMA_KNOWLEDGE_INVALID", f"knowledge.yaml must contain a mapping: {path}", status_code=500)
        return payload

    def _load_requirements(self, path: Path) -> list[ProjectSchemaRequirement]:
        if not path.exists():
            raise ApiError("PROJECT_SCHEMA_REQUIREMENTS_NOT_FOUND", f"requirements.json not found: {path}", status_code=404)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise ApiError("PROJECT_SCHEMA_REQUIREMENTS_READ_ERROR", f"Cannot read requirements.json: {path}", status_code=500) from exc
        raw_items = self._extract_requirement_items(payload, path)
        result: list[ProjectSchemaRequirement] = []
        seen: set[str] = set()
        for item in raw_items:
            requirement_id = item.get("id") or item.get("requirement_id") or item.get("code")
            if not requirement_id:
                continue
            text_id = str(requirement_id)
            if text_id in seen:
                continue
            seen.add(text_id)
            description = str(item.get("description") or item.get("text") or "")
            title = str(item.get("title") or item.get("name") or self._make_title(text_id, description))
            result.append(
                ProjectSchemaRequirement(
                    id=text_id,
                    title=title,
                    description=description,
                    type=str(item["type"]) if item.get("type") is not None else None,
                    status=str(item["status"]) if item.get("status") is not None else None,
                )
            )
        return sorted(result, key=lambda item: item.id)

    @staticmethod
    def _extract_requirement_items(payload: Any, path: Path) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            raw_items = payload
        elif isinstance(payload, dict) and isinstance(payload.get("requirements"), list):
            raw_items = payload["requirements"]
        elif isinstance(payload, dict):
            raw_items = [payload]
        else:
            raise ApiError("PROJECT_SCHEMA_REQUIREMENTS_INVALID", f"requirements.json has unsupported format: {path}", status_code=500)
        return [item for item in raw_items if isinstance(item, dict)]

    def _build_nodes(self, knowledge: dict[str, Any]) -> list[ProjectSchemaNode]:
        raw_modules_payload = knowledge.get("modules") if isinstance(knowledge.get("modules"), dict) else {}
        raw_symbols_payload = knowledge.get("symbols") if isinstance(knowledge.get("symbols"), dict) else {}
        raw_modules = {item_id: raw for item_id, raw in raw_modules_payload.items() if not self._is_test_node_id(str(item_id))}
        raw_symbols = {item_id: raw for item_id, raw in raw_symbols_payload.items() if not self._is_test_node_id(str(item_id))}
        known_ids = set(raw_modules) | set(raw_symbols)
        package_ids = self._infer_package_ids(set(raw_modules))
        all_parent_ids = known_ids | package_ids

        nodes: list[ProjectSchemaNode] = []
        for package_id in sorted(package_ids):
            nodes.append(
                ProjectSchemaNode(
                    id=package_id,
                    kind="package",
                    label=self._label(package_id),
                    title=self._label(package_id),
                    parent_id=self._nearest_parent(package_id, all_parent_ids - {package_id}),
                )
            )
        for module_id, raw in sorted(raw_modules.items()):
            item = raw if isinstance(raw, dict) else {}
            nodes.append(
                ProjectSchemaNode(
                    id=module_id,
                    kind="module",
                    label=self._label(module_id),
                    title=str(item.get("title") or self._label(module_id)),
                    description=str(item.get("description") or ""),
                    parent_id=self._nearest_parent(module_id, all_parent_ids - {module_id}),
                    requirement_ids=self._normalize_ids(item.get("requirements")),
                )
            )
        for symbol_id, raw in sorted(raw_symbols.items()):
            item = raw if isinstance(raw, dict) else {}
            nodes.append(
                ProjectSchemaNode(
                    id=symbol_id,
                    kind=self._infer_symbol_kind(symbol_id, set(raw_modules), set(raw_symbols)),
                    label=self._label(symbol_id),
                    title=str(item.get("title") or self._label(symbol_id)),
                    description=str(item.get("description") or ""),
                    parent_id=self._nearest_parent(symbol_id, all_parent_ids - {symbol_id}),
                    requirement_ids=self._normalize_ids(item.get("requirements")),
                )
            )
        return sorted(nodes, key=lambda item: (self._node_sort_key(item.id), item.kind))

    @staticmethod
    def _is_test_node_id(item_id: str) -> bool:
        return item_id == "tests" or item_id.startswith("tests.") or ".tests." in item_id

    @staticmethod
    def _infer_package_ids(module_ids: set[str]) -> set[str]:
        result: set[str] = set()
        for module_id in module_ids:
            parts = module_id.split(".")
            for index in range(1, len(parts)):
                prefix = ".".join(parts[:index])
                if prefix not in module_ids:
                    result.add(prefix)
        return result

    @classmethod
    def _nearest_parent(cls, item_id: str, candidates: set[str]) -> str | None:
        parts = item_id.split(".")
        for index in range(len(parts) - 1, 0, -1):
            candidate = ".".join(parts[:index])
            if candidate in candidates:
                return candidate
        return None

    @staticmethod
    def _label(item_id: str) -> str:
        return item_id.rsplit(".", 1)[-1]

    @staticmethod
    def _make_title(requirement_id: str, description: str) -> str:
        text = " ".join(description.split())
        if not text:
            return requirement_id
        return text[:96] + ("…" if len(text) > 96 else "")

    @staticmethod
    def _normalize_ids(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item).strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result

    @staticmethod
    def _infer_symbol_kind(symbol_id: str, module_ids: set[str], symbol_ids: set[str]) -> str:
        parent = ProjectSchemaService._nearest_parent(symbol_id, module_ids | (symbol_ids - {symbol_id}))
        if parent and parent in symbol_ids:
            return "member"
        label = ProjectSchemaService._label(symbol_id)
        if label and label[0].isupper():
            return "class"
        return "symbol"

    @staticmethod
    def _node_sort_key(item_id: str) -> tuple[int, str]:
        return (item_id.count("."), item_id)

    @staticmethod
    def _build_links(nodes: list[ProjectSchemaNode]) -> list[ProjectSchemaLink]:
        links: list[ProjectSchemaLink] = []
        seen: set[tuple[str, str]] = set()
        for node in nodes:
            for requirement_id in node.requirement_ids:
                key = (requirement_id, node.id)
                if key in seen:
                    continue
                seen.add(key)
                links.append(ProjectSchemaLink(requirement_id=requirement_id, target_id=node.id))
        return sorted(links, key=lambda item: (item.requirement_id, item.target_id))
