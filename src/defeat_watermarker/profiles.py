from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .capabilities import capability_document
from .digests import content_digest
from .models import Modality
from .suites import RobustnessSuite

_MAX_PROFILE_BYTES = 1024 * 1024
_MAX_REQUIREMENTS = 128
_MAX_SOURCES = 32
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ProfileError(ValueError):
    """Raised when an engineering-readiness profile is malformed."""


class ReadinessStatus(str, Enum):
    READY = "engineering_ready"
    GAP = "engineering_gap"


@dataclass(frozen=True, slots=True)
class EngineeringProfile:
    schema_version: str
    profile_id: str
    version: str
    title: str
    applies_from: str
    scope_note: str
    required_modalities: tuple[Modality, ...]
    required_capabilities: tuple[str, ...]
    minimum_scenarios_per_modality: int
    source_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "0.1":
            raise ProfileError("unsupported profile schema_version")
        if not _ID_RE.fullmatch(self.profile_id):
            raise ProfileError("profile_id must be a stable identifier")
        if not self.version or len(self.version) > 64:
            raise ProfileError("profile version must be non-empty and at most 64 characters")
        if not self.title or len(self.title) > 512:
            raise ProfileError("profile title is missing or too long")
        if not _DATE_RE.fullmatch(self.applies_from):
            raise ProfileError("applies_from must use YYYY-MM-DD")
        if not self.scope_note or len(self.scope_note) > 4000:
            raise ProfileError("scope_note is missing or too long")
        if not self.required_modalities:
            raise ProfileError("profile must require at least one modality")
        if len(set(self.required_modalities)) != len(self.required_modalities):
            raise ProfileError("required_modalities must be unique")
        if not self.required_capabilities:
            raise ProfileError("profile must require at least one capability")
        if len(self.required_capabilities) > _MAX_REQUIREMENTS:
            raise ProfileError(f"profile exceeds {_MAX_REQUIREMENTS} capability requirements")
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ProfileError("required_capabilities must be unique")
        for capability in self.required_capabilities:
            if not _ID_RE.fullmatch(capability):
                raise ProfileError(f"invalid capability identifier: {capability}")
        if not 1 <= self.minimum_scenarios_per_modality <= 64:
            raise ProfileError("minimum_scenarios_per_modality must be in 1..64")
        if not self.source_references or len(self.source_references) > _MAX_SOURCES:
            raise ProfileError(f"source_references must contain 1..{_MAX_SOURCES} entries")
        for source in self.source_references:
            if not source.startswith("https://") or len(source) > 4096:
                raise ProfileError("source references must be bounded HTTPS URLs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "version": self.version,
            "title": self.title,
            "applies_from": self.applies_from,
            "scope_note": self.scope_note,
            "required_modalities": [item.value for item in self.required_modalities],
            "required_capabilities": list(self.required_capabilities),
            "minimum_scenarios_per_modality": self.minimum_scenarios_per_modality,
            "source_references": list(self.source_references),
        }

    @property
    def digest(self) -> str:
        return content_digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class ProfileAssessment:
    profile_id: str
    profile_version: str
    profile_digest: str
    status: ReadinessStatus
    capability_gaps: tuple[str, ...]
    modality_scenario_counts: tuple[tuple[Modality, int], ...]
    modality_gaps: tuple[str, ...]
    suite_digests: tuple[str, ...]
    disclaimer: str = (
        "Engineering-readiness assessment only. This output is not a legal compliance "
        "determination, certification, or substitute for the AI Act, Commission guidelines, "
        "the Code of Practice, or competent-authority assessment."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "profile_digest": self.profile_digest,
            "status": self.status.value,
            "capability_gaps": list(self.capability_gaps),
            "modality_scenario_counts": {
                modality.value: count for modality, count in self.modality_scenario_counts
            },
            "modality_gaps": list(self.modality_gaps),
            "suite_digests": list(self.suite_digests),
            "disclaimer": self.disclaimer,
        }


