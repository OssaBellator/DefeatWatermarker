from __future__ import annotations

from collections.abc import Iterable

from .models import (
    Artifact,
    DetectionComparison,
    DetectionResult,
    EvaluationReport,
    MutationScenario,
    ScenarioEvaluation,
)
from .mutations.base import ArtifactMutation
from .registry import AdapterRegistry


class RobustnessEngine:
    """Runs predefined scenarios without feeding detector results to mutations."""

    def __init__(
        self,
        registry: AdapterRegistry,
        mutations: Iterable[ArtifactMutation],
        *,
        max_scenarios: int = 64,
    ) -> None:
        if max_scenarios < 1:
            raise ValueError("max_scenarios must be positive")
        self.registry = registry
        self.max_scenarios = max_scenarios
        self._mutations: dict[str, ArtifactMutation] = {}
        for mutation in mutations:
            if mutation.mutation_id in self._mutations:
                raise ValueError(f"duplicate mutation_id: {mutation.mutation_id}")
            self._mutations[mutation.mutation_id] = mutation

    def _detect(self, artifact: Artifact) -> tuple[DetectionResult, ...]:
        return tuple(
            adapter.detect(artifact)
            for adapter in self.registry
            if adapter.supports(artifact)
        )

    def evaluate(
        self,
        artifact: Artifact,
        scenarios: Iterable[MutationScenario],
    ) -> EvaluationReport:
        selected = tuple(scenarios)
        if len(selected) > self.max_scenarios:
            raise ValueError(f"scenario count exceeds max_scenarios={self.max_scenarios}")

        # Baseline is computed independently. Results are never passed to mutations.
        baseline = self._detect(artifact)
        baseline_by_adapter = {item.adapter_id: item for item in baseline}
        evaluations: list[ScenarioEvaluation] = []

        for scenario in selected:
            mutation = self._mutations.get(scenario.mutation_id)
            if mutation is None:
                raise KeyError(f"unknown predefined mutation: {scenario.mutation_id}")

            derivative = artifact
            for _ in range(scenario.generation_count):
                derivative = mutation.apply(derivative, scenario)

            after = self._detect(derivative)
            comparisons = tuple(
                DetectionComparison(
                    adapter_id=result.adapter_id,
                    baseline=baseline_by_adapter[result.adapter_id],
                    after=result,
                )
                for result in after
                if result.adapter_id in baseline_by_adapter
            )
            evaluations.append(ScenarioEvaluation(scenario=scenario, comparisons=comparisons))

        return EvaluationReport(
            artifact_name=artifact.name,
            media_type=artifact.media_type,
            baseline=baseline,
            scenarios=tuple(evaluations),
        )
