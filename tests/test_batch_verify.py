from __future__ import annotations

import json
import shutil
from pathlib import Path

from defeat_watermarker.batch_cli import main as batch_main
from defeat_watermarker.batch_verify import verify_batch_directory
from defeat_watermarker.batch_verify_cli import main as batch_verify_main

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "retests"


def _build_scan_batch(tmp_path: Path) -> Path:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    shutil.copy2(FIXTURES / "example_text.txt", inputs / "example_text.txt")
    shutil.copy2(FIXTURES / "example_image.ppm", inputs / "example_image.ppm")
    output = tmp_path / "batch"
    assert batch_main([str(inputs), "--scan-only", "--output-dir", str(output)]) == 0
    return output


def test_batch_directory_verifies_all_referenced_records(tmp_path: Path) -> None:
    output = _build_scan_batch(tmp_path)

    result = verify_batch_directory(output)

    assert result.valid is True
    assert any(check.startswith("records:") for check in result.checks)


def test_batch_verifier_cli_accepts_valid_directory(tmp_path: Path, capsys) -> None:
    output = _build_scan_batch(tmp_path)
    capsys.readouterr()

    assert batch_verify_main([str(output)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True


def test_batch_verifier_detects_tampered_referenced_scan_record(tmp_path: Path) -> None:
    output = _build_scan_batch(tmp_path)
    index = json.loads((output / "batch.json").read_text(encoding="utf-8"))
    record_id = index["records"][0]["record_id"]
    record_path = output / "records" / f"{record_id}.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["artifact"]["byte_length"] += 1
    record_path.write_text(json.dumps(record), encoding="utf-8")

    result = verify_batch_directory(output)

    assert result.valid is False
    assert any("failed scan verification" in error for error in result.errors)


def test_batch_verifier_detects_modified_index(tmp_path: Path) -> None:
    output = _build_scan_batch(tmp_path)
    path = output / "batch.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["input_name"] = "changed"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = verify_batch_directory(output)

    assert result.valid is False
    assert any("batch_id does not match" in error for error in result.errors)
