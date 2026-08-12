from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.engine import RobustnessEngine
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality, MutationScenario
from defeat_watermarker.mutations.base import IdentityMutation
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

    try:
        engine.evaluate(Artifact(data=b"fixture-mark"), [scenario])
    except KeyError as exc:
        assert "unknown predefined mutation" in str(exc)
    else:
        raise AssertionError("expected KeyError")
