from typing import Any

from defeat_watermarker.adapters.c2pa import (
    C2paBackendError,
    C2paManifestNotFound,
    C2paTrustPolicy,
    C2paVerifierAdapter,
)
from defeat_watermarker.models import Artifact, VerificationState


class FakeBackend:
    def __init__(self, payload: dict[str, Any] | Exception) -> None:
        self.payload = payload
        self.policies: list[C2paTrustPolicy] = []

    def read(self, artifact: Artifact, policy: C2paTrustPolicy) -> dict[str, Any]:
        self.policies.append(policy)
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def _store(state: str = "Valid") -> dict[str, Any]:
    label = "contentauth:urn:uuid:fixture"
    return {
        "active_manifest": label,
        "manifests": {
            label: {
                "title": "fixture.jpg",
                "format": "image/jpeg",
                "instance_id": "xmp:iid:fixture",
                "claim_generator": "fixture/1.0",
                "signature_info": {
                    "issuer": "Fixture Issuer",
                    "common_name": "Fixture Signer",
                },
                "ingredients": [
                    {
                        "title": "parent.jpg",
                        "format": "image/jpeg",
                        "instance_id": "xmp:iid:parent",
                        "relationship": "parentOf",
                    }
                ],
            }
        },
        "validation_results": {
            "activeManifest": {
                "success": [
                    {"code": "claimSignature.insideValidity"},
                    {"code": "claimSignature.validated"},
                    *([{"code": "signingCredential.trusted"}] if state == "Trusted" else []),
                ],
                "informational": [],
                "failure": [],
            }
        },
        "validation_state": state,
    }


def _with_failure(payload: dict[str, Any], code: str) -> dict[str, Any]:
    payload["validation_results"]["activeManifest"]["failure"] = [{"code": code}]
    return payload


def test_valid_manifest_is_detected_and_graph_is_bounded_summary() -> None:
    result = C2paVerifierAdapter(backend=FakeBackend(_store())).detect(
        Artifact(data=b"not-used", media_type="image/jpeg")
    )

    assert result.detected is True
    assert result.verification_state is VerificationState.VALID
    assert result.cryptographically_verified is True
    assert result.provenance_identifier == "contentauth:urn:uuid:fixture"
    assert "claimSignature.validated" in result.validation_codes
    assert result.provenance_graph is not None
    graph = result.provenance_graph.to_dict()
    assert len(graph["nodes"]) == 3
    assert {edge["relation"] for edge in graph["edges"]} == {"active_manifest", "ingredient"}
    assert "assertions" not in repr(graph)
    assert result.warnings


def test_trusted_manifest_has_distinct_state() -> None:
    result = C2paVerifierAdapter(backend=FakeBackend(_store("Trusted"))).detect(
        Artifact(data=b"fixture", media_type="image/jpeg")
    )
    assert result.verification_state is VerificationState.TRUSTED
    assert result.cryptographically_verified is True
    assert not result.warnings


def test_invalid_manifest_remains_detected_but_not_verified() -> None:
    payload = _with_failure(_store("Invalid"), "assertion.dataHash.mismatch")
    result = C2paVerifierAdapter(backend=FakeBackend(payload)).detect(
        Artifact(data=b"fixture", media_type="image/jpeg")
    )
    assert result.detected is True
    assert result.verification_state is VerificationState.INVALID
    assert result.cryptographically_verified is False
    assert "assertion.dataHash.mismatch" in result.validation_codes


def test_expired_signing_credential_vector_is_invalid() -> None:
    payload = _with_failure(_store("Invalid"), "claimSignature.outsideValidity")
    result = C2paVerifierAdapter(backend=FakeBackend(payload)).detect(
        Artifact(data=b"fixture", media_type="image/jpeg")
    )

    assert result.detected is True
    assert result.verification_state is VerificationState.INVALID
    assert result.cryptographically_verified is False
    assert "claimSignature.outsideValidity" in result.validation_codes


def test_inaccessible_external_manifest_vector_is_invalid() -> None:
    payload = _with_failure(_store("Invalid"), "manifest.inaccessible")
    result = C2paVerifierAdapter(backend=FakeBackend(payload)).detect(
        Artifact(data=b"fixture", media_type="image/jpeg")
    )

    assert result.detected is True
    assert result.verification_state is VerificationState.INVALID
    assert result.cryptographically_verified is False
    assert "manifest.inaccessible" in result.validation_codes


def test_explicit_failure_overrides_contradictory_trusted_state() -> None:
    payload = _with_failure(_store("Trusted"), "claimSignature.outsideValidity")
    result = C2paVerifierAdapter(backend=FakeBackend(payload)).detect(
        Artifact(data=b"fixture", media_type="image/jpeg")
    )

    assert result.verification_state is VerificationState.INVALID
    assert result.cryptographically_verified is False
    assert "claimSignature.outsideValidity" in result.validation_codes


def test_manifest_not_found_is_clean_negative() -> None:
    result = C2paVerifierAdapter(backend=FakeBackend(C2paManifestNotFound("none"))).detect(
        Artifact(data=b"fixture", media_type="image/jpeg")
    )
    assert result.detected is False
    assert result.verification_state is VerificationState.NOT_EVALUATED
    assert not result.warnings


def test_backend_failure_is_explicit_error_state() -> None:
    result = C2paVerifierAdapter(backend=FakeBackend(C2paBackendError("native failure"))).detect(
        Artifact(data=b"fixture", media_type="image/jpeg")
    )
    assert result.detected is False
    assert result.verification_state is VerificationState.ERROR
    assert result.warnings == ("native failure",)


def test_trust_policy_is_local_only_by_default() -> None:
    policy = C2paTrustPolicy()
    assert policy.to_settings()["verify"]["remote_manifest_fetch"] is False
