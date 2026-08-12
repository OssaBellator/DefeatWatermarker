from copy import deepcopy

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.engine import RobustnessEngine
from defeat_watermarker.evidence import build_evidence_bundle, verify_evidence_document
from defeat_watermarker.metrics import GatePolicy, apply_gate, summarize_report
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality, MutationScenario
from defeat_watermarker.mutations.base import IdentityMutation
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.suites import RobustnessSuite


class FixtureAdapter(WatermarkAdapter):
    adapter_id = "fixture"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.UNKNOWN})

    def detect(self, artifact: Artifact) -> DetectionResult:
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=True,
            confidence=1.0,
        )


def _bundle():
    artifact = Artifact(data=b"fixture", name="fixture.bin")
    scenario = MutationScenario(
        scenario_id="identity",
        mutation_id="control.identity.v1",
        modality=Modality.UNKNOWN,
        transformation_family="control",
    )
    suite = RobustnessSuite(
        schema_version="0.1",
        suite_id="fixture",
        version="0.1",
        description="fixture",
        scenarios=(scenario,),
    )
    report = RobustnessEngine(
        AdapterRegistry([FixtureAdapter()]), [IdentityMutation()]
    ).evaluate(artifact, suite.scenarios)
    summary = summarize_report(report)
    policy = GatePolicy(min_survival_rate=1.0)
    gate = apply_gate(summary, policy)
    evidence = build_evidence_bundle(
        artifact, suite, report, summary, gate_policy=policy, gate=gate
    )
    return evidence, suite


def test_evidence_verifier_checks_internal_digests_and_suite() -> None:
    evidence, suite = _bundle()
    result = verify_evidence_document(evidence.to_dict(), suite=suite)
    assert result.valid is True
    assert {"evidence_id", "report_digest", "suite_digest"}.issubset(result.checks)


def test_gate_tampering_invalidates_evidence_id() -> None:
    evidence, _ = _bundle()
    payload = deepcopy(evidence.to_dict())
    payload["gate"]["reason"] = "tampered"
    result = verify_evidence_document(payload)
    assert result.valid is False
    assert "evidence_id does not match the evidence core" in result.errors


def test_report_tampering_is_detected_independently() -> None:
    evidence, _ = _bundle()
    payload = deepcopy(evidence.to_dict())
    payload["report"]["artifact_name"] = "changed.bin"
    result = verify_evidence_document(payload)
    assert result.valid is False
    assert "report_digest does not match report" in result.errors
