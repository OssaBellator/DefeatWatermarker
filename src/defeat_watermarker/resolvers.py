from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from .digests import sha256_bytes

_MAX_BINDING_BYTES = 4096
_MAX_ALGORITHM_LENGTH = 512
_MAX_ENDPOINTS = 16
_MAX_MATCHES = 64
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_MAX_TIMEOUT_SECONDS = 30.0
_MAX_URI_LENGTH = 4096
_MAX_MANIFEST_ID_LENGTH = 4096


class ResolverError(ValueError):
    """Raised when a soft-binding resolver input, response, or policy is invalid."""


@dataclass(frozen=True, slots=True)
class SoftBinding:
    """Opaque soft binding used for lookup without serializing its raw value."""

    algorithm: str
    value: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not self.algorithm or len(self.algorithm) > _MAX_ALGORITHM_LENGTH:
            raise ResolverError("soft-binding algorithm is missing or too long")
        if "\x00" in self.algorithm:
            raise ResolverError("soft-binding algorithm must not contain NUL")
        if not self.value or len(self.value) > _MAX_BINDING_BYTES:
            raise ResolverError(
                f"soft-binding value must contain 1..{_MAX_BINDING_BYTES} bytes"
            )

    @property
    def query_digest(self) -> str:
        return sha256_bytes(self.algorithm.encode("utf-8") + b"\x00" + self.value)

    def reference_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "query_digest": self.query_digest,
            "value_length": len(self.value),
        }


@dataclass(frozen=True, slots=True)
class ResolverPolicy:
    """Explicit network/resource boundary for resolver implementations."""

    allowed_endpoints: tuple[str, ...]
    timeout_seconds: float = 5.0
    max_response_bytes: int = 2 * 1024 * 1024
    max_matches: int = 16
    allow_artifact_upload: bool = False

    def __post_init__(self) -> None:
        if not self.allowed_endpoints:
            raise ResolverError("resolver policy requires at least one allowed endpoint")
        if len(self.allowed_endpoints) > _MAX_ENDPOINTS:
            raise ResolverError(f"resolver policy exceeds {_MAX_ENDPOINTS} endpoints")
        normalized = [normalize_endpoint(endpoint) for endpoint in self.allowed_endpoints]
        if len(set(normalized)) != len(normalized):
            raise ResolverError("resolver endpoints must be unique after normalization")
        if not 0 < self.timeout_seconds <= _MAX_TIMEOUT_SECONDS:
            raise ResolverError(
                f"timeout_seconds must be in (0, {_MAX_TIMEOUT_SECONDS}]"
            )
        if not 1 <= self.max_response_bytes <= _MAX_RESPONSE_BYTES:
            raise ResolverError(
                f"max_response_bytes must be in 1..{_MAX_RESPONSE_BYTES}"
            )
        if not 1 <= self.max_matches <= _MAX_MATCHES:
            raise ResolverError(f"max_matches must be in 1..{_MAX_MATCHES}")
        if self.allow_artifact_upload:
            raise ResolverError(
                "artifact upload is not supported by the v1 resolver contract; use by-binding lookup"
            )

    def permits(self, endpoint: str) -> bool:
        normalized = normalize_endpoint(endpoint)
        return normalized in {normalize_endpoint(item) for item in self.allowed_endpoints}


def normalize_endpoint(endpoint: str) -> str:
    if not endpoint or len(endpoint) > _MAX_URI_LENGTH:
        raise ResolverError("resolver endpoint is missing or too long")
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ResolverError("resolver endpoints must be HTTPS URLs")
    if parsed.username is not None or parsed.password is not None:
        raise ResolverError("resolver endpoints must not contain userinfo")
    if parsed.query or parsed.fragment:
        raise ResolverError("resolver endpoint must not contain query or fragment")
    path = parsed.path.rstrip("/")
    return urllib.parse.urlunsplit(("https", parsed.netloc.lower(), path, "", ""))


@dataclass(frozen=True, slots=True)
class ManifestReference:
    manifest_id: str
    endpoint: str | None = None
    similarity_score: int | None = None

    def __post_init__(self) -> None:
        if not self.manifest_id or len(self.manifest_id) > _MAX_MANIFEST_ID_LENGTH:
            raise ResolverError("manifest_id is missing or too long")
        if "\x00" in self.manifest_id:
            raise ResolverError("manifest_id must not contain NUL")
        if self.endpoint is not None:
            normalize_endpoint(self.endpoint)
        if self.similarity_score is not None and (
            type(self.similarity_score) is not int or not 0 <= self.similarity_score <= 100
        ):
            raise ResolverError("similarity_score must be an integer in 0..100")

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "endpoint": self.endpoint,
            "similarity_score": self.similarity_score,
        }


@dataclass(frozen=True, slots=True)
class ResolverResult:
    resolver_id: str
    binding_algorithm: str
    query_digest: str
    matches: tuple[ManifestReference, ...]
    warnings: tuple[str, ...] = ()
    schema_version: str = "0.2"

    def __post_init__(self) -> None:
        if not self.resolver_id or len(self.resolver_id) > 128:
            raise ResolverError("resolver_id is missing or too long")
        if len(self.matches) > _MAX_MATCHES:
            raise ResolverError(f"resolver result exceeds {_MAX_MATCHES} matches")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "resolver_id": self.resolver_id,
            "binding_algorithm": self.binding_algorithm,
            "query_digest": self.query_digest,
            "matches": [match.to_dict() for match in self.matches],
            "warnings": list(self.warnings),
        }


