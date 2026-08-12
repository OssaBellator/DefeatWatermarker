"""Defensive watermark/provenance robustness evaluation framework."""

from .engine import RobustnessEngine
from .models import Artifact, DetectionResult, MarkFamily, Modality, MutationScenario
from .registry import AdapterRegistry

__all__ = [
    "AdapterRegistry",
    "Artifact",
    "DetectionResult",
    "MarkFamily",
    "Modality",
    "MutationScenario",
    "RobustnessEngine",
]

__version__ = "0.1.0"
