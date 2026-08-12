import base64
import json

import pytest

from defeat_watermarker.resolvers import (
    C2paSoftBindingHttpResolver,
    ManifestReference,
    ResolverError,
    ResolverPolicy,
    ResolverRegistry,
    ResolverResult,
    SoftBinding,
    SoftBindingResolver,
    _NoRedirect,
)


class FakeResolver(SoftBindingResolver):
    resolver_id = "fixture.resolver"

    def resolve(self, binding: SoftBinding, policy: ResolverPolicy) -> ResolverResult:
        return ResolverResult(
            resolver_id=self.resolver_id,
            binding_algorithm=binding.algorithm,
            query_digest=binding.query_digest,
            matches=(ManifestReference("urn:c2pa:fixture"),),
        )


class FakeTransport:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, bytes, dict[str, str]]] = []

    def post_json(self, url, body, headers, policy):  # type: ignore[no-untyped-def]
        self.calls.append((url, body, headers))
        return self.payload


def test_soft_binding_serialization_redacts_raw_value() -> None:
    binding = SoftBinding("example.algorithm", b"secret-binding-value")
    rendered = repr(binding.reference_dict())
    assert "secret-binding-value" not in rendered
    assert "secret-binding-value" not in repr(binding)
    assert len(binding.query_digest) == 64


def test_resolver_policy_is_bounded_and_https_only() -> None:
    with pytest.raises(ResolverError, match="HTTPS"):
        ResolverPolicy(("http://resolver.example",))
    with pytest.raises(ResolverError, match="artifact upload"):
        ResolverPolicy(("https://resolver.example",), allow_artifact_upload=True)


def test_by_binding_result_contains_digest_not_binding_value() -> None:
    binding = SoftBinding("example.algorithm", b"secret-binding-value")
    result = FakeResolver().resolve(
        binding, ResolverPolicy(("https://resolver.example",))
    )
    payload = result.to_dict()
    assert payload["query_digest"] == binding.query_digest
    assert "secret-binding-value" not in repr(payload)


def test_registry_rejects_duplicate_resolvers() -> None:
    with pytest.raises(ResolverError, match="duplicate resolver_id"):
        ResolverRegistry([FakeResolver(), FakeResolver()])


def test_c2pa_http_resolver_uses_spec_by_binding_shape_and_redacts_result() -> None:
    transport = FakeTransport(
        {
            "matches": [
                {
                    "manifestId": "urn:c2pa:fixture",
                    "endpoint": "https://resolver.example",
                    "similarityScore": 93,
                }
            ]
        }
    )
    resolver = C2paSoftBindingHttpResolver(
        "https://resolver.example", access_token="token", transport=transport
    )
    binding = SoftBinding("example.algorithm.v1", b"secret-binding")
    result = resolver.resolve(
        binding, ResolverPolicy(("https://resolver.example",), max_matches=5)
    )

    url, raw_body, headers = transport.calls[0]
    body = json.loads(raw_body)
    assert url == "https://resolver.example/matches/byBinding?maxResults=5"
    assert body == {
        "alg": "example.algorithm.v1",
        "value": base64.b64encode(b"secret-binding").decode("ascii"),
    }
    assert headers["Authorization"] == "Bearer token"
    assert result.matches[0].manifest_id == "urn:c2pa:fixture"
    assert result.matches[0].similarity_score == 93
    assert "secret-binding" not in repr(result.to_dict())
    assert "token" not in repr(result.to_dict())


def test_match_endpoint_outside_allowlist_is_not_carried_forward() -> None:
    transport = FakeTransport(
        {
            "matches": [
                {
                    "manifestId": "urn:c2pa:fixture",
                    "endpoint": "https://other.example",
                }
            ]
        }
    )
    result = C2paSoftBindingHttpResolver(
        "https://resolver.example", transport=transport
    ).resolve(
        SoftBinding("alg", b"value"),
        ResolverPolicy(("https://resolver.example",)),
    )
    assert result.matches[0].endpoint is None
    assert result.warnings


def test_redirect_handler_refuses_redirects() -> None:
    handler = _NoRedirect()
    assert handler.redirect_request(None, None, 302, "found", {}, "https://other.example") is None
