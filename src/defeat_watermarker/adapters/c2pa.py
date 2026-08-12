from __future__ import annotations

import importlib.util
import io
import json
from dataclasses import dataclass
from typing import Any, Protocol

from ..models import Artifact, DetectionResult, MarkFamily, Modality, VerificationState
from ..provenance import ProvenanceGraphError, build_c2pa_provenance_graph
from .base import WatermarkAdapter

_MAX_VALIDATION_CODES = 2048
_MAX_CODE_LENGTH = 256
_C2PA_CLAIM_SIGNING_EKU = "1.3.6.1.4.1.62558.2.1"
_DOCUMENT_SIGNING_EKU = "1.3.6.1.5.5.7.3.36"
_DEFAULT_TRUST_CONFIG = f"{_DOCUMENT_SIGNING_EKU}\n{_C2PA_CLAIM_SIGNING_EKU}\n"


class C2paBackendError(RuntimeError):
    """Raised when the C2PA SDK cannot complete verification."""


class C2paManifestNotFound(C2paBackendError):
    """Raised when an artifact has no discoverable C2PA manifest."""


@dataclass(frozen=True, slots=True)
class C2paTrustPolicy:
    """Local-first verification configuration for the C2PA SDK."""

    trust_anchors_pem: str | None = None
    verify_cert_anchors: bool = False
    remote_manifest_fetch: bool = False
    trust_config: str | None = None

    def __post_init__(self) -> None:
        if self.verify_cert_anchors and not self.trust_anchors_pem:
            raise ValueError("verify_cert_anchors requires trust_anchors_pem")
        if self.trust_config is not None and not self.trust_config.strip():
            raise ValueError("trust_config must be non-empty when supplied")

    def to_settings(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "verify": {
                "remote_manifest_fetch": self.remote_manifest_fetch,
            }
        }
        if self.trust_anchors_pem is not None:
            payload["trust"] = {
                "user_anchors": self.trust_anchors_pem,
                "trust_config": self.trust_config or _DEFAULT_TRUST_CONFIG,
            }
        elif self.trust_config is not None:
            payload["trust"] = {"trust_config": self.trust_config}
        return payload


class C2paBackend(Protocol):
    def read(self, artifact: Artifact, policy: C2paTrustPolicy) -> dict[str, Any]: ...


class C2paPythonBackend:
    """Thin lazy wrapper around the official c2pa-python Reader API."""

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("c2pa") is not None

    def read(self, artifact: Artifact, policy: C2paTrustPolicy) -> dict[str, Any]:
        if not self.available():
            raise C2paBackendError(
                "c2pa-python is not installed; install defeat-watermarker[c2pa]"
            )
        try:
            from c2pa import Context, Reader, Settings

            settings = Settings.from_dict(policy.to_settings())
            with Context(settings) as context:
                with io.BytesIO(artifact.data) as stream:
                    with Reader(artifact.media_type, stream, context=context) as reader:
                        payload = json.loads(reader.json())
        except Exception as exc:  # SDK exposes several native-backed exception subclasses.
            message = str(exc)
            if "ManifestNotFound" in message:
                raise C2paManifestNotFound("no C2PA manifest found") from exc
            raise C2paBackendError(f"C2PA verification failed: {message}") from exc
        if not isinstance(payload, dict):
            raise C2paBackendError("C2PA Reader returned a non-object manifest store")
        return payload


def _validation_codes(payload: dict[str, Any]) -> tuple[str, ...]:
    results = payload.get("validation_results")
    if not isinstance(results, dict):
        return ()

    found: list[str] = []

    def append_statuses(value: Any) -> None:
        if not isinstance(value, dict):
            return
        for kind in ("success", "informational", "failure"):
            statuses = value.get(kind, [])
            if not isinstance(statuses, list):
                continue
            for status in statuses:
                if not isinstance(status, dict):
                    continue
                code = status.get("code")
                if isinstance(code, str) and len(code) <= _MAX_CODE_LENGTH:
                    found.append(code)
                    if len(found) >= _MAX_VALIDATION_CODES:
                        return

    append_statuses(results.get("activeManifest"))
    deltas = results.get("ingredientDeltas", [])
    if isinstance(deltas, list):
        for delta in deltas:
            if len(found) >= _MAX_VALIDATION_CODES:
                break
            if isinstance(delta, dict):
                append_statuses(delta.get("validationDeltas"))
    return tuple(found)


