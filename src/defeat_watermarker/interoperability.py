from __future__ import annotations

import json
import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path, PurePosixPath
from typing import Any

from .digests import content_digest, sha256_bytes
from .models import Artifact, MarkFamily, Modality, VerificationState
from .registry import AdapterRegistry

_MAX_MATRIX_BYTES = 2 * 1024 * 1024
_MAX_CASES = 500
_MAX_ADAPTERS = 16
_MAX_CASE_BYTES = 64 * 1024 * 1024
_MAX_TOTAL_BYTES = 256 * 1024 * 1024
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class InteroperabilityError(ValueError):
    """Raised when an interoperability matrix definition or run is invalid."""


@dataclass(frozen=True, slots=True)
class InteroperabilityCase:
    case_id: str
    path: str
    media_type: str
    modality: Modality

    def __post_init__(self) -> None:
        if not _ID_RE.fullmatch(self.case_id):
            raise InteroperabilityError(f"invalid case_id: {self.case_id}")
        pure = PurePosixPath(self.path)
        if (
            not self.path
            or pure.is_absolute()
            or ".." in pure.parts
            or "." in pure.parts
            or "\\" in self.path
        ):
            raise InteroperabilityError("case path must be a normalized relative POSIX path")
        if not self.media_type or len(self.media_type) > 255:
            raise InteroperabilityError("media_type is missing or too long")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "path": self.path,
            "media_type": self.media_type,
            "modality": self.modality.value,
        }


@dataclass(frozen=True, slots=True)
class InteroperabilityMatrix:
    schema_version: str
    matrix_id: str
    version: str
    description: str
    adapter_ids: tuple[str, ...]
    cases: tuple[InteroperabilityCase, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "0.1":
            raise InteroperabilityError("unsupported interoperability schema_version")
        if not _ID_RE.fullmatch(self.matrix_id):
            raise InteroperabilityError("matrix_id must be a stable identifier")
        if not self.version or len(self.version) > 64:
            raise InteroperabilityError("version must be non-empty and at most 64 characters")
        if len(self.description) > 4000:
            raise InteroperabilityError("description is too long")
        if not 2 <= len(self.adapter_ids) <= _MAX_ADAPTERS:
            raise InteroperabilityError(f"adapter_ids must contain 2..{_MAX_ADAPTERS} entries")
        if len(set(self.adapter_ids)) != len(self.adapter_ids):
            raise InteroperabilityError("adapter_ids must be unique")
        for adapter_id in self.adapter_ids:
            if not _ID_RE.fullmatch(adapter_id):
                raise InteroperabilityError(f"invalid adapter_id: {adapter_id}")
        if not self.cases or len(self.cases) > _MAX_CASES:
            raise InteroperabilityError(f"cases must contain 1..{_MAX_CASES} entries")
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise InteroperabilityError("case_id values must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "matrix_id": self.matrix_id,
            "version": self.version,
            "description": self.description,
            "adapter_ids": list(self.adapter_ids),
            "cases": [case.to_dict() for case in self.cases],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class AdapterObservation:
    adapter_id: str
    supported: bool
    family: MarkFamily | None
    detected: bool | None
    confidence: float | None
    verification_state: VerificationState | None
    provenance_identifier: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "supported": self.supported,
            "family": self.family.value if self.family is not None else None,
            "detected": self.detected,
            "confidence": self.confidence,
            "verification_state": (
                self.verification_state.value if self.verification_state is not None else None
            ),
            "provenance_identifier": self.provenance_identifier,
        }


@dataclass(frozen=True, slots=True)
class InteroperabilityCaseResult:
    case_id: str
    artifact_sha256: str
    byte_length: int
    observations: tuple[AdapterObservation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "artifact_sha256": self.artifact_sha256,
            "byte_length": self.byte_length,
            "observations": [item.to_dict() for item in self.observations],
        }


@dataclass(frozen=True, slots=True)
class PairwiseAgreement:
    left_adapter_id: str
    right_adapter_id: str
    comparable_cases: int
    detection_agreements: int
    detection_disagreements: int
    agreement_rate: float | None
    both_detected: int
    both_not_detected: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_adapter_id": self.left_adapter_id,
            "right_adapter_id": self.right_adapter_id,
            "comparable_cases": self.comparable_cases,
            "detection_agreements": self.detection_agreements,
            "detection_disagreements": self.detection_disagreements,
            "agreement_rate": self.agreement_rate,
            "both_detected": self.both_detected,
            "both_not_detected": self.both_not_detected,
        }


@dataclass(frozen=True, slots=True)
class InteroperabilityReport:
    matrix_id: str
    matrix_version: str
    matrix_digest: str
    cases: tuple[InteroperabilityCaseResult, ...]
    pairs: tuple[PairwiseAgreement, ...]
    schema_version: str = "0.1"

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "matrix_id": self.matrix_id,
            "matrix_version": self.matrix_version,
            "matrix_digest": self.matrix_digest,
            "cases": [case.to_dict() for case in self.cases],
            "pairs": [pair.to_dict() for pair in self.pairs],
        }

    @property
    def report_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, **self.core_dict()}


def _exact_keys(value: dict[str, Any], allowed: frozenset[str], noun: str) -> None:
    extras = sorted(set(value) - allowed)
    missing = sorted(allowed - set(value))
    if extras:
        raise InteroperabilityError(f"{noun} has unknown fields: {', '.join(extras)}")
    if missing:
        raise InteroperabilityError(f"{noun} is missing fields: {', '.join(missing)}")


