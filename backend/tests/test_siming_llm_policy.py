from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate
from app.services.siming_policy import SimingInterventionPolicy
from app.services.siming_policy import EntityEligibilityRegistry


def make_snapshot(**overrides: object) -> FairnessStateSnapshot:
    payload = {
        "snapshot_id": "fairness:1",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "known_fact_ids": ["visual_fact:300:char_c:light_level_drop"],
        "eligible_actor_ids": ["char_b"],
        "blocked_actor_ids": ["char_locked"],
    }
    payload.update(overrides)
    return FairnessStateSnapshot.model_validate(payload)


def make_candidate(**overrides: object) -> InterventionCandidate:
    payload = {
        "candidate_id": "cand:1",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "proposed_band": "fact_reveal",
        "target_actor_id": "char_b",
        "established_fact_ids": ["visual_fact:300:char_c:light_level_drop"],
        "source": "llm",
    }
    payload.update(overrides)
    return InterventionCandidate.model_validate(payload)


def test_policy_accepts_candidate_grounded_in_established_fact() -> None:
    result = SimingInterventionPolicy().evaluate(make_candidate(), snapshot=make_snapshot())

    assert result.accepted is True
    assert "established_fact_visible" in result.reasons


def test_policy_rejects_unknown_fact_reference() -> None:
    result = SimingInterventionPolicy().evaluate(
        make_candidate(established_fact_ids=["visual_fact:unknown"]),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "unknown_fact_reference" in result.reasons


def test_policy_rejects_blocked_actor_reveal() -> None:
    result = SimingInterventionPolicy().evaluate(
        make_candidate(target_actor_id="char_locked"),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "actor_not_eligible" in result.reasons


def test_policy_rejects_actor_that_is_not_eligible_and_not_blocked() -> None:
    result = SimingInterventionPolicy().evaluate(
        make_candidate(target_actor_id="char_c"),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "actor_not_eligible" in result.reasons


def test_policy_rejects_blocked_actor_even_when_actor_is_eligible() -> None:
    result = SimingInterventionPolicy().evaluate(
        make_candidate(target_actor_id="char_locked"),
        snapshot=make_snapshot(
            eligible_actor_ids=["char_b", "char_locked"],
            blocked_actor_ids=["char_locked"],
        ),
    )

    assert result.accepted is False
    assert "actor_not_eligible" in result.reasons


def test_policy_rejects_locked_truth_rewrite_tag() -> None:
    result = SimingInterventionPolicy().evaluate(
        make_candidate(reason_tags=["locked_truth_rewrite"]),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "locked_truth_rewrite" in result.reasons


def test_policy_rejects_environment_request_without_esm_validated_tag() -> None:
    result = SimingInterventionPolicy().evaluate(
        make_candidate(proposed_band="environment_request"),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "environment_request_requires_esm_path" in result.reasons


def test_policy_accepts_environment_request_with_esm_validated_tag() -> None:
    result = SimingInterventionPolicy().evaluate(
        make_candidate(
            proposed_band="environment_request",
            reason_tags=["esm_validated_request"],
        ),
        snapshot=make_snapshot(),
    )

    assert result.accepted is True
    assert "established_fact_visible" in result.reasons


def test_policy_requires_registered_environment_and_object_eligibility():
    environment = make_candidate(target_actor_id=None, target_environment_id="env_lamp")
    object_candidate = make_candidate(target_actor_id=None, target_object_id="obj_letter")
    snapshot = make_snapshot()
    assert "environment_not_eligible" in SimingInterventionPolicy().evaluate(environment, snapshot=snapshot).reasons
    assert "object_not_eligible" in SimingInterventionPolicy().evaluate(object_candidate, snapshot=snapshot).reasons


def test_policy_accepts_registered_environment_and_object_eligibility():
    snapshot = make_snapshot(eligible_environment_ids=["env_lamp"], eligible_object_ids=["obj_letter"])
    environment = make_candidate(target_actor_id=None, target_environment_id="env_lamp")
    object_candidate = make_candidate(target_actor_id=None, target_object_id="obj_letter")
    assert SimingInterventionPolicy().evaluate(environment, snapshot=snapshot).accepted
    assert SimingInterventionPolicy().evaluate(object_candidate, snapshot=snapshot).accepted


def test_entity_eligibility_registry_covers_all_target_kinds():
    registry = EntityEligibilityRegistry(
        actors=("char_b",), environments=("env_lamp",), objects=("obj_letter",)
    )
    assert registry.is_eligible("actor", "char_b")
    assert registry.is_eligible("environment", "env_lamp")
    assert registry.is_eligible("object", "obj_letter")


def test_s6_eligible_actor_cannot_bypass_environment_or_object_eligibility():
    candidate = make_candidate(target_environment_id="env_unknown", target_object_id="obj_unknown")
    result = SimingInterventionPolicy().evaluate(candidate, snapshot=make_snapshot())
    assert not result.accepted
    assert set(result.reasons) == {"environment_not_eligible", "object_not_eligible"}


def test_s6_all_mixed_targets_can_be_explicitly_eligible():
    result = SimingInterventionPolicy().evaluate(
        make_candidate(target_environment_id="env_lamp", target_object_id="obj_letter"),
        snapshot=make_snapshot(eligible_environment_ids=["env_lamp"], eligible_object_ids=["obj_letter"]),
    )
    assert result.accepted
