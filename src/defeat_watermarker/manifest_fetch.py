from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from .digests import sha256_bytes
from .resolvers import ManifestReference, ResolverError, ResolverPolicy, normalize_endpoint


@dataclass(frozen=True, slots=True)
class FetchedManifestStore:
    """Private fetched C2PA bytes plus a serializable content-addressed reference."""

    manifest_id: str
    endpoint: str
    data: bytes = field(repr=False)
    media_type: str = "application/c2pa"

    @property
    def sha256(self) -> str:
        return sha256_bytes(self.data)

    def reference_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "endpoint": self.endpoint,
            "media_type": self.media_type,
            "sha256": self.sha256,
            "byte_length": len(self.data),
        }


class ManifestGetTransport(Protocol):
    def get_c2pa(
        self,
        url: str,
        headers: dict[str, str],
        policy: ResolverPolicy,
    ) -> bytes: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class UrllibNoRedirectManifestTransport:
    """Bounded C2PA binary transport with proxies and redirects disabled."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def get_c2pa(
        self,
        url: str,
        headers: dict[str, str],
        policy: ResolverPolicy,
    ) -> bytes:
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self._opener.open(request, timeout=policy.timeout_seconds) as response:
                status = getattr(response, "status", None)
                if status != 200:
                    raise ResolverError(f"manifest repository returned HTTP status {status}")
                content_type = response.headers.get_content_type()
                if content_type != "application/c2pa":
                    raise ResolverError(
                        "manifest repository returned unexpected content type: "
                        f"{content_type}"
                    )
                declared = response.headers.get("Content-Length")
                if declared is not None:
                    try:
                        declared_size = int(declared)
                    except ValueError as exc:
                        raise ResolverError(
                            "manifest repository returned invalid Content-Length"
                        ) from exc
                    if declared_size > policy.max_response_bytes:
                        raise ResolverError(
                            "manifest repository response exceeds configured byte limit"
                        )
                data = response.read(policy.max_response_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise ResolverError(
                f"manifest repository HTTP request failed with status {exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ResolverError(
                f"manifest repository network request failed: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise ResolverError("manifest repository network request timed out") from exc
        if len(data) > policy.max_response_bytes:
            raise ResolverError("manifest repository response exceeds configured byte limit")
        return data


class C2paManifestHttpClient:
    """Fetch C2PA manifest-store bytes for an already-resolved manifest reference."""

    def __init__(
        self,
        default_endpoint: str,
        *,
        access_token: str | None = None,
        transport: ManifestGetTransport | None = None,
    ) -> None:
        self.default_endpoint = normalize_endpoint(default_endpoint)
        if access_token is not None and (not access_token or "\x00" in access_token):
            raise ResolverError("access token is invalid")
        self._access_token = access_token
        self._transport = transport or UrllibNoRedirectManifestTransport()

    def fetch(
        self,
        reference: ManifestReference,
        policy: ResolverPolicy,
        *,
        return_active_manifest: bool = False,
    ) -> FetchedManifestStore:
        endpoint = normalize_endpoint(reference.endpoint or self.default_endpoint)
        if not policy.permits(endpoint):
            raise ResolverError("manifest endpoint is not permitted by policy")
        manifest_segment = urllib.parse.quote(reference.manifest_id, safe="")
        url = f"{endpoint}/manifests/{manifest_segment}"
        if return_active_manifest:
            url += "?returnActiveManifest=true"
        headers = {"Accept": "application/c2pa"}
        if self._access_token is not None:
            headers["Authorization"] = f"Bearer {self._access_token}"
        data = self._transport.get_c2pa(url, headers, policy)
        return FetchedManifestStore(
            manifest_id=reference.manifest_id,
            endpoint=endpoint,
            data=data,
        )
