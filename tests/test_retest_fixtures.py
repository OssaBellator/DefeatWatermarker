from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.evidence import verify_evidence_document
from defeat_watermarker.ui_cli import main as ui_main

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "retests"


def _run_fixture(name: str, media_type: str, output: Path) -> dict[str, object]:
    rc = ui_main(
        [
            str(FIXTURES / name),
            "--media-type",
            media_type,
            "--json-output",
            str(output),
        ]
    )
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert verify_evidence_document(payload).valid
    return payload


def test_generated_text_fixture_runs_builtin_editorial_suite(tmp_path: Path) -> None:
    payload = _run_fixture("example_text.txt", "text/plain", tmp_path / "text.json")

    assert payload["suite"]["suite_id"] == "text-editorial-normalization"
    scenarios = payload["report"]["scenarios"]
    assert [item["scenario"]["scenario_id"] for item in scenarios] == [
        "unicode-nfc",
        "line-endings-lf",
        "strip-trailing-horizontal-whitespace",
    ]
    source_hash = payload["artifact"]["sha256"]
    assert any(item["derivative"]["sha256"] != source_hash for item in scenarios)


def test_generated_image_fixture_exercises_hint_loss_under_rendition(
    tmp_path: Path,
) -> None:
    payload = _run_fixture(
        "example_image.ppm",
        "image/x-portable-pixmap",
        tmp_path / "image.json",
    )

    assert payload["suite"]["suite_id"] == "image-platform-rendition"
    baseline = {
        item["adapter_id"]: item for item in payload["report"]["baseline"]
    }
    hint = baseline["builtin.container-hints"]
    assert hint["detected"] is True
    assert any("c2pa" in evidence.lower() for evidence in hint["evidence"])

    comparisons = [
        comparison
        for scenario in payload["report"]["scenarios"]
        for comparison in scenario["comparisons"]
        if comparison["adapter_id"] == "builtin.container-hints"
    ]
    assert comparisons
    assert all(comparison["after"]["detected"] is False for comparison in comparisons)
    assert payload["summary"]["survival_rate"] == 0.0
