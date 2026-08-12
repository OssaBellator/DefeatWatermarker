from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from defeat_watermarker.digests import content_digest
from defeat_watermarker.signature_cli import main


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


def _signed_fixture(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, object]]:
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
    payload = json.loads(signature_path.read_text(encoding="utf-8"))
    return evidence_path, public_path, signature_path, payload


def test_signature_cli_sign_and_verify_round_trip(tmp_path: Path, capsys) -> None:
    evidence_path, public_path, signature_path, payload = _signed_fixture(tmp_path)
    assert capsys.readouterr().out == ""
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


def test_signature_cli_sign_can_emit_detached_document_to_stdout(
    tmp_path: Path, capsys
) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence()), encoding="utf-8")
    private_path, _ = _keys(tmp_path)

    assert main(
        [
            "sign",
            str(evidence_path),
            "--private-key",
            str(private_path),
            "--key-id",
            "stdout-test",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["key_id"] == "stdout-test"
    assert len(payload["signature_id"]) == 64


def test_signature_cli_wrong_public_key_returns_verification_failure(
    tmp_path: Path, capsys
) -> None:
    evidence_path, _, signature_path, _ = _signed_fixture(tmp_path / "signed")
    capsys.readouterr()
    _, wrong_public = _keys(tmp_path / "other")

    assert main(
        [
            "verify",
            str(evidence_path),
            str(signature_path),
            "--public-key",
            str(wrong_public),
        ]
    ) == 8
    verification = json.loads(capsys.readouterr().out)
    assert verification["valid"] is False
    assert "fingerprint" in verification["error"]


def test_signature_cli_refuses_to_overwrite_private_key(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence()), encoding="utf-8")
    private_path, _ = _keys(tmp_path)
    before = private_path.read_bytes()

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "sign",
                str(evidence_path),
                "--private-key",
                str(private_path),
                "--key-id",
                "local-release-test",
                "--output",
                str(private_path),
            ]
        )

    assert exc_info.value.code == 2
    assert private_path.read_bytes() == before


def test_signature_cli_refuses_to_overwrite_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    original = json.dumps(_evidence()).encode("utf-8")
    evidence_path.write_bytes(original)
    private_path, _ = _keys(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "sign",
                str(evidence_path),
                "--private-key",
                str(private_path),
                "--key-id",
                "local-release-test",
                "--output",
                str(evidence_path),
            ]
        )

    assert exc_info.value.code == 2
    assert evidence_path.read_bytes() == original


@pytest.mark.parametrize("target", ["evidence", "signature", "public_key"])
def test_signature_cli_verify_refuses_to_overwrite_inputs(
    tmp_path: Path, capsys, target: str
) -> None:
    evidence_path, public_path, signature_path, _ = _signed_fixture(tmp_path)
    capsys.readouterr()
    paths = {
        "evidence": evidence_path,
        "signature": signature_path,
        "public_key": public_path,
    }
    before = paths[target].read_bytes()

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "verify",
                str(evidence_path),
                str(signature_path),
                "--public-key",
                str(public_path),
                "--output",
                str(paths[target]),
            ]
        )

    assert exc_info.value.code == 2
    assert paths[target].read_bytes() == before
