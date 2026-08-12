from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .digests import content_digest
from .suites import RobustnessSuite

_SEVERITY_ORDER = {"control": 0, "low": 1, "medium": 2, "high": 3}


class AttackPlanError(ValueError):
    """Raised when a fixed anti-watermark attack plan cannot be constructed."""


@dataclass(frozen=True, slots=True)
class PlannedScenario:
    scenario_id: str
    mutation_id: str
    modality: str
    transformation_family: str
    severity: str
    generation_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "mutation_id": self.mutation_id,
            "modality": self.modality,
            "transformation_family": self.transformation_family,
            "severity": self.severity,
            "generation_count": self.generation_count,
        }


@dataclass(frozen=True, slots=True)
class AttackPlan:
    suite_id: str
    suite_version: str
    suite_digest: str
    max_severity: str
    scenarios: tuple[PlannedScenario, ...]
    schema_version: str = "0.1"

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "suite": {
                "suite_id": self.suite_id,
                "version": self.suite_version,
                "digest": self.suite_digest,
            },
            "max_severity": self.max_severity,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }

    @property
    def plan_digest(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"plan_digest": self.plan_digest, **self.core_dict()}


def build_attack_plan(suite: RobustnessSuite, *, max_severity: str = "high") -> AttackPlan:
    try:
        ceiling = _SEVERITY_ORDER[max_severity]
    except KeyError as exc:
        raise AttackPlanError(
            "max_severity must be one of: control, low, medium, high"
        ) from exc

    selected = tuple(
        PlannedScenario(
            scenario_id=scenario.scenario_id,
            mutation_id=scenario.mutation_id,
            modality=scenario.modality.value,
            transformation_family=scenario.transformation_family,
            severity=scenario.severity,
            generation_count=scenario.generation_count,
        )
        for scenario in suite.scenarios
        if _SEVERITY_ORDER[scenario.severity] <= ceiling
    )
    if not selected:
        raise AttackPlanError("attack plan contains no scenarios at the requested severity")

    return AttackPlan(
        suite_id=suite.suite_id,
        suite_version=suite.version,
        suite_digest=suite.digest,
        max_severity=max_severity,
        scenarios=selected,
    )
