from __future__ import annotations

import json
from pathlib import Path

import pytest

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.engine import RobustnessEngine
from defeat_watermarker.evidence import build_evidence_bundle
from defeat_watermarker.metrics import summarize_report
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality, MutationScenario
from defeat_watermarker.mutations.base import ArtifactMutation
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.regression import load_regression_baseline
from defeat_watermarker.regression_cli import main
from defeat_watermarker.suites import RobustnessSuite


class FixtureAdapter(WatermarkAdapter):
    adapter_id = "fixture.regression-cli.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.UNKNOWN})

    def detect(self, artifact: Artifact) -> DetectionResult:
        found = b"fixture-mark" in artifact.data
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=found,
            confidence=1.0 if found else 0.0,
        )


class FixtureAdapterV2(FixtureAdapter):
    pass


class ConditionalDropMutation(ArtifactMutation):
    mutation_id = "fixture.regression-cli-drop.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        data = artifact.data
        if b"drop" in data:
            data = data.replace(b"fixture-mark", b"removed-mark")
        return Artifact(
            data=data,
            media_type=artifact.media_type,
            name=artifact.name,
            modality=artifact.modality,
        )


def _suite() -> RobustnessSuite:
    return RobustnessSuite(
        schema_version="0.1",
        suite_id="fixture-regression-cli",
        version="0.1",
        description="fixture",
        scenarios=(
            MutationScenario(
                scenario_id="conditional",
                mutation_id=ConditionalDropMutation.mutation_id,
                modality=Modality.UNKNOWN,
                transformation_family="fixture",
            ),
        ),
    )


def _evidence(data: bytes, *, adapter: WatermarkAdapter | None = None) -> dict[str, object]:
    artifact = Artifact(data=data, name="fixture.bin")
    report = RobustnessEngine(
        AdapterRegistry([adapter or FixtureAdapter()]),
        [ConditionalDropMutation()],
    ).evaluate(artifact, _suite().scenarios)
    return build_evidence_bundle(
        artifact,
        _suite(),
        report,
        summarize_report(report),
    ).to_dict()


def _write_evidence(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _create_baseline(tmp_path: Path, evidence: dict[str, object]) -> tuple[Path, Path]:
    evidence_path = tmp_path / "baseline-evidence.json"
    baseline_path = tmp_path / "baseline.json"
    _write_evidence(evidence_path, evidence)
    assert main(
        [
            "baseline",
            str(evidence_path),
            "--id",
            "fixture-release",
            "--version",
            "0.1",
            "--max-drop",
            "0",
            "--output",
            str(baseline_path),
        ]
    ) == 0
    return evidence_path, baseline_path


def test_regression_cli_baseline_round_trips_into_loader(tmp_path: Path) -> None:
    _, baseline_path = _create_baseline(tmp_path, _evidence(b"fixture-mark keep"))

    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert "baseline_digest" not in payload
    baseline = load_regression_baseline(baseline_path)
    assert baseline.baseline_id == "fixture-release"
    assert len(baseline.digest) == 64


def test_regression_cli_check_returns_pass(tmp_path: Path, capsys) -> None:
    evidence = _evidence(b"fixture-mark keep")
    _, baseline_path = _create_baseline(tmp_path, evidence)
    current = tmp_path / "current.json"
    _write_evidence(current, evidence)

    assert main(["check", str(baseline_path), str(current)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "pass"
    assert len(payload["report_id"]) == 64


def test_regression_cli_check_returns_fail_for_metric_drop(tmp_path: Path, capsys) -> None:
    _, baseline_path = _create_baseline(tmp_path, _evidence(b"fixture-mark keep"))
    current = tmp_path / "current.json"
    _write_evidence(current, _evidence(b"fixture-mark drop"))

    assert main(["check", str(baseline_path), str(current)]) == 6
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "fail"


def test_regression_cli_check_returns_indeterminate_for_runtime_change(
    tmp_path: Path, capsys
) -> None:
    _, baseline_path = _create_baseline(tmp_path, _evidence(b"fixture-mark keep"))
    current = tmp_path / "current.json"
    _write_evidence(
        current,
        _evidence(b"fixture-mark keep", adapter=FixtureAdapterV2()),
    )

    assert main(["check", str(baseline_path), str(current)]) == 7
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "indeterminate"
    assert payload["adapter_runtime_match"] is False


def test_regression_cli_baseline_refuses_to_overwrite_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    original = json.dumps(_evidence(b"fixture-mark keep")).encode("utf-8")
    evidence_path.write_bytes(original)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "baseline",
                str(evidence_path),
                "--id",
                "fixture-release",
                "--version",
                "0.1",
                "--output",
                str(evidence_path),
            ]
        )

    assert exc_info.value.code == 2
    assert evidence_path.read_bytes() == original


@pytest.mark.parametrize("target", ["baseline", "evidence"])
def test_regression_cli_check_refuses_to_overwrite_inputs(
    tmp_path: Path, target: str
) -> None:
    evidence = _evidence(b"fixture-mark keep")
    _, baseline_path = _create_baseline(tmp_path, evidence)
    current = tmp_path / "current.json"
    _write_evidence(current, evidence)
    paths = {"baseline": baseline_path, "evidence": current}
    before = paths[target].read_bytes()

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "check",
                str(baseline_path),
                str(current),
                "--output",
                str(paths[target]),
            ]
        )

    assert exc_info.value.code == 2
    assert paths[target].read_bytes() == before
