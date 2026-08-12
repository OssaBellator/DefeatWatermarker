import pytest

from defeat_watermarker.bindings import (
    BindingExtractorRegistry,
    SoftBindingExtractor,
    SoftBindingKind,
    extract_soft_bindings,
)
from defeat_watermarker.manifest_fetch import FetchedManifestStore
from defeat_watermarker.models import Artifact, Modality
from defeat_watermarker.recovery import RecoveryError, build_recovery_chain
from defeat_watermarker.resolvers import ManifestReference, ResolverResult, SoftBinding


class FixtureExtractor(SoftBindingExtractor):
    extractor_id = "fixture.fingerprint.v1"
    kind = SoftBindingKind.FINGERPRINT
    modalities = frozenset({Modality.IMAGE})

    def extract(self, artifact: Artifact) -> tuple[SoftBinding, ...]:
        return (SoftBinding("fixture.alg.v1", b"secret-binding"),)


def _parts():
    extraction = extract_soft_bindings(
        Artifact(
            data=b"private-image-bytes",
            media_type="image/png",
            modality=Modality.IMAGE,
        ),
        BindingExtractorRegistry([FixtureExtractor()]),
    )
    extracted = extraction.bindings[0]
    resolution = ResolverResult(
        resolver_id="fixture.resolver",
        binding_algorithm=extracted.binding.algorithm,
        query_digest=extracted.binding.query_digest,
        matches=(
            ManifestReference(
                "urn:c2pa:fixture",
                endpoint="https://resolver.example",
                similarity_score=91,
            ),
        ),
    )
    return extraction, extracted, resolution


def test_recovery_chain_binds_extraction_resolution_and_fetched_hash_only() -> None:
    extraction, extracted, resolution = _parts()
    fetched = FetchedManifestStore(
        manifest_id="urn:c2pa:fixture",
        endpoint="https://resolver.example",
        data=b"private-manifest-store",
    )
    chain = build_recovery_chain(
        extraction,
        extracted,
        resolution,
        fetched_by_manifest_id={fetched.manifest_id: fetched},
    )
    payload = chain.to_dict()
    assert payload["verification_status"] == "candidate_only"
    assert payload["candidates"][0]["similarity_score"] == 91
    assert payload["candidates"][0]["fetched_manifest"]["sha256"] == fetched.sha256
    assert len(payload["recovery_id"]) == 64
    rendered = repr(payload)
    assert "secret-binding" not in rendered
    assert "private-image-bytes" not in rendered
    assert "private-manifest-store" not in rendered


def test_recovery_chain_rejects_resolution_for_different_binding() -> None:
    extraction, extracted, resolution = _parts()
    wrong = ResolverResult(
        resolver_id=resolution.resolver_id,
        binding_algorithm=resolution.binding_algorithm,
        query_digest="0" * 64,
        matches=resolution.matches,
    )
    with pytest.raises(RecoveryError, match="query digest"):
        build_recovery_chain(extraction, extracted, wrong)


def test_recovery_chain_rejects_unrelated_fetched_manifest() -> None:
    extraction, extracted, resolution = _parts()
    fetched = FetchedManifestStore(
        manifest_id="urn:c2pa:other",
        endpoint="https://resolver.example",
        data=b"private",
    )
    with pytest.raises(RecoveryError, match="do not correspond"):
        build_recovery_chain(
            extraction,
            extracted,
            resolution,
            fetched_by_manifest_id={fetched.manifest_id: fetched},
        )
