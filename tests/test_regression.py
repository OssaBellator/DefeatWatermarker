from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.engine import RobustnessEngine
from defeat_watermarker.evidence import build_evidence_bundle
from defeat_watermarker.metrics import summarize_report
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality, MutationScenario
from defeat_watermarker.mutations.base import ArtifactMutation
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.regression import (
    RegressionStatus,
    compare_regression,
    create_regression_baseline,
)
from defeat_watermarker.suites import RobustnessSuite


class FixtureAdapter(WatermarkAdapter):
    adapter_id = "fixture.detector.v1"
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


class FixtureAdapterV2(FixtureAdapter):
    pass


class ConditionalDropMutation(ArtifactMutation):
    mutation_id = "fixture.conditional-drop.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        data = artifact.data
        if b"drop" in data:
            data = data.replace(b"fixture-mark", b"removed-mark")
        return Artifact(
            data=data,
            media_type=artifact.media_type,
            name=artifact.name,
            modality=artifact.modality,
        )


def _suite(suite_id: str = "fixture-suite") -> RobustnessSuite:
    return RobustnessSuite(
        schema_version="0.1",
        suite_id=suite_id,
        version="0.1",
        description="fixture",
        scenarios=(
            MutationScenario(
                scenario_id="conditional",
                mutation_id=ConditionalDropMutation.mutation_id,
                modality=Modality.UNKNOWN,
                transformation_family="fixture",
            ),
        ),
    )


def _evidence(data: bytes, *, adapter=None, suite=None):  # type: ignore[no-untyped-def]
    adapter = adapter or FixtureAdapter()
    suite = suite or _suite()
    artifact = Artifact(data=data, name="fixture.bin")
    report = RobustnessEngine(
        AdapterRegistry([adapter]), [ConditionalDropMutation()]
    ).evaluate(artifact, suite.scenarios)
    summary = summarize_report(report)
    return build_evidence_bundle(artifact, suite, report, summary).to_dict()


def test_same_runtime_and_suite_passes_regression() -> None:
    evidence = _evidence(b"fixture-mark keep")
    baseline = create_regression_baseline(
        evidence,
        baseline_id="fixture",
        version="0.1",
        max_drop=0.0,
    )
    report = compare_regression(baseline, evidence)
    assert report.status is RegressionStatus.PASS
    assert report.suite_match is True
    assert report.adapter_runtime_match is True


def test_fixed_suite_metric_drop_fails_regression() -> None:
    baseline_evidence = _evidence(b"fixture-mark keep")
    current_evidence = _evidence(b"fixture-mark drop")
    baseline = create_regression_baseline(
        baseline_evidence,
        baseline_id="fixture",
        version="0.1",
        max_drop=0.0,
    )
    report = compare_regression(baseline, current_evidence)
    assert report.status is RegressionStatus.FAIL
    assert report.metrics[0].baseline == 1.0
    assert report.metrics[0].current == 0.0


def test_detector_runtime_change_is_indeterminate_not_regression() -> None:
    baseline_evidence = _evidence(b"fixture-mark keep")
    current_evidence = _evidence(
        b"fixture-mark keep", adapter=FixtureAdapterV2()
    )
    baseline = create_regression_baseline(
        baseline_evidence,
        baseline_id="fixture",
        version="0.1",
        max_drop=0.0,
    )
    report = compare_regression(baseline, current_evidence)
    assert report.status is RegressionStatus.INDETERMINATE
    assert report.adapter_runtime_match is False
    assert any("runtime digest" in reason for reason in report.reasons)


def test_suite_change_is_indeterminate() -> None:
    baseline_evidence = _evidence(b"fixture-mark keep", suite=_suite("first"))
    current_evidence = _evidence(b"fixture-mark keep", suite=_suite("second"))
    baseline = create_regression_baseline(
        baseline_evidence,
        baseline_id="fixture",
        version="0.1",
        max_drop=0.0,
    )
    report = compare_regression(baseline, current_evidence)
    assert report.status is RegressionStatus.INDETERMINATE
    assert report.suite_match is False
