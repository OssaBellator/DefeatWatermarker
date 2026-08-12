from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.engine import RobustnessEngine
from defeat_watermarker.evidence import build_evidence_bundle
from defeat_watermarker.metrics import GatePolicy, GateStatus, apply_gate, summarize_report
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality, MutationScenario
from defeat_watermarker.mutations.base import IdentityMutation
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.suites import RobustnessSuite


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


def _suite(scenario: MutationScenario) -> RobustnessSuite:
    return RobustnessSuite(
        schema_version="0.1",
        suite_id="fixture",
        version="0.1",
        description="fixture suite",
        scenarios=(scenario,),
    )


def test_evidence_bundle_is_content_addressed_and_excludes_bytes() -> None:
    artifact = Artifact(data=b"payload fixture-mark", name="fixture.bin")
    scenario = MutationScenario(
        scenario_id="identity",
        mutation_id="control.identity.v1",
        modality=Modality.UNKNOWN,
        transformation_family="control",
    )
    suite = _suite(scenario)
    report = RobustnessEngine(
        AdapterRegistry([FixtureAdapter()]),
        [IdentityMutation()],
    ).evaluate(artifact, suite.scenarios)
    summary = summarize_report(report)
    evidence = build_evidence_bundle(artifact, suite, report, summary)

    payload = evidence.to_dict()
    assert len(payload["evidence_id"]) == 64
    assert len(payload["artifact"]["sha256"]) == 64
    assert payload["summary"]["survival_rate"] == 1.0
    assert "payload fixture-mark" not in repr(payload)
    assert "data" not in payload["artifact"]


def test_gate_is_indeterminate_when_no_mark_was_detected() -> None:
    artifact = Artifact(data=b"plain payload")
    scenario = MutationScenario(
        scenario_id="identity",
        mutation_id="control.identity.v1",
        modality=Modality.UNKNOWN,
        transformation_family="control",
    )
    report = RobustnessEngine(
        AdapterRegistry([FixtureAdapter()]),
        [IdentityMutation()],
    ).evaluate(artifact, [scenario])
    result = apply_gate(summarize_report(report), GatePolicy())

    assert result.status is GateStatus.INDETERMINATE
