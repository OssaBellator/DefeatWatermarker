from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .digests import content_digest, sha256_bytes
from .metrics import RobustnessSummary
from .models import Artifact, EvaluationReport
from .suites import RobustnessSuite


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
    schema_version: str = "0.1"

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
        }

    @property
    def evidence_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"evidence_id": self.evidence_id, **self.core_dict()}


def build_evidence_bundle(
    artifact: Artifact,
    suite: RobustnessSuite,
    report: EvaluationReport,
    summary: RobustnessSummary,
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
    )
