import pytest

from defeat_watermarker.manifest_fetch import C2paManifestHttpClient
from defeat_watermarker.resolvers import ManifestReference, ResolverError, ResolverPolicy


class FakeTransport:
    def __init__(self, data: bytes = b"manifest-store") -> None:
        self.data = data
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get_c2pa(self, url, headers, policy):  # type: ignore[no-untyped-def]
        self.calls.append((url, headers))
        return self.data


def test_manifest_fetch_url_encodes_manifest_id_and_keeps_bytes_private() -> None:
    transport = FakeTransport(b"private-c2pa-bytes")
    client = C2paManifestHttpClient(
        "https://resolver.example/v1",
        access_token="token",
        transport=transport,
    )
    reference = ManifestReference("urn:c2pa:fixture/with space")
    fetched = client.fetch(
        reference,
        ResolverPolicy(("https://resolver.example/v1",)),
    )

    url, headers = transport.calls[0]
    assert url == (
        "https://resolver.example/v1/manifests/"
        "urn%3Ac2pa%3Afixture%2Fwith%20space"
    )
    assert headers == {
        "Accept": "application/c2pa",
        "Authorization": "Bearer token",
    }
    payload = fetched.reference_dict()
    assert payload["byte_length"] == len(b"private-c2pa-bytes")
    assert len(payload["sha256"]) == 64
    assert "private-c2pa-bytes" not in repr(fetched)
    assert "private-c2pa-bytes" not in repr(payload)
    assert "token" not in repr(payload)


def test_return_active_manifest_is_explicit_query() -> None:
    transport = FakeTransport()
    client = C2paManifestHttpClient(
        "https://resolver.example", transport=transport
    )
    client.fetch(
        ManifestReference("urn:c2pa:fixture"),
        ResolverPolicy(("https://resolver.example",)),
        return_active_manifest=True,
    )
    assert transport.calls[0][0].endswith(
        "/manifests/urn%3Ac2pa%3Afixture?returnActiveManifest=true"
    )


def test_reference_endpoint_must_also_be_allowlisted() -> None:
    client = C2paManifestHttpClient(
        "https://resolver.example", transport=FakeTransport()
    )
    with pytest.raises(ResolverError, match="not permitted"):
        client.fetch(
            ManifestReference(
                "urn:c2pa:fixture", endpoint="https://other.example"
            ),
            ResolverPolicy(("https://resolver.example",)),
        )
