from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "test" / "recorded.py"
SPEC = importlib.util.spec_from_file_location("defeat_watermarker_recorded_tests", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RECORDED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECORDED)


def _report() -> dict[str, object]:
    core = {
        "schema_version": "0.2",
        "suite": "core",
        "git_commit": None,
        "git_dirty": None,
        "python_version": "3.13.5",
        "python_implementation": "CPython",
        "steps": [
            {
                "name": "preflight",
                "command": ["bash", "scripts/test/preflight.sh"],
                "return_code": 0,
            },
            {
                "name": "pytest",
                "command": ["{python}", "-m", "pytest", "-q"],
                "return_code": 0,
            },
            {
                "name": "benchmark-regression",
                "command": ["{python}", "scripts/test/benchmark_regression.py"],
                "return_code": 0,
            },
        ],
        "passed": True,
    }
    return {"report_id": RECORDED.content_digest(core), **core}


def _rebind(payload: dict[str, object]) -> None:
    payload["report_id"] = RECORDED.content_digest(
        {key: value for key, value in payload.items() if key != "report_id"}
    )


def test_valid_local_test_report_verifies() -> None:
    valid, errors = RECORDED.verify_report(_report())

    assert valid is True
    assert errors == []


def test_rehashed_false_pass_is_rejected() -> None:
    payload = _report()
    payload["steps"][1]["return_code"] = 1
    _rebind(payload)

    valid, errors = RECORDED.verify_report(payload)

    assert valid is False
    assert "passed does not match recorded step outcomes" in errors


def test_truncated_successful_suite_is_rejected() -> None:
    payload = _report()
    payload["steps"] = payload["steps"][:1]
    _rebind(payload)

    valid, errors = RECORDED.verify_report(payload)

    assert valid is False
    assert "passed does not match recorded step outcomes" in errors


def test_rehashed_substituted_successful_command_is_rejected() -> None:
    payload = _report()
    payload["steps"][1]["command"] = ["{python}", "-c", "pass"]
    _rebind(payload)

    valid, errors = RECORDED.verify_report(payload)

    assert valid is False
    assert "step 1 command does not match selected suite" in errors


def test_rehashed_renamed_step_is_rejected() -> None:
    payload = _report()
    payload["steps"][0]["name"] = "fake-preflight"
    _rebind(payload)

    valid, errors = RECORDED.verify_report(payload)

    assert valid is False
    assert "step 0 name does not match selected suite" in errors


def test_git_dirty_requires_commit() -> None:
    payload = _report()
    payload["git_dirty"] = True
    _rebind(payload)

    valid, errors = RECORDED.verify_report(payload)

    assert valid is False
    assert "git_dirty must be null when git_commit is unavailable" in errors


def test_git_dirty_must_be_boolean_or_null() -> None:
    payload = _report()
    payload["git_commit"] = "a" * 40
    payload["git_dirty"] = "yes"
    _rebind(payload)

    valid, errors = RECORDED.verify_report(payload)

    assert valid is False
    assert "git_dirty must be boolean or null" in errors
