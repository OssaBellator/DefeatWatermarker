from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .digests import content_digest
from .models import Modality, MutationScenario

_MAX_SUITE_BYTES = 1024 * 1024
_MAX_SCENARIOS = 64
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_ALLOWED_SEVERITIES = frozenset({"control", "low", "medium", "high"})


class SuiteError(ValueError):
    """Raised when a robustness suite is malformed or exceeds safety bounds."""


@dataclass(frozen=True, slots=True)
class RobustnessSuite:
    """Immutable, content-addressed collection of predefined mutation scenarios."""

    schema_version: str
    suite_id: str
    version: str
    description: str
    scenarios: tuple[MutationScenario, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "0.1":
            raise SuiteError("unsupported suite schema_version")
        if not _ID_RE.fullmatch(self.suite_id):
            raise SuiteError("suite_id must be a simple stable identifier")
        if not self.version or len(self.version) > 64:
            raise SuiteError("version must be non-empty and at most 64 characters")
        if len(self.description) > 4000:
            raise SuiteError("description is too long")
        if not self.scenarios:
            raise SuiteError("suite must contain at least one scenario")
        if len(self.scenarios) > _MAX_SCENARIOS:
            raise SuiteError(f"suite exceeds {_MAX_SCENARIOS} scenarios")

        scenario_ids = [item.scenario_id for item in self.scenarios]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise SuiteError("scenario_id values must be unique")
        for scenario in self.scenarios:
            if not _ID_RE.fullmatch(scenario.scenario_id):
                raise SuiteError(f"invalid scenario_id: {scenario.scenario_id}")
            if not _ID_RE.fullmatch(scenario.mutation_id):
                raise SuiteError(f"invalid mutation_id: {scenario.mutation_id}")
            if not _ID_RE.fullmatch(scenario.transformation_family):
                raise SuiteError(
                    f"invalid transformation_family: {scenario.transformation_family}"
                )
            if scenario.severity not in _ALLOWED_SEVERITIES:
                raise SuiteError(f"unsupported severity: {scenario.severity}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "suite_id": self.suite_id,
            "version": self.version,
            "description": self.description,
            "scenarios": [
                {
                    "scenario_id": item.scenario_id,
                    "mutation_id": item.mutation_id,
                    "modality": item.modality.value,
                    "transformation_family": item.transformation_family,
                    "severity": item.severity,
                    "generation_count": item.generation_count,
                }
                for item in self.scenarios
            ],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.to_dict())


def _expect_exact_keys(value: dict[str, Any], allowed: frozenset[str], noun: str) -> None:
    extras = sorted(set(value) - allowed)
    missing = sorted(allowed - set(value))
    if extras:
        raise SuiteError(f"{noun} has unknown fields: {', '.join(extras)}")
    if missing:
        raise SuiteError(f"{noun} is missing fields: {', '.join(missing)}")


def suite_from_dict(payload: dict[str, Any]) -> RobustnessSuite:
    if not isinstance(payload, dict):
        raise SuiteError("suite document must be a JSON object")
    _expect_exact_keys(
        payload,
        frozenset({"schema_version", "suite_id", "version", "description", "scenarios"}),
        "suite",
    )
    raw_scenarios = payload["scenarios"]
    if not isinstance(raw_scenarios, list):
        raise SuiteError("scenarios must be an array")

    scenarios: list[MutationScenario] = []
    scenario_keys = frozenset(
        {
            "scenario_id",
            "mutation_id",
            "modality",
            "transformation_family",
            "severity",
            "generation_count",
        }
    )
    for index, raw in enumerate(raw_scenarios):
        if not isinstance(raw, dict):
            raise SuiteError(f"scenario {index} must be an object")
        _expect_exact_keys(raw, scenario_keys, f"scenario {index}")
        generation_count = raw["generation_count"]
        if type(generation_count) is not int:
            raise SuiteError(f"scenario {index} generation_count must be an integer")
        try:
            modality = Modality(raw["modality"])
        except (TypeError, ValueError) as exc:
            raise SuiteError(f"scenario {index} has an invalid modality") from exc
        try:
            scenarios.append(
                MutationScenario(
                    scenario_id=str(raw["scenario_id"]),
                    mutation_id=str(raw["mutation_id"]),
                    modality=modality,
                    transformation_family=str(raw["transformation_family"]),
                    severity=str(raw["severity"]),
                    generation_count=generation_count,
                )
            )
        except ValueError as exc:
            raise SuiteError(f"scenario {index} is invalid: {exc}") from exc

    return RobustnessSuite(
        schema_version=str(payload["schema_version"]),
        suite_id=str(payload["suite_id"]),
        version=str(payload["version"]),
        description=str(payload["description"]),
        scenarios=tuple(scenarios),
    )


def load_suite(path: Path) -> RobustnessSuite:
    if path.stat().st_size > _MAX_SUITE_BYTES:
        raise SuiteError(f"suite file exceeds {_MAX_SUITE_BYTES} bytes")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SuiteError(f"could not read suite: {exc}") from exc
    return suite_from_dict(payload)
