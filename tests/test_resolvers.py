import pytest

from defeat_watermarker.resolvers import (
    ManifestReference,
    ResolverError,
    ResolverPolicy,
    ResolverRegistry,
    ResolverResult,
    SoftBinding,
    SoftBindingResolver,
)


class FakeResolver(SoftBindingResolver):
    resolver_id = "fixture.resolver"

    def resolve(self, binding: SoftBinding, policy: ResolverPolicy) -> ResolverResult:
        return ResolverResult(
            resolver_id=self.resolver_id,
            binding_algorithm=binding.algorithm,
            query_digest=binding.query_digest,
            matches=(ManifestReference("https://resolver.example/manifests/fixture"),),
        )


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
