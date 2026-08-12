import pytest

from defeat_watermarker.bindings import (
    BindingError,
    BindingExtractorRegistry,
    SoftBindingExtractor,
    SoftBindingKind,
    extract_soft_bindings,
)
from defeat_watermarker.models import Artifact, Modality
from defeat_watermarker.resolvers import SoftBinding


class FixtureExtractor(SoftBindingExtractor):
    extractor_id = "fixture.watermark.v1"
    kind = SoftBindingKind.WATERMARK
    modalities = frozenset({Modality.IMAGE})

    def extract(self, artifact: Artifact) -> tuple[SoftBinding, ...]:
        return (SoftBinding("fixture.algorithm.v1", b"secret-binding-value"),)


class TooManyExtractor(FixtureExtractor):
    extractor_id = "fixture.too-many.v1"

    def extract(self, artifact: Artifact) -> tuple[SoftBinding, ...]:
        return tuple(SoftBinding("alg", bytes([index + 1])) for index in range(33))


def test_binding_evidence_contains_digest_not_raw_binding() -> None:
    artifact = Artifact(
        data=b"private image bytes",
        media_type="image/png",
        modality=Modality.IMAGE,
    )
    evidence = extract_soft_bindings(
        artifact, BindingExtractorRegistry([FixtureExtractor()])
    ).to_dict()
    binding = evidence["bindings"][0]
    assert binding["extractor_id"] == "fixture.watermark.v1"
    assert binding["kind"] == "watermark"
    assert binding["value_length"] == len(b"secret-binding-value")
    assert len(binding["query_digest"]) == 64
    rendered = repr(evidence)
    assert "secret-binding-value" not in rendered
    assert "private image bytes" not in rendered


def test_modality_mismatch_skips_extractor() -> None:
    evidence = extract_soft_bindings(
        Artifact(data=b"audio", modality=Modality.AUDIO),
        BindingExtractorRegistry([FixtureExtractor()]),
    )
    assert evidence.bindings == ()


def test_extractor_output_count_is_bounded() -> None:
    with pytest.raises(BindingError, match="exceeded 32 bindings"):
        extract_soft_bindings(
            Artifact(data=b"image", modality=Modality.IMAGE),
            BindingExtractorRegistry([TooManyExtractor()]),
        )
