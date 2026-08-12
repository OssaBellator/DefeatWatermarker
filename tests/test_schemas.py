from __future__ import annotations

import json
from pathlib import Path


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def test_all_published_schemas_are_strict_draft_2020_12_documents() -> None:
    paths = sorted(SCHEMA_DIR.glob("*.schema.json"))
    assert paths, "expected at least one published schema"

    ids: set[str] = set()
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert payload["type"] == "object"
        assert payload["additionalProperties"] is False
        assert isinstance(payload["title"], str) and payload["title"]
        schema_id = payload["$id"]
        assert schema_id.startswith("https://github.com/OssaBellator/DefeatWatermarker/schemas/")
        assert schema_id.endswith(path.name)
        assert schema_id not in ids
        ids.add(schema_id)


def test_schema_documents_are_canonical_json_objects_not_duplicate_names() -> None:
    paths = sorted(SCHEMA_DIR.glob("*.schema.json"))
    names = [path.name for path in paths]
    assert len(names) == len(set(names))
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Round-tripping catches non-JSON values and keeps these artifacts friendly to
        # non-Python tooling without adding a runtime jsonschema dependency.
        assert isinstance(json.loads(json.dumps(payload, sort_keys=True)), dict)
