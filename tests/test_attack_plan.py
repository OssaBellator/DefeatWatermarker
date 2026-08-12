from __future__ import annotations

from defeat_watermarker.attack_plan import build_attack_plan
from defeat_watermarker.suites import suite_from_dict


def _suite():
    return suite_from_dict(
        {
            "schema_version": "0.1",
            "suite_id": "attack-plan-fixture",
            "version": "0.1",
            "description": "fixture",
            "scenarios": [
                {
                    "scenario_id": "low",
                    "mutation_id": "control.identity.v1",
                    "modality": "unknown",
                    "transformation_family": "control",
                    "severity": "low",
                    "generation_count": 1,
                },
                {
                    "scenario_id": "high",
                    "mutation_id": "control.byte-copy.v1",
                    "modality": "unknown",
                    "transformation_family": "control",
                    "severity": "high",
                    "generation_count": 2,
                },
            ],
        }
    )


def test_attack_plan_is_content_addressed_and_filters_before_execution() -> None:
    suite = _suite()
    plan = build_attack_plan(suite, max_severity="low")

    assert [item.scenario_id for item in plan.scenarios] == ["low"]
    assert plan.suite_digest == suite.digest
    assert len(plan.plan_digest) == 64
    assert plan.to_dict()["max_severity"] == "low"


def test_attack_plan_digest_is_stable() -> None:
    suite = _suite()
    first = build_attack_plan(suite)
    second = build_attack_plan(suite)

    assert first.plan_digest == second.plan_digest
