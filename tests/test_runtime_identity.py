from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.engine import RobustnessEngine
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality, MutationScenario
from defeat_watermarker.mutations.base import IdentityMutation
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.runtime import adapter_runtime_identity


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


class ExternalAdapter:
    adapter_id = "provider.detector.v1"


ExternalAdapter.__module__ = "provider_detector.adapter"


class BuiltinAdapter:
    adapter_id = "builtin.test.v1"


BuiltinAdapter.__module__ = "defeat_watermarker.adapters.test"


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


def test_external_adapter_runtime_binds_distribution_version(monkeypatch) -> None:
    monkeypatch.setattr(
        "defeat_watermarker.runtime.metadata.packages_distributions",
        lambda: {"provider_detector": ["provider-detector"]},
    )
    monkeypatch.setattr(
        "defeat_watermarker.runtime.metadata.version",
        lambda name: "2.4.1" if name == "provider-detector" else "0.1.0",
    )

    identity = adapter_runtime_identity(ExternalAdapter())

    assert "plugin-distribution=provider-detector==2.4.1" in identity


def test_builtin_adapter_does_not_duplicate_package_distribution(monkeypatch) -> None:
    monkeypatch.setattr(
        "defeat_watermarker.runtime.metadata.packages_distributions",
        lambda: {"defeat_watermarker": ["defeat-watermarker"]},
    )
    monkeypatch.setattr(
        "defeat_watermarker.runtime.metadata.version",
        lambda name: "0.1.0",
    )

    identity = adapter_runtime_identity(BuiltinAdapter())

    assert "defeat-watermarker=0.1.0" in identity
    assert not any(item.startswith("plugin-distribution=") for item in identity)


def test_external_distribution_lookup_failure_is_nonfatal(monkeypatch) -> None:
    def fail_lookup():
        raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(
        "defeat_watermarker.runtime.metadata.packages_distributions", fail_lookup
    )

    identity = adapter_runtime_identity(ExternalAdapter())

    assert identity[0] == "adapter_id=provider.detector.v1"
    assert not any(item.startswith("plugin-distribution=") for item in identity)
