from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from .digests import sha256_bytes

_MAX_BINDING_BYTES = 4096
_MAX_ALGORITHM_LENGTH = 512
_MAX_ENDPOINTS = 16
_MAX_MATCHES = 64
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_MAX_TIMEOUT_SECONDS = 30.0
_MAX_URI_LENGTH = 4096


class ResolverError(ValueError):
    """Raised when a soft-binding resolver input or policy is invalid."""


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
    """Explicit network/resource boundary for future resolver implementations."""

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
        if len(set(self.allowed_endpoints)) != len(self.allowed_endpoints):
            raise ResolverError("resolver endpoints must be unique")
        for endpoint in self.allowed_endpoints:
            if not endpoint.startswith("https://") or len(endpoint) > _MAX_URI_LENGTH:
                raise ResolverError("resolver endpoints must be bounded HTTPS URLs")
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


@dataclass(frozen=True, slots=True)
class ManifestReference:
    uri: str
    sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.uri or len(self.uri) > _MAX_URI_LENGTH:
            raise ResolverError("manifest URI is missing or too long")
        if self.sha256 is not None and (
            len(self.sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.sha256)
        ):
            raise ResolverError("manifest sha256 must be a lowercase SHA-256 digest")

    def to_dict(self) -> dict[str, Any]:
        return {"uri": self.uri, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class ResolverResult:
    resolver_id: str
    binding_algorithm: str
    query_digest: str
    matches: tuple[ManifestReference, ...]
    warnings: tuple[str, ...] = ()
    schema_version: str = "0.1"

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
    """Resolve an already-extracted soft binding; raw artifact upload is intentionally absent."""

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
