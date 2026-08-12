#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "0.1"
_PYTHON = "{python}"
SUITES = {
    "core": (
        ("preflight", ("bash", "scripts/test/preflight.sh")),
        ("pytest", (_PYTHON, "-m", "pytest", "-q")),
        ("benchmark-regression", (_PYTHON, "scripts/test/benchmark_regression.py")),
    ),
    "standard": (
        ("preflight", ("bash", "scripts/test/preflight.sh")),
        ("pytest", (_PYTHON, "-m", "pytest", "-q")),
        ("benchmark-regression", (_PYTHON, "scripts/test/benchmark_regression.py")),
        ("cli-smoke", ("bash", "scripts/test/cli_smoke.sh")),
        ("package-wheel", ("bash", "scripts/test/package.sh")),
        ("detector-conformance", ("bash", "scripts/test/conformance.sh")),
        ("benchmarks", ("bash", "scripts/test/benchmarks.sh")),
        ("batch", ("bash", "scripts/test/batch.sh")),
        ("fixtures", ("bash", "scripts/test/fixtures.sh")),
    ),
}
SUITES["optional"] = SUITES["standard"] + (
    ("signing", ("bash", "scripts/test/signing.sh")),
    ("video", ("bash", "scripts/test/video.sh")),
    ("c2pa", ("bash", "scripts/test/c2pa.sh")),
)


def content_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolve_command(command: tuple[str, ...]) -> tuple[str, ...]:
    if command and command[0] == _PYTHON:
        return (sys.executable, *command[1:])
    return command


def git_commit() -> str | None:
    try:
        result = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return (
        value
        if len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
        else None
    )


def run_suite(suite: str) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    for name, logical_command in SUITES[suite]:
        command = _resolve_command(logical_command)
        print(f"\n==> {name}: {' '.join(command)}", flush=True)
        try:
            completed = subprocess.run(command, cwd=ROOT, check=False)
            return_code = completed.returncode
        except OSError as exc:
            print(f"could not execute {command[0]}: {exc}", file=sys.stderr)
            return_code = 127
        steps.append(
            {
                "name": name,
                "command": list(logical_command),
                "return_code": return_code,
            }
        )
        if return_code != 0:
            break

    all_expected_steps_ran = len(steps) == len(SUITES[suite])
    core = {
        "schema_version": SCHEMA_VERSION,
        "suite": suite,
        "git_commit": git_commit(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "steps": steps,
        "passed": (
            bool(steps)
            and all(step["return_code"] == 0 for step in steps)
            and all_expected_steps_ran
        ),
    }
    return {"report_id": content_digest(core), **core}


def _expected_steps(suite: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return SUITES[suite]


def verify_report(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    required = {
        "report_id",
        "schema_version",
        "suite",
        "git_commit",
        "python_version",
        "python_implementation",
        "steps",
        "passed",
    }
    if set(payload) != required:
        return False, ["local test report has invalid fields"]

    report_id = payload.get("report_id")
    if (
        not isinstance(report_id, str)
        or len(report_id) != 64
        or any(character not in "0123456789abcdef" for character in report_id)
    ):
        errors.append("report_id is invalid")
    else:
        core = {key: value for key, value in payload.items() if key != "report_id"}
        if content_digest(core) != report_id:
            errors.append("report_id does not match local test report core")

    suite = payload.get("suite")
    if suite not in SUITES:
        errors.append("suite is invalid")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version is unsupported")

    commit = payload.get("git_commit")
    if commit is not None and (
        not isinstance(commit, str)
        or len(commit) != 40
        or any(character not in "0123456789abcdef" for character in commit)
    ):
        errors.append("git_commit is invalid")

    for field in ("python_version", "python_implementation"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            errors.append(f"{field} is invalid")

    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty array")
        steps = []
    else:
        for index, step in enumerate(steps):
            if not isinstance(step, dict) or set(step) != {
                "name",
                "command",
                "return_code",
            }:
                errors.append(f"step {index} has invalid fields")
                continue
            if not isinstance(step["name"], str) or not step["name"]:
                errors.append(f"step {index} name is invalid")
            if (
                not isinstance(step["command"], list)
                or not step["command"]
                or any(
                    not isinstance(item, str) or not item for item in step["command"]
                )
            ):
                errors.append(f"step {index} command is invalid")
            if type(step["return_code"]) is not int:
                errors.append(f"step {index} return_code is invalid")

    if steps and suite in SUITES:
        expected = _expected_steps(suite)
        if len(steps) > len(expected):
            errors.append("recorded steps exceed selected suite")
        for index, step in enumerate(steps[: len(expected)]):
            expected_name, expected_command = expected[index]
            if step.get("name") != expected_name:
                errors.append(
                    f"step {index} name does not match selected suite"
                )
            if step.get("command") != list(expected_command):
                errors.append(
                    f"step {index} command does not match selected suite"
                )

    passed = payload.get("passed")
    if type(passed) is not bool:
        errors.append("passed must be boolean")
    elif steps and suite in SUITES:
        expected_pass = all(step.get("return_code") == 0 for step in steps) and len(
            steps
        ) == len(SUITES[suite])
        if passed != expected_pass:
            errors.append("passed does not match recorded step outcomes")

    return not errors, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scripts/test/recorded.py")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser(
        "run", help="run a local suite and write content-addressed result evidence"
    )
    run.add_argument("--suite", choices=tuple(SUITES), default="standard")
    run.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".defeat-watermarker" / "local-test-report.json",
    )

    verify = sub.add_parser("verify", help="verify a local test result record")
    verify.add_argument("report", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify":
        payload = json.loads(args.report.read_text(encoding="utf-8"))
        valid, errors = verify_report(payload)
        print(
            json.dumps(
                {
                    "valid": valid,
                    "report_id": payload.get("report_id"),
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if valid else 4

    payload = run_suite(args.suite)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    valid, errors = verify_report(payload)
    if not valid:
        print(
            "internal local test report verification failed: " + "; ".join(errors),
            file=sys.stderr,
        )
        return 4
    print(f"\nLocal test report: {args.output}")
    print(f"Report ID: {payload['report_id']}")
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