def matrix_from_dict(payload: dict[str, Any]) -> InteroperabilityMatrix:
    if not isinstance(payload, dict):
        raise InteroperabilityError("interoperability matrix must be a JSON object")
    _exact_keys(
        payload,
        frozenset({"schema_version", "matrix_id", "version", "description", "adapter_ids", "cases"}),
        "matrix",
    )
    raw_adapters = payload["adapter_ids"]
    raw_cases = payload["cases"]
    if not isinstance(raw_adapters, list) or not all(isinstance(item, str) for item in raw_adapters):
        raise InteroperabilityError("adapter_ids must be an array of strings")
    if not isinstance(raw_cases, list):
        raise InteroperabilityError("cases must be an array")
    case_keys = frozenset({"case_id", "path", "media_type", "modality"})
    cases: list[InteroperabilityCase] = []
    for index, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise InteroperabilityError(f"case {index} must be an object")
        _exact_keys(raw, case_keys, f"case {index}")
        try:
            modality = Modality(raw["modality"])
        except (TypeError, ValueError) as exc:
            raise InteroperabilityError(f"case {index} has invalid modality") from exc
        cases.append(
            InteroperabilityCase(
                case_id=str(raw["case_id"]),
                path=str(raw["path"]),
                media_type=str(raw["media_type"]),
                modality=modality,
            )
        )
    return InteroperabilityMatrix(
        schema_version=str(payload["schema_version"]),
        matrix_id=str(payload["matrix_id"]),
        version=str(payload["version"]),
        description=str(payload["description"]),
        adapter_ids=tuple(raw_adapters),
        cases=tuple(cases),
    )


def load_matrix(path: Path) -> InteroperabilityMatrix:
    if path.stat().st_size > _MAX_MATRIX_BYTES:
        raise InteroperabilityError(f"matrix file exceeds {_MAX_MATRIX_BYTES} bytes")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InteroperabilityError(f"could not read interoperability matrix: {exc}") from exc
    return matrix_from_dict(payload)


def _resolve_case_file(root: Path, relative: str) -> Path:
    root = root.resolve(strict=True)
    candidate = (root / relative).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise InteroperabilityError("case path resolves outside the matrix directory") from exc
    if not candidate.is_file():
        raise InteroperabilityError(f"case path is not a regular file: {relative}")
    return candidate


def _pairwise(
    adapter_ids: tuple[str, ...],
    results: tuple[InteroperabilityCaseResult, ...],
) -> tuple[PairwiseAgreement, ...]:
    output: list[PairwiseAgreement] = []
    for left, right in combinations(adapter_ids, 2):
        comparable = agreements = disagreements = both_detected = both_not = 0
        for case in results:
            observations = {item.adapter_id: item for item in case.observations}
            a = observations[left]
            b = observations[right]
            if not a.supported or not b.supported:
                continue
            assert a.detected is not None and b.detected is not None
            comparable += 1
            if a.detected == b.detected:
                agreements += 1
                if a.detected:
                    both_detected += 1
                else:
                    both_not += 1
            else:
                disagreements += 1
        output.append(
            PairwiseAgreement(
                left_adapter_id=left,
                right_adapter_id=right,
                comparable_cases=comparable,
                detection_agreements=agreements,
                detection_disagreements=disagreements,
                agreement_rate=agreements / comparable if comparable else None,
                both_detected=both_detected,
                both_not_detected=both_not,
            )
        )
    return tuple(output)


def run_interoperability_matrix(
    matrix_path: Path,
    registry: AdapterRegistry,
) -> InteroperabilityReport:
    matrix = load_matrix(matrix_path)
    adapters = {adapter_id: registry.get(adapter_id) for adapter_id in matrix.adapter_ids}
    root = matrix_path.parent
    total_bytes = 0
    case_results: list[InteroperabilityCaseResult] = []

    for case in matrix.cases:
        path = _resolve_case_file(root, case.path)
        byte_length = path.stat().st_size
        if byte_length > _MAX_CASE_BYTES:
            raise InteroperabilityError(f"case {case.case_id} exceeds {_MAX_CASE_BYTES} bytes")
        total_bytes += byte_length
        if total_bytes > _MAX_TOTAL_BYTES:
            raise InteroperabilityError(f"matrix exceeds {_MAX_TOTAL_BYTES} total artifact bytes")
        data = path.read_bytes()
        artifact = Artifact(
            data=data,
            media_type=case.media_type,
            name=path.name,
            modality=case.modality,
        )
        observations: list[AdapterObservation] = []
        for adapter_id in matrix.adapter_ids:
            adapter = adapters[adapter_id]
            if not adapter.supports(artifact):
                observations.append(
                    AdapterObservation(
                        adapter_id=adapter_id,
                        supported=False,
                        family=adapter.family,
                        detected=None,
                        confidence=None,
                        verification_state=None,
                        provenance_identifier=None,
                    )
                )
                continue
            detected = adapter.detect(artifact)
            observations.append(
                AdapterObservation(
                    adapter_id=adapter_id,
                    supported=True,
                    family=detected.family,
                    detected=detected.detected,
                    confidence=detected.confidence,
                    verification_state=detected.verification_state,
                    provenance_identifier=detected.provenance_identifier,
                )
            )
        case_results.append(
            InteroperabilityCaseResult(
                case_id=case.case_id,
                artifact_sha256=sha256_bytes(data),
                byte_length=len(data),
                observations=tuple(observations),
            )
        )

    frozen = tuple(case_results)
    return InteroperabilityReport(
        matrix_id=matrix.matrix_id,
        matrix_version=matrix.version,
        matrix_digest=matrix.digest,
        cases=frozen,
        pairs=_pairwise(matrix.adapter_ids, frozen),
    )
