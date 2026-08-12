from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .provenance import ProvenanceGraph


class Modality(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    DOCUMENT = "document"
    BINARY = "binary"
    UNKNOWN = "unknown"


class MarkFamily(str, Enum):
    METADATA = "metadata"
    SIGNED_PROVENANCE = "signed_provenance"
    PERCEPTUAL = "perceptual"
    STATISTICAL = "statistical"
    FINGERPRINT = "fingerprint"
    REGISTRY = "registry"
    HARDWARE_ATTESTATION = "hardware_attestation"
    UNKNOWN = "unknown"


class VerificationState(str, Enum):
    NOT_EVALUATED = "not_evaluated"
    WELL_FORMED = "well_formed"
    VALID = "valid"
    TRUSTED = "trusted"
    INVALID = "invalid"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Artifact:
    data: bytes = field(repr=False)
    media_type: str = "application/octet-stream"
    name: str = "artifact"
    modality: Modality = Modality.UNKNOWN


@dataclass(frozen=True, slots=True)
class DetectionResult:
    adapter_id: str
    family: MarkFamily
    detected: bool
    confidence: float
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    provenance_identifier: str | None = None
    cryptographically_verified: bool = False
    registry_verified: bool = False
    verification_state: VerificationState = VerificationState.NOT_EVALUATED
    validation_codes: tuple[str, ...] = ()
    provenance_graph: ProvenanceGraph | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "family": self.family.value,
            "detected": self.detected,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "warnings": list(self.warnings),
            "provenance_identifier": self.provenance_identifier,
            "cryptographically_verified": self.cryptographically_verified,
            "registry_verified": self.registry_verified,
            "verification_state": self.verification_state.value,
            "validation_codes": list(self.validation_codes),
            "provenance_graph": (
                self.provenance_graph.to_dict() if self.provenance_graph is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class MutationScenario:
    scenario_id: str
    mutation_id: str
    modality: Modality
    transformation_family: str
    severity: str = "control"
    generation_count: int = 1

    def __post_init__(self) -> None:
        if self.generation_count < 1:
            raise ValueError("generation_count must be at least 1")


@dataclass(frozen=True, slots=True)
class DetectionComparison:
    adapter_id: str
    baseline: DetectionResult
    after: DetectionResult

    @property
    def survived(self) -> bool:
        return self.baseline.detected and self.after.detected

    @property
    def confidence_delta(self) -> float:
        return self.after.confidence - self.baseline.confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "survived": self.survived,
            "confidence_delta": self.confidence_delta,
            "baseline": self.baseline.to_dict(),
            "after": self.after.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ScenarioEvaluation:
    scenario: MutationScenario
    comparisons: tuple[DetectionComparison, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": {
                "scenario_id": self.scenario.scenario_id,
                "mutation_id": self.scenario.mutation_id,
                "modality": self.scenario.modality.value,
                "transformation_family": self.scenario.transformation_family,
                "severity": self.scenario.severity,
                "generation_count": self.scenario.generation_count,
            },
            "comparisons": [item.to_dict() for item in self.comparisons],
        }


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    artifact_name: str
    media_type: str
    baseline: tuple[DetectionResult, ...]
    scenarios: tuple[ScenarioEvaluation, ...]

    def to_dict(self) -> dict[str, Any]:
        # Deliberately excludes Artifact.data and all transformed derivatives.
        return {
            "artifact_name": self.artifact_name,
            "media_type": self.media_type,
            "baseline": [item.to_dict() for item in self.baseline],
            "scenarios": [item.to_dict() for item in self.scenarios],
        }