class SoftBindingResolver(ABC):
    """Resolve an extracted soft binding; raw artifact upload is intentionally absent."""

    resolver_id: str

    @abstractmethod
    def resolve(self, binding: SoftBinding, policy: ResolverPolicy) -> ResolverResult:
        raise NotImplementedError


class ResolverRegistry:
    def __init__(self, resolvers: Iterable[SoftBindingResolver] = ()) -> None:
        self._resolvers: dict[str, SoftBindingResolver] = {}
        for resolver in resolvers:
            self.register(resolver)

    def register(self, resolver: SoftBindingResolver) -> None:
        if resolver.resolver_id in self._resolvers:
            raise ResolverError(f"duplicate resolver_id: {resolver.resolver_id}")
        self._resolvers[resolver.resolver_id] = resolver

    def get(self, resolver_id: str) -> SoftBindingResolver:
        try:
            return self._resolvers[resolver_id]
        except KeyError as exc:
            raise ResolverError(f"unknown resolver_id: {resolver_id}") from exc

    def __iter__(self) -> Iterator[SoftBindingResolver]:
        return iter(self._resolvers.values())


class JsonPostTransport(Protocol):
    def post_json(
        self,
        url: str,
        body: bytes,
        headers: dict[str, str],
        policy: ResolverPolicy,
    ) -> dict[str, Any]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class UrllibNoRedirectTransport:
    """Direct HTTPS JSON transport with redirects and environment proxies disabled."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def post_json(
        self,
        url: str,
        body: bytes,
        headers: dict[str, str],
        policy: ResolverPolicy,
    ) -> dict[str, Any]:
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with self._opener.open(request, timeout=policy.timeout_seconds) as response:
                status = getattr(response, "status", None)
                if status != 200:
                    raise ResolverError(f"resolver returned HTTP status {status}")
                content_type = response.headers.get_content_type()
                if content_type != "application/json":
                    raise ResolverError(
                        f"resolver returned unexpected content type: {content_type}"
                    )
                declared = response.headers.get("Content-Length")
                if declared is not None:
                    try:
                        declared_size = int(declared)
                    except ValueError as exc:
                        raise ResolverError("resolver returned invalid Content-Length") from exc
                    if declared_size > policy.max_response_bytes:
                        raise ResolverError("resolver response exceeds configured byte limit")
                raw = response.read(policy.max_response_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise ResolverError(f"resolver HTTP request failed with status {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ResolverError(f"resolver network request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ResolverError("resolver network request timed out") from exc
        if len(raw) > policy.max_response_bytes:
            raise ResolverError("resolver response exceeds configured byte limit")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ResolverError("resolver returned invalid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ResolverError("resolver response must be a JSON object")
        return payload


class C2paSoftBindingHttpResolver(SoftBindingResolver):
    """C2PA Soft Binding Resolution API client using only POST /matches/byBinding."""

    resolver_id = "c2pa.soft-binding-http.by-binding.v1"

    def __init__(
        self,
        endpoint: str,
        *,
        access_token: str | None = None,
        transport: JsonPostTransport | None = None,
    ) -> None:
        self.endpoint = normalize_endpoint(endpoint)
        if access_token is not None and (not access_token or "\x00" in access_token):
            raise ResolverError("access token is invalid")
        self._access_token = access_token
        self._transport = transport or UrllibNoRedirectTransport()

    def resolve(self, binding: SoftBinding, policy: ResolverPolicy) -> ResolverResult:
        if not policy.permits(self.endpoint):
            raise ResolverError("resolver endpoint is not permitted by policy")
        request_url = (
            f"{self.endpoint}/matches/byBinding?"
            + urllib.parse.urlencode({"maxResults": policy.max_matches})
        )
        body = json.dumps(
            {
                "alg": binding.algorithm,
                "value": base64.b64encode(binding.value).decode("ascii"),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._access_token is not None:
            headers["Authorization"] = f"Bearer {self._access_token}"
        payload = self._transport.post_json(request_url, body, headers, policy)
        raw_matches = payload.get("matches", [])
        if not isinstance(raw_matches, list):
            raise ResolverError("resolver response matches must be an array")
        if len(raw_matches) > policy.max_matches:
            raise ResolverError("resolver returned more matches than requested")

        matches: list[ManifestReference] = []
        warnings: list[str] = []
        for index, raw in enumerate(raw_matches):
            if not isinstance(raw, dict):
                raise ResolverError(f"resolver match {index} must be an object")
            manifest_id = raw.get("manifestId")
            endpoint = raw.get("endpoint")
            score = raw.get("similarityScore")
            if not isinstance(manifest_id, str):
                raise ResolverError(f"resolver match {index} is missing manifestId")
            if endpoint is not None and not isinstance(endpoint, str):
                raise ResolverError(f"resolver match {index} endpoint must be a string")
            if score is not None and type(score) is not int:
                raise ResolverError(f"resolver match {index} similarityScore must be an integer")
            normalized_match_endpoint = None
            if endpoint is not None:
                normalized_match_endpoint = normalize_endpoint(endpoint)
                if not policy.permits(normalized_match_endpoint):
                    warnings.append(
                        f"match {index} endpoint omitted because it is outside the endpoint allowlist"
                    )
                    normalized_match_endpoint = None
            matches.append(
                ManifestReference(
                    manifest_id=manifest_id,
                    endpoint=normalized_match_endpoint,
                    similarity_score=score,
                )
            )
        return ResolverResult(
            resolver_id=self.resolver_id,
            binding_algorithm=binding.algorithm,
            query_digest=binding.query_digest,
            matches=tuple(matches),
            warnings=tuple(warnings),
        )