def _exact_keys(value: dict[str, Any], allowed: frozenset[str], noun: str) -> None:
    extras = sorted(set(value) - allowed)
    missing = sorted(allowed - set(value))
    if extras:
        raise ProfileError(f"{noun} has unknown fields: {', '.join(extras)}")
    if missing:
        raise ProfileError(f"{noun} is missing fields: {', '.join(missing)}")


def profile_from_dict(payload: dict[str, Any]) -> EngineeringProfile:
    if not isinstance(payload, dict):
        raise ProfileError("profile document must be a JSON object")
    keys = frozenset(
        {
            "schema_version",
            "profile_id",
            "version",
            "title",
            "applies_from",
            "scope_note",
            "required_modalities",
            "required_capabilities",
            "minimum_scenarios_per_modality",
            "source_references",
        }
    )
    _exact_keys(payload, keys, "profile")

    raw_modalities = payload["required_modalities"]
    if not isinstance(raw_modalities, list):
        raise ProfileError("required_modalities must be an array")
    modalities: list[Modality] = []
    for raw in raw_modalities:
        try:
            modalities.append(Modality(raw))
        except (TypeError, ValueError) as exc:
            raise ProfileError(f"invalid required modality: {raw!r}") from exc

    raw_capabilities = payload["required_capabilities"]
    raw_sources = payload["source_references"]
    minimum = payload["minimum_scenarios_per_modality"]
    if not isinstance(raw_capabilities, list) or not all(
        isinstance(item, str) for item in raw_capabilities
    ):
        raise ProfileError("required_capabilities must be an array of strings")
    if not isinstance(raw_sources, list) or not all(isinstance(item, str) for item in raw_sources):
        raise ProfileError("source_references must be an array of strings")
    if type(minimum) is not int:
        raise ProfileError("minimum_scenarios_per_modality must be an integer")

    return EngineeringProfile(
        schema_version=str(payload["schema_version"]),
        profile_id=str(payload["profile_id"]),
        version=str(payload["version"]),
        title=str(payload["title"]),
        applies_from=str(payload["applies_from"]),
        scope_note=str(payload["scope_note"]),
        required_modalities=tuple(modalities),
        required_capabilities=tuple(raw_capabilities),
        minimum_scenarios_per_modality=minimum,
        source_references=tuple(raw_sources),
    )


def load_profile(path: Path) -> EngineeringProfile:
    if path.stat().st_size > _MAX_PROFILE_BYTES:
        raise ProfileError(f"profile file exceeds {_MAX_PROFILE_BYTES} bytes")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileError(f"could not read profile: {exc}") from exc
    return profile_from_dict(payload)


def assess_profile(
    profile: EngineeringProfile,
    suites: tuple[RobustnessSuite, ...],
) -> ProfileAssessment:
    available = {
        item["component_id"]
        for item in capability_document()["components"]
        if item["available"]
    }
    capability_gaps = tuple(
        capability
        for capability in profile.required_capabilities
        if capability not in available
    )

    counts: dict[Modality, int] = {modality: 0 for modality in profile.required_modalities}
    for suite in suites:
        for scenario in suite.scenarios:
            if scenario.modality in counts:
                counts[scenario.modality] += 1

    modality_gaps = tuple(
        f"{modality.value}: {counts[modality]}/{profile.minimum_scenarios_per_modality} scenarios"
        for modality in profile.required_modalities
        if counts[modality] < profile.minimum_scenarios_per_modality
    )
    status = (
        ReadinessStatus.READY
        if not capability_gaps and not modality_gaps
        else ReadinessStatus.GAP
    )
    return ProfileAssessment(
        profile_id=profile.profile_id,
        profile_version=profile.version,
        profile_digest=profile.digest,
        status=status,
        capability_gaps=capability_gaps,
        modality_scenario_counts=tuple(
            (modality, counts[modality]) for modality in profile.required_modalities
        ),
        modality_gaps=modality_gaps,
        suite_digests=tuple(suite.digest for suite in suites),
    )
