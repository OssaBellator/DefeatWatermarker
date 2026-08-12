from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from defeat_watermarker.batch import BatchError, run_batch
from defeat_watermarker.batch_cli import main as batch_main
from defeat_watermarker.scan_evidence import verify_scan_document

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "retests"


def _fixture_dir(tmp_path: Path) -> Path:
    root = tmp_path / "inputs"
    root.mkdir()
    shutil.copy2(FIXTURES / "example_text.txt", root / "example_text.txt")
    shutil.copy2(FIXTURES / "example_image.ppm", root / "example_image.ppm")
    return root


def test_batch_runs_fixed_suites_for_known_modalities(tmp_path: Path) -> None:
    root = _fixture_dir(tmp_path)

    result = run_batch(root)

    assert result.failed_records == 0
    assert [item.relative_path for item in result.records] == [
        "example_image.ppm",
        "example_text.txt",
    ]
    assert all(item.mode == "attack" for item in result.records)
    assert all(item.record_id is not None and len(item.record_id) == 64 for item in result.records)
    assert len(result.batch_id) == 64


def test_batch_scan_only_emits_verifiable_scan_records(tmp_path: Path) -> None:
    root = _fixture_dir(tmp_path)

    result = run_batch(root, scan_only=True)

    assert result.failed_records == 0
    assert all(item.mode == "scan" for item in result.records)
    for item in result.records:
        assert item.record is not None
        assert verify_scan_document(item.record).valid


def test_same_batch_input_produces_same_batch_id(tmp_path: Path) -> None:
    root = _fixture_dir(tmp_path)

    first = run_batch(root, scan_only=True)
    second = run_batch(root, scan_only=True)

    assert first.batch_id == second.batch_id


def test_batch_cli_writes_index_and_records_by_record_id(tmp_path: Path, capsys) -> None:
    root = _fixture_dir(tmp_path)
    output = tmp_path / "output"

    assert batch_main([str(root), "--scan-only", "--output-dir", str(output)]) == 0
    console = capsys.readouterr().out
    assert "Batch ID:" in console

    payload = json.loads((output / "batch.json").read_text(encoding="utf-8"))
    assert len(payload["batch_id"]) == 64
    for record in payload["records"]:
        record_id = record["record_id"]
        assert record_id is not None
        path = output / "records" / f"{record_id}.json"
        assert path.is_file()


def test_batch_rejects_symlink_input_root(tmp_path: Path) -> None:
    target = _fixture_dir(tmp_path)
    link = tmp_path / "linked-inputs"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")

    with pytest.raises(BatchError, match="must not be a symlink"):
        run_batch(link)


def test_batch_cli_rejects_output_inside_input_tree(tmp_path: Path) -> None:
    root = _fixture_dir(tmp_path)
    output = root / "generated-output"

    with pytest.raises(SystemExit) as exc:
        batch_main([str(root), "--scan-only", "--output-dir", str(output)])

    assert exc.value.code == 2
    assert not output.exists()


def test_batch_cli_rejects_nonempty_output_directory(tmp_path: Path) -> None:
    root = _fixture_dir(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    (output / "stale.json").write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        batch_main([str(root), "--scan-only", "--output-dir", str(output)])

    assert exc.value.code == 2
    assert (output / "stale.json").is_file()


def test_nonrecursive_batch_ignores_nested_files(tmp_path: Path) -> None:
    root = _fixture_dir(tmp_path)
    nested = root / "nested"
    nested.mkdir()
    shutil.copy2(FIXTURES / "example_text.txt", nested / "nested.txt")

    shallow = run_batch(root, scan_only=True)
    recursive = run_batch(root, recursive=True, scan_only=True)

    assert len(shallow.records) == 2
    assert len(recursive.records) == 3