def _verification_state(payload: dict[str, Any], detected: bool) -> VerificationState:
    raw = payload.get("validation_state")
    if raw == "Trusted":
        return VerificationState.TRUSTED
    if raw == "Valid":
        return VerificationState.VALID
    if raw == "Invalid":
        return VerificationState.INVALID
    if detected:
        # A Reader-produced store with manifests but no validation state was parseable, but
        # cryptographic validity/trust was not established by the reported result.
        return VerificationState.WELL_FORMED
    return VerificationState.NOT_EVALUATED


class C2paVerifierAdapter(WatermarkAdapter):
    """Read-only C2PA detector/verifier using an injectable backend."""

    adapter_id = "c2pa.reader.v1"
    family = MarkFamily.SIGNED_PROVENANCE
    modalities = frozenset(
        {
            Modality.IMAGE,
            Modality.VIDEO,
            Modality.AUDIO,
            Modality.DOCUMENT,
            Modality.BINARY,
            Modality.UNKNOWN,
        }
    )

    def __init__(
        self,
        backend: C2paBackend | None = None,
        policy: C2paTrustPolicy | None = None,
    ) -> None:
        self.backend = backend or C2paPythonBackend()
        self.policy = policy or C2paTrustPolicy()

    def detect(self, artifact: Artifact) -> DetectionResult:
        try:
            payload = self.backend.read(artifact, self.policy)
        except C2paManifestNotFound:
            return DetectionResult(
                adapter_id=self.adapter_id,
                family=self.family,
                detected=False,
                confidence=1.0,
            )
        except C2paBackendError as exc:
            return DetectionResult(
                adapter_id=self.adapter_id,
                family=self.family,
                detected=False,
                confidence=0.0,
                warnings=(str(exc),),
                verification_state=VerificationState.ERROR,
            )

        raw_manifests = payload.get("manifests", {})
        manifests = raw_manifests if isinstance(raw_manifests, dict) else {}
        active_manifest = payload.get("active_manifest")
        active = active_manifest if isinstance(active_manifest, str) else None
        detected = bool(manifests) or active is not None
        state = _verification_state(payload, detected)
        codes = _validation_codes(payload)
        warnings: list[str] = []

        graph = None
        if detected:
            try:
                graph = build_c2pa_provenance_graph(payload)
            except ProvenanceGraphError as exc:
                warnings.append(f"provenance graph omitted: {exc}")

        if state is VerificationState.INVALID:
            warnings.append("C2PA manifest was discovered but validation failed.")
        elif state is VerificationState.WELL_FORMED:
            warnings.append(
                "C2PA manifest was parsed, but cryptographic validity was not established."
            )
        elif state is VerificationState.VALID:
            warnings.append(
                "C2PA manifest is cryptographically valid, but signer trust was not established."
            )

        evidence = [f"manifest_count={len(manifests)}", f"verification_state={state.value}"]
        if active is not None:
            evidence.append(f"active_manifest={active}")

        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=detected,
            confidence=1.0 if detected else 0.0,
            evidence=tuple(evidence),
            warnings=tuple(warnings),
            provenance_identifier=active,
            cryptographically_verified=state in {VerificationState.VALID, VerificationState.TRUSTED},
            verification_state=state,
            validation_codes=codes,
            provenance_graph=graph,
        )

    def capabilities(self) -> tuple[str, ...]:
        return ("detect", "verify", "provenance_graph", "validation_codes")
