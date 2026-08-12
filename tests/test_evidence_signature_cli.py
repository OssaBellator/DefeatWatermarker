from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from defeat_watermarker.digests import content_digest
from defeat_watermarker.evidence_signature_cli import main


def _evidence() -> dict[str, object]:
    report = {"artifact_name": "fixture.bin", "baseline": [], "scenarios": []}
    core = {
        "schema_version": "0.2",
        "artifact": {
            "sha256": "a" * 64,
            "byte_length": 7,
            "media_type": "application/octet-stream",
            "name": "fixture.bin",
        },
        "suite": {
            "suite_id": "fixture-suite",
            "version": "0.1",
            "digest": "b" * 64,
        },
        "report_digest": content_digest(report),
        "report": report,
        "summary": {"survival_rate": None},
        "gate_policy": None,
        "gate": None,
    }
    return {"evidence_id": content_digest(core), **core}


def _keys(tmp_path: Path) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    private_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    if os.name == "posix":
        private_path.chmod(0o600)
    public_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_path, public_path


def test_signature_cli_sign_and_verify_round_trip(tmp_path: Path, capsys) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence()), encoding="utf-8")
    private_path, public_path = _keys(tmp_path)
    signature_path = tmp_path / "signature.json"

    assert main(
        [
            "sign",
            str(evidence_path),
            "--private-key",
            str(private_path),
            "--key-id",
            "local-release-test",
            "--output",
            str(signature_path),
        ]
    ) == 0
    sign_output = capsys.readouterr().out
    assert "Signature ID:" in sign_output

    payload = json.loads(signature_path.read_text(encoding="utf-8"))
    assert payload["algorithm"] == "ed25519"
    assert payload["key_id"] == "local-release-test"
    assert "PRIVATE KEY" not in repr(payload)

    assert main(
        [
            "verify",
            str(evidence_path),
            str(signature_path),
            "--public-key",
            str(public_path),
        ]
    ) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["valid"] is True
    assert verification["signature_id"] == payload["signature_id"]


def test_signature_cli_wrong_public_key_returns_verification_failure(
    tmp_path: Path, capsys
) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence()), encoding="utf-8")
    private_path, _ = _keys(tmp_path / "signer")
    _, wrong_public = _keys(tmp_path / "other")
    signature_path = tmp_path / "signature.json"

    assert main(
        [
            "sign",
            str(evidence_path),
            "--private-key",
            str(private_path),
            "--key-id",
            "local-release-test",
            "--output",
            str(signature_path),
        ]
    ) == 0
    capsys.readouterr()

    assert main(
        [
            "verify",
            str(evidence_path),
            str(signature_path),
            "--public-key",
            str(wrong_public),
        ]
    ) == 4
    verification = json.loads(capsys.readouterr().out)
    assert verification["valid"] is False
    assert "fingerprint" in verification["error"]
