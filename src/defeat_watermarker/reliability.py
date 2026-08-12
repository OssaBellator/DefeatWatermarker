from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .digests import content_digest, sha256_bytes
from .models import Artifact, Modality, VerificationState
from .registry import AdapterRegistry

_MAX_CORPUS_BYTES = 2 * 1024 * 1024
_MAX_CASES = 1000
_MAX_CASE_BYTES = 64 * 1024 * 1024
_MAX_TOTAL_BYTES = 256 * 1024 * 1024
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class ReliabilityError(ValueError):
    """Raised when a fixed reliability corpus or evaluation is invalid."""


@dataclass(frozen=True, slots=True)
class ReliabilityCase:
    case_id: str
    path: str
    media_type: str
    modality: Modality
    expected_detected: bool

    def __post_init__(self) -> None:
        if not _ID_RE.fullmatch(self.case_id):
            raise ReliabilityError(f"invalid case_id: {self.case_id}")
        if not self.media_type or len(self.media_type) > 255:
            raise ReliabilityError("media_type is missing or too long")
        pure = PurePosixPath(self.path)
        if (
            not self.path
            or pure.is_absolute()
            or ".." in pure.parts
            or "." in pure.parts
            or "\\" in self.path
        ):
            raise ReliabilityError("case path must be a normalized relative POSIX path")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "path": self.path,
            "media_type": self.media_type,
            "modality": self.modality.value,
            "expected_detected": self.expected_detected,
        }


@dataclass(frozen=True, slots=True)
class ReliabilityCorpus:
    schema_version: str
    corpus_id: str
    version: str
    adapter_id: str
    description: str
    cases: tuple[ReliabilityCase, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "0.1":
            raise ReliabilityError("unsupported reliability corpus schema_version")
        for noun, value in (("corpus_id", self.corpus_id), ("adapter_id", self.adapter_id)):
            if not _ID_RE.fullmatch(value):
                raise ReliabilityError(f"{noun} must be a stable identifier")
        if not self.version or len(self.version) > 64:
            raise ReliabilityError("version must be non-empty and at most 64 characters")
        if len(self.description) > 4000:
            raise ReliabilityError("description is too long")
        if not self.cases or len(self.cases) > _MAX_CASES:
            raise ReliabilityError(f"corpus must contain 1..{_MAX_CASES} cases")
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ReliabilityError("case_id values must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "corpus_id": self.corpus_id,
            "version": self.version,
            "adapter_id": self.adapter_id,
            "description": self.description,
            "cases": [case.to_dict() for case in self.cases],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class ReliabilityCaseResult:
    case_id: str
    artifact_sha256: str
    byte_length: int
    expected_detected: bool
    actual_detected: bool
    confidence: float
    verification_state: VerificationState

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "artifact_sha256": self.artifact_sha256,
            "byte_length": self.byte_length,
            "expected_detected": self.expected_detected,
            "actual_detected": self.actual_detected,
            "confidence": self.confidence,
            "verification_state": self.verification_state.value,
        }


@dataclass(frozen=True, slots=True)
class ReliabilitySummary:
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    accuracy: float
    precision: float | None
    recall: float | None
    specificity: float | None
    false_positive_rate: float | None
    false_negative_rate: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "true_positive": self.true_positive,
            "true_negative": self.true_negative,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "specificity": self.specificity,
            "false_positive_rate": self.false_positive_rate,
            "false_negative_rate": self.false_negative_rate,
        }


@dataclass(frozen=True, slots=True)
class ReliabilityReport:
    corpus_id: str
    corpus_version: str
    corpus_digest: str
    adapter_id: str
    cases: tuple[ReliabilityCaseResult, ...]
    summary: ReliabilitySummary
    schema_version: str = "0.1"

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "corpus_id": self.corpus_id,
            "corpus_version": self.corpus_version,
            "corpus_digest": self.corpus_digest,
            "adapter_id": self.adapter_id,
            "cases": [case.to_dict() for case in self.cases],
            "summary": self.summary.to_dict(),
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
        raise ReliabilityError(f"{noun} has unknown fields: {', '.join(extras)}")
    if missing:
        raise ReliabilityError(f"{noun} is missing fields: {', '.join(missing)}")


