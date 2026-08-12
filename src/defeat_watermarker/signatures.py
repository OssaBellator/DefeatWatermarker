from __future__ import annotations

import base64
import binascii
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .digests import content_digest, sha256_bytes
from .evidence import verify_evidence_document
from .io_utils import read_bounded_bytes

_MAX_KEY_BYTES = 64 * 1024
_MAX_SIGNATURE_BYTES = 1024 * 1024
_DOMAIN = b"DefeatWatermarker Evidence Signature v1\x00"


class SignatureError(ValueError):
    """Raised when evidence signing or signature verification cannot be completed safely."""


def _crypto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except ImportError as exc:
        raise SignatureError(
            "Ed25519 signing requires the optional 'signing' extra"
        ) from exc
    return InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey


def _evidence_id(evidence: dict[str, Any]) -> str:
    verification = verify_evidence_document(evidence)
    if not verification.valid or verification.evidence_id is None:
        raise SignatureError(
            "evidence failed self-consistency verification: "
            + "; ".join(verification.errors)
        )
    return verification.evidence_id


def _message(evidence_id: str) -> bytes:
    try:
        digest = bytes.fromhex(evidence_id)
    except ValueError as exc:
        raise SignatureError("evidence_id is not valid hexadecimal") from exc
    if len(digest) != 32:
        raise SignatureError("evidence_id must be a SHA-256 digest")
    return _DOMAIN + digest


def _private_key_bytes(path: Path) -> bytes:
    if os.name == "posix":
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise SignatureError(
                "private key file must not be readable or writable by group/other users"
            )
    return read_bounded_bytes(path, max_bytes=_MAX_KEY_BYTES)


def _public_key_fingerprint(public_key: Any) -> str:
    _, serialization, _, _ = _crypto()
    encoded = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return sha256_bytes(encoded)


@dataclass(frozen=True, slots=True)
class EvidenceSignature:
    key_id: str
    evidence_id: str
    public_key_sha256: str
    signature: bytes
    algorithm: str = "ed25519"
    schema_version: str = "0.1"

    def __post_init__(self) -> None:
        if not self.key_id or len(self.key_id) > 255 or "\x00" in self.key_id:
            raise SignatureError("key_id is missing, too long, or contains NUL")
        for noun, digest in (
            ("evidence_id", self.evidence_id),
            ("public_key_sha256", self.public_key_sha256),
        ):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise SignatureError(f"{noun} must be a lowercase SHA-256 digest")
        if self.algorithm != "ed25519":
            raise SignatureError("unsupported signature algorithm")
        if self.schema_version != "0.1":
            raise SignatureError("unsupported signature schema_version")
        if not self.signature or len(self.signature) > 256:
            raise SignatureError("signature byte length is invalid")

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "evidence_id": self.evidence_id,
            "public_key_sha256": self.public_key_sha256,
            "signature": base64.b64encode(self.signature).decode("ascii"),
        }

    @property
    def signature_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"signature_id": self.signature_id, **self.core_dict()}


@dataclass(frozen=True, slots=True)
class SignatureVerification:
    valid: bool
    evidence_id: str
    key_id: str
    public_key_sha256: str
    signature_id: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "evidence_id": self.evidence_id,
            "key_id": self.key_id,
            "public_key_sha256": self.public_key_sha256,
            "signature_id": self.signature_id,
            "error": self.error,
        }


def sign_evidence(
    evidence: dict[str, Any],
    private_key_path: Path,
    *,
    key_id: str,
) -> EvidenceSignature:
    _, serialization, Ed25519PrivateKey, _ = _crypto()
    evidence_id = _evidence_id(evidence)
    key_data = _private_key_bytes(private_key_path)
    try:
        private_key = serialization.load_pem_private_key(key_data, password=None)
    except (TypeError, ValueError) as exc:
        raise SignatureError("could not load unencrypted PEM private key") from exc
    if not isinstance(private_key, Ed25519PrivateKey):
        raise SignatureError("private key must be Ed25519")
    public_key = private_key.public_key()
    return EvidenceSignature(
        key_id=key_id,
        evidence_id=evidence_id,
        public_key_sha256=_public_key_fingerprint(public_key),
        signature=private_key.sign(_message(evidence_id)),
    )


def signature_from_dict(payload: dict[str, Any]) -> EvidenceSignature:
    required = {
        "signature_id",
        "schema_version",
        "algorithm",
        "key_id",
        "evidence_id",
        "public_key_sha256",
        "signature",
    }
    if set(payload) != required:
        extras = sorted(set(payload) - required)
        missing = sorted(required - set(payload))
        if extras:
            raise SignatureError(f"signature has unknown fields: {', '.join(extras)}")
        raise SignatureError(f"signature is missing fields: {', '.join(missing)}")
    encoded = payload["signature"]
    if not isinstance(encoded, str):
        raise SignatureError("signature must be base64 text")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SignatureError("signature is not valid base64") from exc
    signature = EvidenceSignature(
        key_id=str(payload["key_id"]),
        evidence_id=str(payload["evidence_id"]),
        public_key_sha256=str(payload["public_key_sha256"]),
        signature=raw,
        algorithm=str(payload["algorithm"]),
        schema_version=str(payload["schema_version"]),
    )
    if payload["signature_id"] != signature.signature_id:
        raise SignatureError("signature_id does not match signature document")
    return signature


def load_signature(path: Path) -> EvidenceSignature:
    if path.stat().st_size > _MAX_SIGNATURE_BYTES:
        raise SignatureError(f"signature file exceeds {_MAX_SIGNATURE_BYTES} bytes")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SignatureError(f"could not read signature document: {exc}") from exc
    if not isinstance(payload, dict):
        raise SignatureError("signature document must be a JSON object")
    return signature_from_dict(payload)


def verify_signature(
    evidence: dict[str, Any],
    signature: EvidenceSignature,
    public_key_path: Path,
) -> SignatureVerification:
    InvalidSignature, serialization, _, Ed25519PublicKey = _crypto()
    evidence_id = _evidence_id(evidence)
    if evidence_id != signature.evidence_id:
        return SignatureVerification(
            valid=False,
            evidence_id=evidence_id,
            key_id=signature.key_id,
            public_key_sha256=signature.public_key_sha256,
            signature_id=signature.signature_id,
            error="signature evidence_id does not match evidence",
        )
    key_data = read_bounded_bytes(public_key_path, max_bytes=_MAX_KEY_BYTES)
    try:
        public_key = serialization.load_pem_public_key(key_data)
    except (TypeError, ValueError) as exc:
        raise SignatureError("could not load PEM public key") from exc
    if not isinstance(public_key, Ed25519PublicKey):
        raise SignatureError("public key must be Ed25519")
    fingerprint = _public_key_fingerprint(public_key)
    if fingerprint != signature.public_key_sha256:
        return SignatureVerification(
            valid=False,
            evidence_id=evidence_id,
            key_id=signature.key_id,
            public_key_sha256=fingerprint,
            signature_id=signature.signature_id,
            error="public key fingerprint does not match signature document",
        )
    try:
        public_key.verify(signature.signature, _message(evidence_id))
    except InvalidSignature:
        return SignatureVerification(
            valid=False,
            evidence_id=evidence_id,
            key_id=signature.key_id,
            public_key_sha256=fingerprint,
            signature_id=signature.signature_id,
            error="Ed25519 signature verification failed",
        )
    return SignatureVerification(
        valid=True,
        evidence_id=evidence_id,
        key_id=signature.key_id,
        public_key_sha256=fingerprint,
        signature_id=signature.signature_id,
    )
