from __future__ import annotations

from codeui.services.json_io import extract_json_from_stdout


def test_extract_json_from_stdout_handles_logs_before_nested_object() -> None:
    stdout = '''2026-05-13 13:35:42,329 | WARNING | something
{
  "status": "failed",
  "details": {
    "error_code": "project_root_already_registered",
    "warnings": []
  }
}
'''

    payload = extract_json_from_stdout(stdout)

    assert payload["status"] == "failed"
    assert payload["details"]["error_code"] == "project_root_already_registered"
