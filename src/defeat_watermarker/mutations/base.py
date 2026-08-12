from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Artifact, MutationScenario


class ArtifactMutation(ABC):
    """A predefined transformation.

    The interface intentionally receives no detector instance or DetectionResult,
    preventing detector-feedback coupling inside the evaluation engine.
    """

    mutation_id: str

    @abstractmethod
    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        raise NotImplementedError


class IdentityMutation(ArtifactMutation):
    mutation_id = "control.identity.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        return Artifact(
            data=artifact.data,
            media_type=artifact.media_type,
            name=artifact.name,
            modality=artifact.modality,
        )


class ByteCopyMutation(ArtifactMutation):
    mutation_id = "control.byte-copy.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        # Produces a distinct bytes object where possible while preserving content.
        copied = bytes(bytearray(artifact.data))
        return Artifact(
            data=copied,
            media_type=artifact.media_type,
            name=artifact.name,
            modality=artifact.modality,
        )
