from defeat_watermarker.models import Modality, MutationScenario
from defeat_watermarker.preflight import PreflightStatus, preflight_suite
from defeat_watermarker.suites import RobustnessSuite


def _suite(mutation_id: str) -> RobustnessSuite:
    return RobustnessSuite(
        schema_version="0.1",
        suite_id="fixture-preflight",
        version="0.1",
        description="fixture",
        scenarios=(
            MutationScenario(
                scenario_id="fixture",
                mutation_id=mutation_id,
                modality=Modality.UNKNOWN,
                transformation_family="fixture",
            ),
        ),
    )


def test_control_mutation_is_preflight_ready() -> None:
    report = preflight_suite(_suite("control.identity.v1"))
    assert report.status is PreflightStatus.READY
    assert report.scenarios[0].known is True
    assert report.scenarios[0].runnable is True
    assert len(report.capability_digest) == 64
    assert len(report.report_id) == 64


def test_unknown_mutation_is_reported_before_artifact_processing() -> None:
    report = preflight_suite(_suite("future.unavailable.mutation.v1"))
    assert report.status is PreflightStatus.GAP
    assert report.scenarios[0].known is False
    assert report.scenarios[0].runnable is False
    assert "not registered" in report.scenarios[0].reason
