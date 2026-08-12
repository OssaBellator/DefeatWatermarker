from email.message import Message

import pytest

from defeat_watermarker.manifest_fetch import (
    C2paManifestHttpClient,
    UrllibNoRedirectManifestTransport,
)
from defeat_watermarker.resolvers import ManifestReference, ResolverError, ResolverPolicy


class FakeTransport:
    def __init__(self, data: bytes = b"manifest-store") -> None:
        self.data = data
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get_c2pa(self, url, headers, policy):  # type: ignore[no-untyped-def]
        self.calls.append((url, headers))
        return self.data


class FakeResponse:
    def __init__(
        self,
        data: bytes,
        *,
        status: int = 200,
        content_type: str = "application/c2pa",
        content_length: str | None = None,
    ) -> None:
        self.status = status
        self._data = data
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if content_length is not None:
            self.headers["Content-Length"] = content_length

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def read(self, limit: int) -> bytes:
        return self._data[:limit]


class FakeOpener:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[object, float]] = []

    def open(self, request, timeout):  # type: ignore[no-untyped-def]
        self.calls.append((request, timeout))
        return self.response


def _policy(*, max_response_bytes: int = 1024) -> ResolverPolicy:
    return ResolverPolicy(
        ("https://resolver.example",),
        timeout_seconds=1.5,
        max_response_bytes=max_response_bytes,
    )


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


def test_access_token_rejects_nul() -> None:
    with pytest.raises(ResolverError, match="access token is invalid"):
        C2paManifestHttpClient(
            "https://resolver.example",
            access_token="bad\x00token",
            transport=FakeTransport(),
        )


def test_concrete_transport_rejects_wrong_content_type_without_network() -> None:
    transport = UrllibNoRedirectManifestTransport()
    transport._opener = FakeOpener(  # type: ignore[attr-defined]
        FakeResponse(b"not-c2pa", content_type="application/octet-stream")
    )

    with pytest.raises(ResolverError, match="unexpected content type"):
        transport.get_c2pa(
            "https://resolver.example/manifests/test",
            {"Accept": "application/c2pa"},
            _policy(),
        )


def test_concrete_transport_rejects_declared_oversize_response() -> None:
    transport = UrllibNoRedirectManifestTransport()
    transport._opener = FakeOpener(  # type: ignore[attr-defined]
        FakeResponse(b"small", content_length="2048")
    )

    with pytest.raises(ResolverError, match="exceeds configured byte limit"):
        transport.get_c2pa(
            "https://resolver.example/manifests/test",
            {"Accept": "application/c2pa"},
            _policy(max_response_bytes=1024),
        )


def test_concrete_transport_rejects_streamed_oversize_response() -> None:
    transport = UrllibNoRedirectManifestTransport()
    transport._opener = FakeOpener(  # type: ignore[attr-defined]
        FakeResponse(b"x" * 1025)
    )

    with pytest.raises(ResolverError, match="exceeds configured byte limit"):
        transport.get_c2pa(
            "https://resolver.example/manifests/test",
            {"Accept": "application/c2pa"},
            _policy(max_response_bytes=1024),
        )


def test_concrete_transport_uses_policy_timeout() -> None:
    opener = FakeOpener(FakeResponse(b"manifest"))
    transport = UrllibNoRedirectManifestTransport()
    transport._opener = opener  # type: ignore[attr-defined]

    assert transport.get_c2pa(
        "https://resolver.example/manifests/test",
        {"Accept": "application/c2pa"},
        _policy(),
    ) == b"manifest"
    assert opener.calls[0][1] == 1.5
