from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .digests import content_digest
from .evidence import verify_evidence_document
from .scan_evidence import verify_scan_document

_MAX_BATCH_INDEX_BYTES = 4 * 1024 * 1024
_MAX_RECORD_BYTES = 20 * 1024 * 1024
_MAX_RECORDS = 64


class BatchVerificationError(ValueError):
    """Raised when a batch directory cannot be safely read."""


@dataclass(frozen=True, slots=True)
class BatchVerificationResult:
    valid: bool
    batch_id: str | None
    checks: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "batch_id": self.batch_id,
            "checks": list(self.checks),
            "errors": list(self.errors),
        }


def _load_json(path: Path, *, max_bytes: int) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise BatchVerificationError(f"expected regular file: {path.name}")
    if path.stat().st_size > max_bytes:
        raise BatchVerificationError(f"file exceeds bounded size: {path.name}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchVerificationError(f"could not read {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BatchVerificationError(f"{path.name} must contain a JSON object")
    return payload


def _looks_like_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def verify_batch_directory(directory: Path) -> BatchVerificationResult:
    if directory.is_symlink():
        raise BatchVerificationError("batch output directory must not be a symlink")
    root = directory.resolve()
    if not root.is_dir():
        raise BatchVerificationError("batch output path must be a directory")

    payload = _load_json(root / "batch.json", max_bytes=_MAX_BATCH_INDEX_BYTES)
    required = {
        "batch_id",
        "schema_version",
        "input_name",
        "recursive",
        "scan_only",
        "records",
    }
    checks: list[str] = []
    errors: list[str] = []
    if set(payload) != required:
        missing = sorted(required - set(payload))
        extras = sorted(set(payload) - required)
        if missing:
            errors.append(f"batch index missing fields: {', '.join(missing)}")
        if extras:
            errors.append(f"batch index has unknown fields: {', '.join(extras)}")
        return BatchVerificationResult(False, None, tuple(checks), tuple(errors))

    batch_id = payload.get("batch_id")
    if not _looks_like_sha256(batch_id):
        errors.append("batch_id is not a lowercase SHA-256 digest")
    else:
        core = {key: value for key, value in payload.items() if key != "batch_id"}
        if content_digest(core) != batch_id:
            errors.append("batch_id does not match batch index core")
        else:
            checks.append("batch_id")

    if payload.get("schema_version") != "0.1":
        errors.append("unsupported batch schema_version")
    else:
        checks.append("schema_version")

    records = payload.get("records")
    if not isinstance(records, list) or not 1 <= len(records) <= _MAX_RECORDS:
        errors.append("records must contain between 1 and 64 entries")
        return BatchVerificationResult(
            valid=False,
            batch_id=batch_id if isinstance(batch_id, str) else None,
            checks=tuple(checks),
            errors=tuple(errors),
        )

    records_dir = root / "records"
    verified_record_ids: set[str] = set()
    record_keys = {
        "relative_path",
        "media_type",
        "modality",
        "mode",
        "record_id",
        "error",
    }
    for index, entry in enumerate(records):
        if not isinstance(entry, dict) or set(entry) != record_keys:
            errors.append(f"record {index} has invalid fields")
            continue
        mode = entry.get("mode")
        record_id = entry.get("record_id")
        error = entry.get("error")
        if mode == "error":
            if record_id is not None or not isinstance(error, str) or not error:
                errors.append(f"record {index} has invalid error binding")
            continue
        if mode not in {"scan", "attack"}:
            errors.append(f"record {index} has invalid mode")
            continue
        if error is not None or not _looks_like_sha256(record_id):
            errors.append(f"record {index} has invalid record binding")
            continue

        record_path = records_dir / f"{record_id}.json"
        try:
            record_payload = _load_json(record_path, max_bytes=_MAX_RECORD_BYTES)
        except BatchVerificationError as exc:
            errors.append(f"record {index}: {exc}")
            continue
        if mode == "scan":
            verification = verify_scan_document(record_payload)
            actual_id = verification.scan_id
        else:
            verification = verify_evidence_document(record_payload)
            actual_id = verification.evidence_id
        if not verification.valid:
            errors.append(f"record {index} failed {mode} verification")
            continue
        if actual_id != record_id:
            errors.append(f"record {index} id does not match referenced record")
            continue
        verified_record_ids.add(record_id)

    if not errors:
        checks.append(f"records:{len(verified_record_ids)}")

    return BatchVerificationResult(
        valid=not errors,
        batch_id=batch_id if isinstance(batch_id, str) else None,
        checks=tuple(checks),
        errors=tuple(errors),
    )
