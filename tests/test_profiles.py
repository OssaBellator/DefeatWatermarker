import pytest

from defeat_watermarker.models import Modality, MutationScenario
from defeat_watermarker.profiles import (
    ProfileError,
    ReadinessStatus,
    assess_profile,
    profile_from_dict,
)
from defeat_watermarker.suites import RobustnessSuite


def _profile_payload() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "profile_id": "eu.article50.provider-marking",
        "version": "fixture",
        "title": "Fixture profile",
        "applies_from": "2026-08-02",
        "scope_note": "Engineering only; not legal certification.",
        "required_modalities": ["audio", "image", "video", "text"],
        "required_capabilities": ["metrics.detection-survival.v1"],
        "minimum_scenarios_per_modality": 1,
        "source_references": ["https://example.invalid/source"],
    }


def _suite(modality: Modality) -> RobustnessSuite:
    return RobustnessSuite(
        schema_version="0.1",
        suite_id=f"fixture-{modality.value}",
        version="0.1",
        description="fixture",
        scenarios=(
            MutationScenario(
                scenario_id=f"{modality.value}-scenario",
                mutation_id="control.identity.v1",
                modality=modality,
                transformation_family="control",
            ),
        ),
    )


def test_profile_assessment_reports_missing_modalities_without_legal_pass_claim() -> None:
    profile = profile_from_dict(_profile_payload())
    assessment = assess_profile(profile, (_suite(Modality.IMAGE),))
    payload = assessment.to_dict()
    assert assessment.status is ReadinessStatus.GAP
    assert payload["modality_scenario_counts"]["image"] == 1
    assert {item.split(":", 1)[0] for item in payload["modality_gaps"]} == {
        "audio",
        "video",
        "text",
    }
    assert "not a legal compliance" in payload["disclaimer"]


def test_profile_can_be_engineering_ready_when_all_declared_requirements_exist() -> None:
    profile = profile_from_dict(_profile_payload())
    assessment = assess_profile(
        profile,
        tuple(_suite(modality) for modality in profile.required_modalities),
    )
    assert assessment.status is ReadinessStatus.READY
    assert not assessment.capability_gaps
    assert not assessment.modality_gaps
    assert not assessment.unavailable_suite_mutations


def test_profile_rejects_unknown_fields() -> None:
    payload = _profile_payload()
    payload["legally_compliant"] = True
    with pytest.raises(ProfileError, match="unknown fields"):
        profile_from_dict(payload)
