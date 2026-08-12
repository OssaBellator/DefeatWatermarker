from __future__ import annotations

from collections.abc import Iterable

from .io_utils import DEFAULT_MAX_ARTIFACT_BYTES
from .models import (
    Artifact,
    DetectionComparison,
    DetectionResult,
    EvaluationReport,
    Modality,
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
        max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
    ) -> None:
        if max_scenarios < 1:
            raise ValueError("max_scenarios must be positive")
        if max_artifact_bytes < 1:
            raise ValueError("max_artifact_bytes must be positive")
        self.registry = registry
        self.max_scenarios = max_scenarios
        self.max_artifact_bytes = max_artifact_bytes
        self._mutations: dict[str, ArtifactMutation] = {}
        for mutation in mutations:
            if mutation.mutation_id in self._mutations:
                raise ValueError(f"duplicate mutation_id: {mutation.mutation_id}")
            self._mutations[mutation.mutation_id] = mutation

    def _check_size(self, artifact: Artifact, *, noun: str) -> None:
        if len(artifact.data) > self.max_artifact_bytes:
            raise ValueError(f"{noun} exceeds max_artifact_bytes={self.max_artifact_bytes}")

    def _detect(self, artifact: Artifact) -> tuple[DetectionResult, ...]:
        return tuple(
            adapter.detect(artifact)
            for adapter in self.registry
            if adapter.supports(artifact)
        )

    @staticmethod
    def _validate_scenario_modality(artifact: Artifact, scenario: MutationScenario) -> None:
        if (
            artifact.modality is not Modality.UNKNOWN
            and scenario.modality is not Modality.UNKNOWN
            and artifact.modality is not scenario.modality
        ):
            raise ValueError(
                f"scenario {scenario.scenario_id} expects {scenario.modality.value}, "
                f"artifact is {artifact.modality.value}"
            )

    def evaluate(
        self,
        artifact: Artifact,
        scenarios: Iterable[MutationScenario],
    ) -> EvaluationReport:
        self._check_size(artifact, noun="source artifact")
        selected = tuple(scenarios)
        if len(selected) > self.max_scenarios:
            raise ValueError(f"scenario count exceeds max_scenarios={self.max_scenarios}")

        # Baseline is computed independently. Results are never passed to mutations.
        baseline = self._detect(artifact)
        baseline_by_adapter = {item.adapter_id: item for item in baseline}
        evaluations: list[ScenarioEvaluation] = []

        for scenario in selected:
            self._validate_scenario_modality(artifact, scenario)
            mutation = self._mutations.get(scenario.mutation_id)
            if mutation is None:
                raise KeyError(f"unknown predefined mutation: {scenario.mutation_id}")

            derivative = artifact
            for generation in range(scenario.generation_count):
                derivative = mutation.apply(derivative, scenario)
                self._check_size(
                    derivative,
                    noun=f"scenario {scenario.scenario_id} generation {generation + 1} derivative",
                )

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
