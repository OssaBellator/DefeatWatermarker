#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_DIR = ROOT / "schemas"
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
ID_PREFIX = "https://github.com/OssaBellator/DefeatWatermarker/schemas/"


def audit_schema_directory(schema_dir: Path) -> tuple[int, tuple[str, ...]]:
    errors: list[str] = []
    paths = tuple(sorted(schema_dir.glob("*.schema.json")))
    if not paths:
        return 0, ("expected at least one published schema",)

    seen_ids: dict[str, str] = {}
    for path in paths:
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{path.name}: schema root must be an object")
            continue

        if payload.get("$schema") != DRAFT_2020_12:
            errors.append(f"{path.name}: unexpected $schema")
        if payload.get("type") != "object":
            errors.append(f"{path.name}: root type must be object")
        if payload.get("additionalProperties") is not False:
            errors.append(f"{path.name}: root additionalProperties must be false")
        title = payload.get("title")
        if not isinstance(title, str) or not title:
            errors.append(f"{path.name}: title must be a non-empty string")

        expected_id = ID_PREFIX + path.name
        schema_id = payload.get("$id")
        if schema_id != expected_id:
            errors.append(
                f"{path.name}: $id must be {expected_id!r}, got {schema_id!r}"
            )
        elif schema_id in seen_ids:
            errors.append(
                f"{path.name}: duplicate $id already used by {seen_ids[schema_id]}"
            )
        else:
            seen_ids[schema_id] = path.name

        try:
            round_trip = json.loads(json.dumps(payload, sort_keys=True))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: not canonical JSON-compatible data: {exc}")
        else:
            if not isinstance(round_trip, dict):
                errors.append(f"{path.name}: JSON round-trip did not produce an object")

    return len(paths), tuple(errors)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scripts/test/schema_audit.py")
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=DEFAULT_SCHEMA_DIR,
        help="schema directory to audit; defaults to repository schemas/",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    count, errors = audit_schema_directory(args.schema_dir)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"OK: {count} published schemas use strict Draft 2020-12 repository IDs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
