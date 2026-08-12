import pytest

from defeat_watermarker.adapters.metadata import ContainerHintAdapter
from defeat_watermarker.models import Artifact
from defeat_watermarker.registry import AdapterRegistry


def test_container_hint_adapter_finds_c2pa_candidate_without_verifying_it() -> None:
    result = ContainerHintAdapter().detect(Artifact(data=b"header C2PA footer"))
    assert result.detected is True
    assert result.cryptographically_verified is False
    assert "C2PA marker" in result.evidence
    assert result.warnings


def test_registry_rejects_duplicate_adapter_ids() -> None:
    with pytest.raises(ValueError, match="duplicate adapter_id"):
        AdapterRegistry([ContainerHintAdapter(), ContainerHintAdapter()])
