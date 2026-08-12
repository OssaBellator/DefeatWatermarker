from __future__ import annotations

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.detector_conformance import (
    run_detector_conformance,
    verify_conformance_document,
)
from defeat_watermarker.digests import content_digest
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality


class GoodAdapter(WatermarkAdapter):
    adapter_id = "fixture.conformance.good.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def runtime_identity(self):
        return ("model=fixture-v1",)

    def detect(self, artifact: Artifact) -> DetectionResult:
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=True,
            confidence=0.9,
        )


class WrongResultAdapter(GoodAdapter):
    adapter_id = "fixture.conformance.wrong-id.v1"

    def detect(self, artifact: Artifact) -> DetectionResult:
        return DetectionResult(
            adapter_id="fixture.other.v1",
            family=self.family,
            detected=True,
            confidence=0.9,
        )


class RemovalSurfaceAdapter(GoodAdapter):
    adapter_id = "fixture.conformance.remove.v1"

    def remove(self, artifact: Artifact) -> Artifact:
        return artifact


class NondeterministicAdapter(GoodAdapter):
    adapter_id = "fixture.conformance.nondeterministic.v1"

    def __init__(self) -> None:
        self._count = 0

    def detect(self, artifact: Artifact) -> DetectionResult:
        self._count += 1
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=bool(self._count % 2),
            confidence=0.9,
        )


class MutatingSupportAdapter(GoodAdapter):
    adapter_id = "fixture.conformance.mutating-support.v1"

    def supports(self, artifact: Artifact) -> bool:
        object.__setattr__(artifact, "name", "mutated.txt")
        return True


class RuntimeChangesAfterDetectionAdapter(GoodAdapter):
    adapter_id = "fixture.conformance.runtime-change.v1"

    def __init__(self) -> None:
        self._generation = 0

    def runtime_identity(self):
        return (f"generation={self._generation}",)

    def detect(self, artifact: Artifact) -> DetectionResult:
        self._generation += 1
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=True,
            confidence=0.9,
        )


class NondeterministicSupportsAdapter(GoodAdapter):
    adapter_id = "fixture.conformance.supports-change.v1"

    def __init__(self) -> None:
        self._count = 0

    def supports(self, artifact: Artifact) -> bool:
        self._count += 1
        return bool(self._count % 2)


class NondeterministicCapabilitiesAdapter(GoodAdapter):
    adapter_id = "fixture.conformance.capabilities-change.v1"

    def __init__(self) -> None:
        self._count = 0

    def capabilities(self):
        self._count += 1
        return ("detect",) if self._count % 2 else ("detect", "unstable")


def _artifact() -> Artifact:
    return Artifact(
        data=b"fixed detector conformance fixture",
        media_type="text/plain",
        name="fixture.txt",
        modality=Modality.TEXT,
    )


def _rebind(payload: dict[str, object]) -> None:
    payload["report_id"] = content_digest(
        {key: value for key, value in payload.items() if key != "report_id"}
    )


def test_read_only_deterministic_adapter_passes_conformance() -> None:
    report = run_detector_conformance("fixture-good", GoodAdapter(), _artifact())
    verification = verify_conformance_document(report.to_dict())

    assert report.passed is True
    assert verification.valid is True
    assert "read_only_capability" in report.checks
    assert "capabilities_deterministic" in report.checks
    assert "supports_deterministic" in report.checks
    assert "deterministic_detection" in report.checks
    assert "runtime_identity_stable" in report.checks
    assert "source_unchanged" in report.checks
    assert "status_semantics" in verification.checks
    assert len(report.report_id) == 64


def test_result_adapter_id_mismatch_fails_conformance() -> None:
    report = run_detector_conformance(
        "fixture-wrong-id", WrongResultAdapter(), _artifact()
    )

    assert report.passed is False
    assert any("adapter_id does not match" in error for error in report.errors)


def test_adapter_with_remove_surface_fails_read_only_conformance() -> None:
    report = run_detector_conformance(
        "fixture-remove", RemovalSurfaceAdapter(), _artifact()
    )

    assert report.passed is False
    assert any("removal capability" in error for error in report.errors)


def test_nondeterministic_detection_fails_conformance() -> None:
    report = run_detector_conformance(
        "fixture-nondeterministic", NondeterministicAdapter(), _artifact()
    )

    assert report.passed is False
    assert any("not deterministic" in error for error in report.errors)


def test_supports_cannot_mutate_artifact_metadata() -> None:
    report = run_detector_conformance(
        "fixture-mutating-support", MutatingSupportAdapter(), _artifact()
    )

    assert report.passed is False
    assert "source_unchanged" not in report.checks
    assert any("source artifact state changed" in error for error in report.errors)


def test_runtime_identity_must_stay_stable_after_detection() -> None:
    report = run_detector_conformance(
        "fixture-runtime-change", RuntimeChangesAfterDetectionAdapter(), _artifact()
    )

    assert report.passed is False
    assert any("runtime identity changed after detection" in error for error in report.errors)


def test_supports_must_be_deterministic() -> None:
    report = run_detector_conformance(
        "fixture-supports-change", NondeterministicSupportsAdapter(), _artifact()
    )

    assert report.passed is False
    assert any("supports() is not deterministic" in error for error in report.errors)


def test_capabilities_must_be_deterministic() -> None:
    report = run_detector_conformance(
        "fixture-capabilities-change", NondeterministicCapabilitiesAdapter(), _artifact()
    )

    assert report.passed is False
    assert any("capabilities are not deterministic" in error for error in report.errors)


def test_rehashed_false_pass_missing_required_check_is_rejected() -> None:
    payload = run_detector_conformance(
        "fixture-good", GoodAdapter(), _artifact()
    ).to_dict()
    payload["checks"].remove("deterministic_detection")
    _rebind(payload)

    verification = verify_conformance_document(payload)

    assert verification.valid is False
    assert any("missing required checks" in error for error in verification.errors)


def test_rehashed_detection_with_unknown_field_is_rejected() -> None:
    payload = run_detector_conformance(
        "fixture-good", GoodAdapter(), _artifact()
    ).to_dict()
    payload["detection"]["unexpected"] = "unbound-extension"
    _rebind(payload)

    verification = verify_conformance_document(payload)

    assert verification.valid is False
    assert any("detection evidence has invalid fields" in error for error in verification.errors)
