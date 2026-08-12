import json

import pytest

from defeat_watermarker.suites import SuiteError, load_suite, suite_from_dict


def _suite_payload() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "suite_id": "control-baseline",
        "version": "0.1",
        "description": "fixture",
        "scenarios": [
            {
                "scenario_id": "identity",
                "mutation_id": "control.identity.v1",
                "modality": "unknown",
                "transformation_family": "control",
                "severity": "control",
                "generation_count": 1,
            }
        ],
    }


def test_suite_digest_is_stable_across_json_formatting(tmp_path) -> None:
    payload = _suite_payload()
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps(payload), encoding="utf-8")
    second.write_text(json.dumps(payload, indent=4, sort_keys=True), encoding="utf-8")

    assert load_suite(first).digest == load_suite(second).digest


def test_suite_rejects_unknown_fields() -> None:
    payload = _suite_payload()
    payload["adaptive_detector_feedback"] = True

    with pytest.raises(SuiteError, match="unknown fields"):
        suite_from_dict(payload)


def test_suite_rejects_duplicate_scenario_ids() -> None:
    payload = _suite_payload()
    assert isinstance(payload["scenarios"], list)
    payload["scenarios"].append(dict(payload["scenarios"][0]))

    with pytest.raises(SuiteError, match="unique"):
        suite_from_dict(payload)