def corpus_from_dict(payload: dict[str, Any]) -> ReliabilityCorpus:
    if not isinstance(payload, dict):
        raise ReliabilityError("reliability corpus must be a JSON object")
    _exact_keys(
        payload,
        frozenset(
            {"schema_version", "corpus_id", "version", "adapter_id", "description", "cases"}
        ),
        "corpus",
    )
    raw_cases = payload["cases"]
    if not isinstance(raw_cases, list):
        raise ReliabilityError("cases must be an array")
    case_keys = frozenset({"case_id", "path", "media_type", "modality", "expected_detected"})
    cases: list[ReliabilityCase] = []
    for index, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise ReliabilityError(f"case {index} must be an object")
        _exact_keys(raw, case_keys, f"case {index}")
        if type(raw["expected_detected"]) is not bool:
            raise ReliabilityError(f"case {index} expected_detected must be boolean")
        try:
            modality = Modality(raw["modality"])
        except (TypeError, ValueError) as exc:
            raise ReliabilityError(f"case {index} has invalid modality") from exc
        cases.append(
            ReliabilityCase(
                case_id=str(raw["case_id"]),
                path=str(raw["path"]),
                media_type=str(raw["media_type"]),
                modality=modality,
                expected_detected=raw["expected_detected"],
            )
        )
    return ReliabilityCorpus(
        schema_version=str(payload["schema_version"]),
        corpus_id=str(payload["corpus_id"]),
        version=str(payload["version"]),
        adapter_id=str(payload["adapter_id"]),
        description=str(payload["description"]),
        cases=tuple(cases),
    )


def load_corpus(path: Path) -> ReliabilityCorpus:
    if path.stat().st_size > _MAX_CORPUS_BYTES:
        raise ReliabilityError(f"corpus file exceeds {_MAX_CORPUS_BYTES} bytes")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReliabilityError(f"could not read reliability corpus: {exc}") from exc
    return corpus_from_dict(payload)


def _resolve_case_file(root: Path, relative: str) -> Path:
    root = root.resolve(strict=True)
    candidate = (root / relative).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ReliabilityError("case path resolves outside the corpus directory") from exc
    if not candidate.is_file():
        raise ReliabilityError(f"case path is not a regular file: {relative}")
    return candidate


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _summary(results: tuple[ReliabilityCaseResult, ...]) -> ReliabilitySummary:
    tp = sum(1 for item in results if item.expected_detected and item.actual_detected)
    tn = sum(1 for item in results if not item.expected_detected and not item.actual_detected)
    fp = sum(1 for item in results if not item.expected_detected and item.actual_detected)
    fn = sum(1 for item in results if item.expected_detected and not item.actual_detected)
    total = len(results)
    return ReliabilitySummary(
        true_positive=tp,
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
        accuracy=(tp + tn) / total,
        precision=_ratio(tp, tp + fp),
        recall=_ratio(tp, tp + fn),
        specificity=_ratio(tn, tn + fp),
        false_positive_rate=_ratio(fp, fp + tn),
        false_negative_rate=_ratio(fn, fn + tp),
    )


def run_reliability_benchmark(
    corpus_path: Path,
    registry: AdapterRegistry,
) -> ReliabilityReport:
    corpus = load_corpus(corpus_path)
    adapter = registry.get(corpus.adapter_id)
    root = corpus_path.parent
    results: list[ReliabilityCaseResult] = []
    total_bytes = 0

    for case in corpus.cases:
        path = _resolve_case_file(root, case.path)
        byte_length = path.stat().st_size
        if byte_length > _MAX_CASE_BYTES:
            raise ReliabilityError(f"case {case.case_id} exceeds {_MAX_CASE_BYTES} bytes")
        total_bytes += byte_length
        if total_bytes > _MAX_TOTAL_BYTES:
            raise ReliabilityError(f"corpus exceeds {_MAX_TOTAL_BYTES} total artifact bytes")
        data = path.read_bytes()
        artifact = Artifact(
            data=data,
            media_type=case.media_type,
            name=path.name,
            modality=case.modality,
        )
        if not adapter.supports(artifact):
            raise ReliabilityError(
                f"adapter {adapter.adapter_id} does not support case {case.case_id} modality"
            )
        detection = adapter.detect(artifact)
        results.append(
            ReliabilityCaseResult(
                case_id=case.case_id,
                artifact_sha256=sha256_bytes(data),
                byte_length=len(data),
                expected_detected=case.expected_detected,
                actual_detected=detection.detected,
                confidence=detection.confidence,
                verification_state=detection.verification_state,
            )
        )

    frozen = tuple(results)
    return ReliabilityReport(
        corpus_id=corpus.corpus_id,
        corpus_version=corpus.version,
        corpus_digest=corpus.digest,
        adapter_id=corpus.adapter_id,
        cases=frozen,
        summary=_summary(frozen),
    )
