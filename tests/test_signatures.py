import base64
import json
import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.engine import RobustnessEngine
from defeat_watermarker.evidence import build_evidence_bundle
from defeat_watermarker.metrics import summarize_report
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality, MutationScenario
from defeat_watermarker.mutations.base import IdentityMutation
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.signatures import (
    SignatureError,
    load_signature,
    sign_evidence,
    signature_from_dict,
    verify_signature,
)
from defeat_watermarker.suites import RobustnessSuite


class FixtureAdapter(WatermarkAdapter):
    adapter_id = "fixture.signature.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.UNKNOWN})

    def detect(self, artifact: Artifact) -> DetectionResult:
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=True,
            confidence=1.0,
        )


def _evidence():
    suite = RobustnessSuite(
        schema_version="0.1",
        suite_id="fixture",
        version="0.1",
        description="fixture",
        scenarios=(
            MutationScenario(
                scenario_id="identity",
                mutation_id="control.identity.v1",
                modality=Modality.UNKNOWN,
                transformation_family="control",
            ),
        ),
    )
    artifact = Artifact(data=b"private fixture", name="fixture.bin")
    report = RobustnessEngine(
        AdapterRegistry([FixtureAdapter()]), [IdentityMutation()]
    ).evaluate(artifact, suite.scenarios)
    summary = summarize_report(report)
    return build_evidence_bundle(artifact, suite, report, summary).to_dict()


def _write_keys(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        private_path.chmod(0o600)
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_path, public_path


def test_detached_ed25519_signature_verifies_and_keeps_private_material_out(tmp_path) -> None:
    evidence = _evidence()
    private_path, public_path = _write_keys(tmp_path)
    signature = sign_evidence(evidence, private_path, key_id="release-2026")
    payload = signature.to_dict()
    assert payload["algorithm"] == "ed25519"
    assert payload["evidence_id"] == evidence["evidence_id"]
    assert len(payload["public_key_sha256"]) == 64
    assert len(base64.b64decode(payload["signature"], validate=True)) == 64
    assert "PRIVATE KEY" not in repr(payload)

    signature_path = tmp_path / "signature.json"
    signature_path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_signature(signature_path)
    result = verify_signature(evidence, loaded, public_path)
    assert result.valid is True


def test_wrong_public_key_fails_by_fingerprint(tmp_path) -> None:
    evidence = _evidence()
    private_path, _ = _write_keys(tmp_path)
    signature = sign_evidence(evidence, private_path, key_id="release-2026")
    _, wrong_public = _write_keys(tmp_path / "other")
    result = verify_signature(evidence, signature, wrong_public)
    assert result.valid is False
    assert "fingerprint" in result.error


def test_signature_document_rejects_non_text_fields(tmp_path) -> None:
    evidence = _evidence()
    private_path, _ = _write_keys(tmp_path)
    payload = sign_evidence(evidence, private_path, key_id="release-2026").to_dict()
    payload["key_id"] = 123

    with pytest.raises(SignatureError, match="key_id must be text"):
        signature_from_dict(payload)


def test_signature_document_requires_exact_ed25519_signature_length(tmp_path) -> None:
    evidence = _evidence()
    private_path, _ = _write_keys(tmp_path)
    payload = sign_evidence(evidence, private_path, key_id="release-2026").to_dict()
    payload["signature"] = base64.b64encode(b"x" * 63).decode("ascii")

    with pytest.raises(SignatureError, match="exactly 64 bytes"):
        signature_from_dict(payload)


def test_key_id_rejects_line_separators(tmp_path) -> None:
    evidence = _evidence()
    private_path, _ = _write_keys(tmp_path)

    with pytest.raises(SignatureError, match="control separator"):
        sign_evidence(evidence, private_path, key_id="release\nspoofed")
