from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.engine import RobustnessEngine
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality, MutationScenario
from defeat_watermarker.mutations.base import IdentityMutation
from defeat_watermarker.registry import AdapterRegistry


class FixtureAdapter(WatermarkAdapter):
    adapter_id = "fixture.runtime.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.UNKNOWN})

    def detect(self, artifact: Artifact) -> DetectionResult:
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=True,
            confidence=1.0,
        )


def test_report_binds_adapter_runtime_identity_without_source_bytes() -> None:
    report = RobustnessEngine(
        AdapterRegistry([FixtureAdapter()]), [IdentityMutation()]
    ).evaluate(
        Artifact(data=b"private fixture"),
        [
            MutationScenario(
                scenario_id="identity",
                mutation_id="control.identity.v1",
                modality=Modality.UNKNOWN,
                transformation_family="control",
            )
        ],
    )

    payload = report.to_dict()
    runtime = payload["adapter_runtime"]["fixture.runtime.v1"]
    assert any(item.startswith("python=") for item in runtime)
    assert any(item.startswith("defeat-watermarker=") for item in runtime)
    assert any("FixtureAdapter" in item for item in runtime)
    assert "private fixture" not in repr(payload)
