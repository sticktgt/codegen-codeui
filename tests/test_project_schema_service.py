from __future__ import annotations

import json
from pathlib import Path

import yaml

from codeui.services.project_schema_service import ProjectSchemaService


def write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_project_schema_builds_tree_and_requirement_links(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.yaml"
    requirements_path = tmp_path / "requirements.json"
    write_yaml(
        knowledge_path,
        {
            "modules": {
                "common.constants": {"title": "Глобальные константы", "requirements": ["REQ-1"]},
                "note.note_storage": {"title": "Хранилище"},
            },
            "symbols": {
                "note.note_storage.NoteStorage": {"title": "NoteStorage"},
                "note.note_storage.NoteStorage.save": {"title": "save", "requirements": ["REQ-2"]},
            },
        },
    )
    write_json(
        requirements_path,
        {
            "requirements": [
                {"id": "REQ-1", "type": "FR", "description": "Первое требование"},
                {"id": "REQ-2", "type": "BR", "description": "Второе требование"},
            ]
        },
    )

    result = ProjectSchemaService().build_from_files(knowledge_path=knowledge_path, requirements_path=requirements_path)

    nodes = {node.id: node for node in result.nodes}
    assert nodes["common.constants"].parent_id == "common"
    assert nodes["note.note_storage.NoteStorage"].parent_id == "note.note_storage"
    assert nodes["note.note_storage.NoteStorage.save"].parent_id == "note.note_storage.NoteStorage"
    assert nodes["common.constants"].requirement_ids == ["REQ-1"]
    assert nodes["note.note_storage.NoteStorage.save"].requirement_ids == ["REQ-2"]
    assert {(link.requirement_id, link.target_id) for link in result.links} == {
        ("REQ-1", "common.constants"),
        ("REQ-2", "note.note_storage.NoteStorage.save"),
    }
    assert result.summary.links_count == 2


def test_project_schema_does_not_require_cr_fields(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.yaml"
    requirements_path = tmp_path / "requirements.json"
    write_yaml(
        knowledge_path,
        {
            "modules": {"common.constants": {"title": "Глобальные константы", "change_requests": [{"id": "CR-1"}]}},
            "symbols": {},
        },
    )
    write_json(requirements_path, {"requirements": []})

    result = ProjectSchemaService().build_from_files(knowledge_path=knowledge_path, requirements_path=requirements_path)

    assert [node.id for node in result.nodes if node.kind == "module"] == ["common.constants"]
    assert result.links == []


def test_project_schema_excludes_test_nodes_and_links(tmp_path: Path) -> None:
    knowledge_path = tmp_path / "knowledge.yaml"
    requirements_path = tmp_path / "requirements.json"
    write_yaml(
        knowledge_path,
        {
            "modules": {
                "common.constants": {"title": "Глобальные константы", "requirements": ["REQ-1"]},
                "tests.test_constants": {"title": "Тесты", "requirements": ["REQ-1"]},
            },
            "symbols": {
                "common.constants.FileExtensions": {"title": "FileExtensions"},
                "tests.test_constants.test_default_encoding": {"title": "test", "requirements": ["REQ-1"]},
            },
        },
    )
    write_json(requirements_path, {"requirements": [{"id": "REQ-1", "description": "Требование"}]})

    result = ProjectSchemaService().build_from_files(knowledge_path=knowledge_path, requirements_path=requirements_path)

    node_ids = {node.id for node in result.nodes}
    assert "common.constants" in node_ids
    assert "common.constants.FileExtensions" in node_ids
    assert "tests" not in node_ids
    assert "tests.test_constants" not in node_ids
    assert "tests.test_constants.test_default_encoding" not in node_ids
    assert {(link.requirement_id, link.target_id) for link in result.links} == {("REQ-1", "common.constants")}
