from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "test" / "schema_audit.py"
SPEC = importlib.util.spec_from_file_location("defeat_watermarker_schema_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def _schema(name: str, *, schema_id: str | None = None) -> dict[str, object]:
    return {
        "$schema": AUDIT.DRAFT_2020_12,
        "$id": schema_id or AUDIT.ID_PREFIX + name,
        "title": f"Fixture {name}",
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    }


def _write(directory: Path, name: str, payload: dict[str, object]) -> None:
    (directory / name).write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def test_schema_audit_accepts_strict_repository_ids(tmp_path: Path) -> None:
    name = "fixture-v0.1.schema.json"
    _write(tmp_path, name, _schema(name))

    count, errors = AUDIT.audit_schema_directory(tmp_path)

    assert count == 1
    assert errors == ()


def test_schema_audit_rejects_non_repository_id(tmp_path: Path) -> None:
    name = "fixture-v0.1.schema.json"
    _write(
        tmp_path,
        name,
        _schema(name, schema_id="https://example.invalid/fixture.schema.json"),
    )

    count, errors = AUDIT.audit_schema_directory(tmp_path)

    assert count == 1
    assert any("$id must be" in error for error in errors)


def test_schema_audit_rejects_duplicate_schema_ids(tmp_path: Path) -> None:
    first = "first-v0.1.schema.json"
    second = "second-v0.1.schema.json"
    duplicate_id = AUDIT.ID_PREFIX + first
    _write(tmp_path, first, _schema(first, schema_id=duplicate_id))
    _write(tmp_path, second, _schema(second, schema_id=duplicate_id))

    count, errors = AUDIT.audit_schema_directory(tmp_path)

    assert count == 2
    assert any("duplicate $id" in error for error in errors)
    assert any("$id must be" in error for error in errors)


def test_schema_audit_rejects_missing_root_strictness(tmp_path: Path) -> None:
    name = "loose-v0.1.schema.json"
    payload = _schema(name)
    payload["additionalProperties"] = True
    _write(tmp_path, name, payload)

    _, errors = AUDIT.audit_schema_directory(tmp_path)

    assert any("additionalProperties must be false" in error for error in errors)
