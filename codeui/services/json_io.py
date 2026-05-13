from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codeui.errors import ApiError


def read_json_file(path: Path, *, error_code: str = "ARTIFACT_READ_ERROR") -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise ApiError(error_code, f"JSON file not found: {path}", status_code=404, details={"path": str(path)}) from exc
    except json.JSONDecodeError as exc:
        raise ApiError(
            error_code,
            f"Invalid JSON file: {path}",
            status_code=500,
            details={"path": str(path), "line": exc.lineno, "column": exc.colno, "message": exc.msg},
        ) from exc
    except OSError as exc:
        raise ApiError(error_code, f"Cannot read JSON file: {path}", status_code=500, details={"path": str(path), "error": str(exc)}) from exc


def write_json_file(path: Path, payload: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
            fh.write("\n")
        tmp_path.replace(path)
    except OSError as exc:
        raise ApiError("ARTIFACT_WRITE_ERROR", f"Cannot write JSON file: {path}", status_code=500, details={"path": str(path), "error": str(exc)}) from exc


def extract_json_from_stdout(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        raise ApiError("CODECOLLECTOR_EMPTY_OUTPUT", "codecollector returned empty stdout", status_code=502)

    # Normal case: stdout is valid JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # codecollector CLI может писать лог-строки перед JSON. Ищем последний полный
    # JSON object/array, а не последний символ "{" внутри вложенного блока.
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            payload, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if text[start + end :].strip():
            continue
        return payload

    raise ApiError(
        "CODECOLLECTOR_INVALID_OUTPUT",
        "codecollector stdout does not contain valid JSON",
        status_code=502,
        details={"stdout_tail": text[-2000:]},
    )
