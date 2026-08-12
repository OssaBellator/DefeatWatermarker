from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .capabilities import capability_document
from .digests import content_digest
from .suites import RobustnessSuite


class PreflightStatus(str, Enum):
    READY = "ready"
    GAP = "gap"


@dataclass(frozen=True, slots=True)
class ScenarioPreflight:
    scenario_id: str
    mutation_id: str
    known: bool
    runnable: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "mutation_id": self.mutation_id,
            "known": self.known,
            "runnable": self.runnable,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class SuitePreflightReport:
    suite_id: str
    suite_version: str
    suite_digest: str
    capability_digest: str
    status: PreflightStatus
    scenarios: tuple[ScenarioPreflight, ...]
    schema_version: str = "0.1"

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "suite_id": self.suite_id,
            "suite_version": self.suite_version,
            "suite_digest": self.suite_digest,
            "capability_digest": self.capability_digest,
            "status": self.status.value,
            "scenarios": [item.to_dict() for item in self.scenarios],
        }

    @property
    def report_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, **self.core_dict()}


def preflight_suite(suite: RobustnessSuite) -> SuitePreflightReport:
    capability = capability_document()
    components = {
        item["component_id"]: item
        for item in capability["components"]
        if item["component_type"] == "mutation"
    }
    scenarios: list[ScenarioPreflight] = []
    for scenario in suite.scenarios:
        component = components.get(scenario.mutation_id)
        if component is None:
            scenarios.append(
                ScenarioPreflight(
                    scenario_id=scenario.scenario_id,
                    mutation_id=scenario.mutation_id,
                    known=False,
                    runnable=False,
                    reason="mutation is not registered in the built-in capability document",
                )
            )
            continue
        runnable = bool(component["available"])
        scenarios.append(
            ScenarioPreflight(
                scenario_id=scenario.scenario_id,
                mutation_id=scenario.mutation_id,
                known=True,
                runnable=runnable,
                reason=None if runnable else (component.get("notes") or "mutation is unavailable"),
            )
        )
    frozen = tuple(scenarios)
    status = (
        PreflightStatus.READY
        if all(item.runnable for item in frozen)
        else PreflightStatus.GAP
    )
    return SuitePreflightReport(
        suite_id=suite.suite_id,
        suite_version=suite.version,
        suite_digest=suite.digest,
        capability_digest=content_digest(capability),
        status=status,
        scenarios=frozen,
    )
