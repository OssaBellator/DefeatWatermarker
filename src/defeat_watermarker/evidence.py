from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .digests import content_digest, sha256_bytes
from .metrics import GatePolicy, GateResult, RobustnessSummary
from .models import Artifact, EvaluationReport
from .suites import RobustnessSuite

_MAX_EVIDENCE_BYTES = 20 * 1024 * 1024
_SHA256_LENGTH = 64


class EvidenceError(ValueError):
    """Raised when an evidence document is malformed or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    sha256: str
    byte_length: int
    media_type: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "byte_length": self.byte_length,
            "media_type": self.media_type,
            "name": self.name,
        }


@dataclass(frozen=True, slots=True)
class EvaluationEvidence:
    """Content-addressed evidence bundle that never embeds source or derivative bytes."""

    artifact: ArtifactReference
    suite_id: str
    suite_version: str
    suite_digest: str
    report_digest: str
    report: EvaluationReport
    summary: RobustnessSummary
    gate_policy: GatePolicy | None = None
    gate: GateResult | None = None
    schema_version: str = "0.2"

    def __post_init__(self) -> None:
        if (self.gate_policy is None) != (self.gate is None):
            raise ValueError("gate_policy and gate must either both be present or both be absent")

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact": self.artifact.to_dict(),
            "suite": {
                "suite_id": self.suite_id,
                "version": self.suite_version,
                "digest": self.suite_digest,
            },
            "report_digest": self.report_digest,
            "report": self.report.to_dict(),
            "summary": self.summary.to_dict(),
            "gate_policy": (
                self.gate_policy.to_dict() if self.gate_policy is not None else None
            ),
            "gate": self.gate.to_dict() if self.gate is not None else None,
        }

    @property
    def evidence_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"evidence_id": self.evidence_id, **self.core_dict()}


@dataclass(frozen=True, slots=True)
class EvidenceVerificationResult:
    valid: bool
    evidence_id: str | None
    checks: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "evidence_id": self.evidence_id,
            "checks": list(self.checks),
            "errors": list(self.errors),
        }


def build_evidence_bundle(
    artifact: Artifact,
    suite: RobustnessSuite,
    report: EvaluationReport,
    summary: RobustnessSummary,
    *,
    gate_policy: GatePolicy | None = None,
    gate: GateResult | None = None,
) -> EvaluationEvidence:
    return EvaluationEvidence(
        artifact=ArtifactReference(
            sha256=sha256_bytes(artifact.data),
            byte_length=len(artifact.data),
            media_type=artifact.media_type,
            name=artifact.name,
        ),
        suite_id=suite.suite_id,
        suite_version=suite.version,
        suite_digest=suite.digest,
        report_digest=content_digest(report.to_dict()),
        report=report,
        summary=summary,
        gate_policy=gate_policy,
        gate=gate,
    )


def _looks_like_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _SHA256_LENGTH
        and all(char in "0123456789abcdef" for char in value)
    )


def verify_evidence_document(
    payload: dict[str, Any],
    *,
    suite: RobustnessSuite | None = None,
) -> EvidenceVerificationResult:
    required = {
        "evidence_id",
        "schema_version",
        "artifact",
        "suite",
        "report_digest",
        "report",
        "summary",
        "gate_policy",
        "gate",
    }
    errors: list[str] = []
    checks: list[str] = []
    if set(payload) != required:
        missing = sorted(required - set(payload))
        extras = sorted(set(payload) - required)
        if missing:
            errors.append(f"missing fields: {', '.join(missing)}")
        if extras:
            errors.append(f"unknown fields: {', '.join(extras)}")
        return EvidenceVerificationResult(False, None, tuple(checks), tuple(errors))

    evidence_id = payload.get("evidence_id")
    if not _looks_like_sha256(evidence_id):
        errors.append("evidence_id is not a lowercase SHA-256 digest")
    else:
        core = {key: value for key, value in payload.items() if key != "evidence_id"}
        if content_digest(core) != evidence_id:
            errors.append("evidence_id does not match the evidence core")
        else:
            checks.append("evidence_id")

    report_digest = payload.get("report_digest")
    if not _looks_like_sha256(report_digest):
        errors.append("report_digest is not a lowercase SHA-256 digest")
    elif content_digest(payload.get("report")) != report_digest:
        errors.append("report_digest does not match report")
    else:
        checks.append("report_digest")

    artifact = payload.get("artifact")
    if not isinstance(artifact, dict) or not _looks_like_sha256(artifact.get("sha256")):
        errors.append("artifact reference is missing a valid SHA-256 digest")
    else:
        checks.append("artifact_reference")

    suite_ref = payload.get("suite")
    if not isinstance(suite_ref, dict) or not _looks_like_sha256(suite_ref.get("digest")):
        errors.append("suite reference is missing a valid SHA-256 digest")
    elif suite is not None:
        if suite_ref.get("digest") != suite.digest:
            errors.append("suite digest does not match supplied suite")
        elif suite_ref.get("suite_id") != suite.suite_id or suite_ref.get("version") != suite.version:
            errors.append("suite identity does not match supplied suite")
        else:
            checks.append("suite_digest")

    gate_policy = payload.get("gate_policy")
    gate = payload.get("gate")
    if (gate_policy is None) != (gate is None):
        errors.append("gate_policy and gate must either both be present or both be absent")
    else:
        checks.append("gate_binding")

    return EvidenceVerificationResult(
        valid=not errors,
        evidence_id=evidence_id if isinstance(evidence_id, str) else None,
        checks=tuple(checks),
        errors=tuple(errors),
    )


def load_evidence_document(path: Path) -> dict[str, Any]:
    if path.stat().st_size > _MAX_EVIDENCE_BYTES:
        raise EvidenceError(f"evidence file exceeds {_MAX_EVIDENCE_BYTES} bytes")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"could not read evidence: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceError("evidence document must be a JSON object")
    return payload
