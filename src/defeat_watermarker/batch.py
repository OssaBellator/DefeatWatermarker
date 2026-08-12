from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .builtin_suites import builtin_suite_for
from .cli import _infer_modality, _mutations, _registry
from .digests import content_digest
from .engine import RobustnessEngine
from .evidence import build_evidence_bundle
from .io_utils import DEFAULT_MAX_ARTIFACT_BYTES, read_bounded_bytes
from .metrics import summarize_report
from .models import Artifact
from .scan_evidence import build_scan_evidence

_MAX_BATCH_FILES = 64
_MAX_BATCH_BYTES = 256 * 1024 * 1024
_MAX_ERROR_LENGTH = 1024


class BatchError(ValueError):
    """Raised when a batch request is malformed or exceeds bounded limits."""


@dataclass(frozen=True, slots=True)
class BatchRecord:
    relative_path: str
    media_type: str
    modality: str
    mode: str
    record_id: str | None
    record: dict[str, Any] | None
    error: str | None = None

    def to_index_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "media_type": self.media_type,
            "modality": self.modality,
            "mode": self.mode,
            "record_id": self.record_id,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class BatchResult:
    input_name: str
    recursive: bool
    scan_only: bool
    records: tuple[BatchRecord, ...]
    schema_version: str = "0.1"

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "input_name": self.input_name,
            "recursive": self.recursive,
            "scan_only": self.scan_only,
            "records": [item.to_index_dict() for item in self.records],
        }

    @property
    def batch_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"batch_id": self.batch_id, **self.core_dict()}

    @property
    def failed_records(self) -> int:
        return sum(1 for item in self.records if item.error is not None)


def _media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if path.suffix.lower() == ".ppm":
        return "image/x-portable-pixmap"
    return guessed or "application/octet-stream"


def _safe_relative(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    if relative.startswith("../") or relative == "..":
        raise BatchError("batch path escaped input root")
    return relative


def _candidate_files(root: Path, *, recursive: bool) -> tuple[Path, ...]:
    if root.is_file():
        return (root,)
    if not root.is_dir():
        raise BatchError("batch input must be a regular file or directory")

    iterator = root.rglob("*") if recursive else root.glob("*")
    files = tuple(
        sorted(
            (
                path
                for path in iterator
                if path.is_file() and not path.is_symlink()
            ),
            key=lambda item: item.relative_to(root).as_posix(),
        )
    )
    if not files:
        raise BatchError("batch input contains no regular files")
    if len(files) > _MAX_BATCH_FILES:
        raise BatchError(f"batch exceeds {_MAX_BATCH_FILES} files")
    return files


def run_batch(
    input_path: Path,
    *,
    recursive: bool = False,
    scan_only: bool = False,
    trust_anchors: Path | None = None,
    detector_plugins: tuple[str, ...] = (),
) -> BatchResult:
    if input_path.is_symlink():
        raise BatchError("batch input root must not be a symlink")
    resolved = input_path.resolve()
    files = _candidate_files(resolved, recursive=recursive)
    root = resolved.parent if resolved.is_file() else resolved
    total_bytes = 0
    records: list[BatchRecord] = []
    registry = _registry(trust_anchors, detector_plugins)
    mutations = _mutations()

    for path in files:
        relative = path.name if resolved.is_file() else _safe_relative(path, root)
        size = path.stat().st_size
        media_type = _media_type(path)
        modality = _infer_modality(media_type)
        if size > DEFAULT_MAX_ARTIFACT_BYTES:
            message = f"source artifact exceeds max bytes: {size}"
            records.append(
                BatchRecord(
                    relative_path=relative,
                    media_type=media_type,
                    modality=modality.value,
                    mode="error",
                    record_id=None,
                    record=None,
                    error=message[:_MAX_ERROR_LENGTH],
                )
            )
            continue
        total_bytes += size
        if total_bytes > _MAX_BATCH_BYTES:
            raise BatchError(f"batch exceeds {_MAX_BATCH_BYTES} total source bytes")

        try:
            artifact = Artifact(
                data=read_bounded_bytes(path),
                media_type=media_type,
                name=path.name,
                modality=modality,
            )
            suite = None if scan_only else builtin_suite_for(modality)
            if suite is None:
                scan = build_scan_evidence(artifact, registry)
                records.append(
                    BatchRecord(
                        relative_path=relative,
                        media_type=media_type,
                        modality=modality.value,
                        mode="scan",
                        record_id=scan.scan_id,
                        record=scan.to_dict(),
                    )
                )
            else:
                report = RobustnessEngine(registry, mutations).evaluate(
                    artifact, suite.scenarios
                )
                summary = summarize_report(report)
                evidence = build_evidence_bundle(artifact, suite, report, summary)
                records.append(
                    BatchRecord(
                        relative_path=relative,
                        media_type=media_type,
                        modality=modality.value,
                        mode="attack",
                        record_id=evidence.evidence_id,
                        record=evidence.to_dict(),
                    )
                )
        except (OSError, UnicodeError, ValueError, KeyError) as exc:
            records.append(
                BatchRecord(
                    relative_path=relative,
                    media_type=media_type,
                    modality=modality.value,
                    mode="error",
                    record_id=None,
                    record=None,
                    error=str(exc)[:_MAX_ERROR_LENGTH],
                )
            )

    return BatchResult(
        input_name=resolved.name,
        recursive=recursive,
        scan_only=scan_only,
        records=tuple(records),
    )
