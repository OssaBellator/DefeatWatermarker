import pytest

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.engine import RobustnessEngine
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality, MutationScenario
from defeat_watermarker.mutations.base import ArtifactMutation, IdentityMutation
from defeat_watermarker.registry import AdapterRegistry


class FixtureAdapter(WatermarkAdapter):
    adapter_id = "test.fixture"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.UNKNOWN})

    def detect(self, artifact: Artifact) -> DetectionResult:
        found = b"fixture-mark" in artifact.data
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=found,
            confidence=1.0 if found else 0.0,
        )


class ExpandingMutation(ArtifactMutation):
    mutation_id = "test.expand.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        return Artifact(
            data=artifact.data + artifact.data,
            media_type=artifact.media_type,
            name=artifact.name,
            modality=artifact.modality,
        )


def test_identity_scenario_preserves_detection_and_report_has_no_bytes() -> None:
    artifact = Artifact(data=b"payload fixture-mark", name="fixture.bin")
    engine = RobustnessEngine(
        AdapterRegistry([FixtureAdapter()]),
        [IdentityMutation()],
    )
    scenario = MutationScenario(
        scenario_id="control",
        mutation_id="control.identity.v1",
        modality=Modality.BINARY,
        transformation_family="control",
    )

    report = engine.evaluate(artifact, [scenario])
    comparison = report.scenarios[0].comparisons[0]

    assert comparison.survived is True
    serialized = report.to_dict()
    assert "data" not in repr(serialized)
    assert b"fixture-mark" not in repr(serialized).encode()


def test_unknown_mutation_is_rejected() -> None:
    engine = RobustnessEngine(AdapterRegistry([FixtureAdapter()]), [IdentityMutation()])
    scenario = MutationScenario(
        scenario_id="bad",
        mutation_id="not-registered",
        modality=Modality.BINARY,
        transformation_family="unknown",
    )

    with pytest.raises(KeyError, match="unknown predefined mutation"):
        engine.evaluate(Artifact(data=b"fixture-mark"), [scenario])


def test_known_modality_mismatch_is_rejected_before_mutation() -> None:
    engine = RobustnessEngine(AdapterRegistry([FixtureAdapter()]), [IdentityMutation()])
    scenario = MutationScenario(
        scenario_id="wrong-modality",
        mutation_id="control.identity.v1",
        modality=Modality.IMAGE,
        transformation_family="control",
    )
    with pytest.raises(ValueError, match="expects image, artifact is audio"):
        engine.evaluate(
            Artifact(data=b"fixture-mark", modality=Modality.AUDIO),
            [scenario],
        )


def test_source_and_derivatives_are_byte_bounded() -> None:
    registry = AdapterRegistry([FixtureAdapter()])
    identity = MutationScenario(
        scenario_id="identity",
        mutation_id="control.identity.v1",
        modality=Modality.UNKNOWN,
        transformation_family="control",
    )
    with pytest.raises(ValueError, match="source artifact exceeds"):
        RobustnessEngine(registry, [IdentityMutation()], max_artifact_bytes=3).evaluate(
            Artifact(data=b"1234"), [identity]
        )

    expand = MutationScenario(
        scenario_id="expand",
        mutation_id=ExpandingMutation.mutation_id,
        modality=Modality.UNKNOWN,
        transformation_family="test",
    )
    with pytest.raises(ValueError, match="generation 1 derivative exceeds"):
        RobustnessEngine(registry, [ExpandingMutation()], max_artifact_bytes=6).evaluate(
            Artifact(data=b"1234"), [expand]
        )
