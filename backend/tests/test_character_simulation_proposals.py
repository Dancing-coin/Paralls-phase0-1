from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.population_continuity.simulation_contracts import (
    ActivityCandidatePayload, ActionCandidatePayload, ContinuityDeltaPayload,
    DecisionConflictPayload, IntersectionPacket, ModuleFieldPolicy, ModuleProposal,
    SimulationCommitPacket, UpgradeRequestPayload,
)
from app.population_continuity.simulation_frame import validate_module_proposal
from test_character_simulation_frame import frame, module_definition


def proposal(**changes: object) -> ModuleProposal:
    inputs = frame()
    fields = dict(
        proposal_ref="proposal:fatigue:10", actor_ref=inputs.actor_ref,
        module_ref="needs", definition_version="1", frame_digest=inputs.frame_digest,
        proposal_kind="continuity_delta", typed_payload=ContinuityDeltaPayload(
            expected_group_revision=2, state_delta={"fatigue": 0.3},
        ),
        read_dependencies=dict(inputs.source_revision_vector), required_fidelity="B1",
        expiry_tick=20, source_ref="needs", idempotency_key="fatigue:10",
    )
    fields.update(changes)
    return ModuleProposal(**fields)


def validate(candidate: ModuleProposal, *, tick: int = 10, definition=None) -> ModuleProposal:
    return validate_module_proposal(proposal=candidate, definition=definition or module_definition(), frame=frame(), tick=tick)


def test_declared_candidate_is_read_only_and_uses_full_frame_dependencies() -> None:
    original = {"fatigue": 0.3}
    candidate = proposal(typed_payload=ContinuityDeltaPayload(expected_group_revision=2, state_delta=original))
    validate(candidate)
    original["fatigue"] = 0.8
    assert candidate.typed_payload.state_delta["fatigue"] == 0.3
    with pytest.raises(TypeError):
        candidate.typed_payload.state_delta["fatigue"] = 0.8
    assert candidate.model_validate_json(candidate.model_dump_json()) == candidate


@pytest.mark.parametrize("changes,reason", [
    ({"actor_ref": "character:char_b"}, "proposal_actor_mismatch"),
    ({"frame_digest": "sha256:other"}, "proposal_frame_mismatch"),
    ({"definition_version": "2"}, "proposal_definition_mismatch"),
    ({"module_ref": "unregistered"}, "proposal_definition_mismatch"),
    ({"read_dependencies": {}}, "proposal_read_dependencies_mismatch"),
    ({"required_fidelity": "B0"}, "proposal_fidelity_denied"),
    ({"expiry_tick": 10}, "proposal_expired"),
    ({"expiry_tick": 31}, "proposal_policy_deadline_exceeded"),
])
def test_stale_or_unpermitted_candidate_is_refused(changes: dict, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        validate(proposal(**changes))


def test_undeclared_field_and_capability_are_not_a_free_write_payload() -> None:
    with pytest.raises(ValueError, match="proposal_module_field_not_declared"):
        validate(proposal(typed_payload=ContinuityDeltaPayload(
            expected_group_revision=2, state_delta={"inventory.balance": 999},
        )))
    with pytest.raises(ValidationError):
        ActionCandidatePayload(intent_ref="intent:1", capability_ref="existing:capability", world_payload={"balance": 999})
    with pytest.raises(ValidationError):
        proposal(typed_payload={"kind": "continuity_delta", "schema_revision": "unregistered@1", "state_delta": {}})


@pytest.mark.parametrize("forbidden,denied", [("needs.fatigue", True), ("needs.tags", False), ("affect.fatigue", False)])
def test_individual_delta_respects_participation_forbidden_dimensions(forbidden, denied) -> None:
    participation = frame().participation_resolution.model_copy(update={"forbidden_dimensions": (forbidden,)})
    inputs = frame(participation=participation)
    candidate = proposal(frame_digest=inputs.frame_digest)
    if denied:
        with pytest.raises(ValueError, match="proposal_dimension_denied"):
            validate_module_proposal(proposal=candidate, definition=module_definition(), frame=inputs, tick=10)
    else:
        assert validate_module_proposal(proposal=candidate, definition=module_definition(), frame=inputs, tick=10) == candidate


@pytest.mark.parametrize("policy,denied", [
    (ModuleFieldPolicy(individual_only=False, group_summary_only=True), True),
    (ModuleFieldPolicy(), False),
    (ModuleFieldPolicy(individual_only=False, aggregatable=True), False),
])
def test_individual_delta_respects_module_field_policy(policy, denied) -> None:
    definition = module_definition().model_copy(update={"field_policies": {"fatigue": policy}})
    if denied:
        with pytest.raises(ValueError, match="proposal_individual_field_denied"):
            validate(proposal(), definition=definition)
    else:
        assert validate(proposal(), definition=definition) == proposal()


@pytest.mark.parametrize("payload", [
    ActivityCandidatePayload(activity_ref="activity:rest"),
    ActionCandidatePayload(intent_ref="intent:1", capability_ref="existing:capability"),
    UpgradeRequestPayload(trigger_ref="trigger:care", target_fidelity="B3"),
    DecisionConflictPayload(constraint_refs=("constraint:care",)),
])
def test_declared_kind_must_match_typed_payload(payload) -> None:
    with pytest.raises(ValidationError, match="proposal_kind_mismatch"):
        proposal(typed_payload=payload)
    candidate = proposal(proposal_kind=payload.kind, typed_payload=payload)
    assert candidate.model_validate_json(candidate.model_dump_json()) == candidate
    with pytest.raises(ValueError, match="proposal_kind_not_declared"):
        validate(candidate)


def test_proposal_requires_exactly_one_actor_or_cohort() -> None:
    for changes in ({"actor_ref": None}, {"cohort_ref": "cohort:bakery"}):
        with pytest.raises(ValidationError, match="simulation_subject_invalid"):
            proposal(**changes)
    cohort = proposal(actor_ref=None, cohort_ref="cohort:bakery")
    with pytest.raises(ValueError, match="proposal_actor_mismatch"):
        validate(cohort)


def test_only_registered_action_capability_and_upgrade_trigger_are_permitted() -> None:
    definition = module_definition().model_copy(update={
        "proposal_kinds": ("action_candidate", "upgrade_request"),
        "capability_refs": ("existing:capability",), "upgrade_triggers": ("trigger:care",),
    })
    action = proposal(proposal_kind="action_candidate", typed_payload=ActionCandidatePayload(
        intent_ref="intent:1", capability_ref="existing:capability",
    ))
    validate(action, definition=definition)
    with pytest.raises(ValueError, match="proposal_capability_not_declared"):
        validate(proposal(proposal_kind="action_candidate", typed_payload=ActionCandidatePayload(
            intent_ref="intent:1", capability_ref="unregistered:capability",
        )), definition=definition)
    upgrade = proposal(proposal_kind="upgrade_request", required_fidelity="B3", typed_payload=UpgradeRequestPayload(
        trigger_ref="trigger:care", target_fidelity="B3",
    ))
    validate(upgrade, definition=definition)
    with pytest.raises(ValueError, match="proposal_trigger_not_declared"):
        validate(proposal(proposal_kind="upgrade_request", required_fidelity="B3", typed_payload=UpgradeRequestPayload(
            trigger_ref="unregistered:trigger", target_fidelity="B3",
        )), definition=definition)
    with pytest.raises(ValueError, match="proposal_upgrade_fidelity_mismatch"):
        validate(upgrade.model_copy(update={"required_fidelity": "B1"}), definition=definition)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_proposal_delta_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValidationError):
        proposal(typed_payload=ContinuityDeltaPayload(expected_group_revision=2, state_delta={"fatigue": value}))


@pytest.mark.parametrize("tick", [True, -1, 10.0])
def test_proposal_validation_rejects_invalid_clock_values(tick) -> None:
    with pytest.raises(ValueError, match="proposal_tick_invalid"):
        validate(proposal(), tick=tick)


@pytest.mark.parametrize("changes", [
    {"expiry_tick": float("nan")},
    {"typed_payload": ActivityCandidatePayload(activity_ref="activity:rest")},
    {"typed_payload": ContinuityDeltaPayload(expected_group_revision=2, state_delta={"fatigue": 0.3})
        .model_copy(update={"state_delta": {"fatigue": float("inf")}})},
])
def test_proposal_acceptance_revalidates_model_copy_payload(changes: dict) -> None:
    with pytest.raises(ValidationError):
        validate(proposal().model_copy(update=changes))


def test_proposal_acceptance_returns_an_isolated_validated_copy() -> None:
    original = {"fatigue": 0.3}
    unvalidated = proposal().model_copy(update={"typed_payload":
        ContinuityDeltaPayload(expected_group_revision=2, state_delta=original)
        .model_copy(update={"state_delta": original})})
    accepted = validate(unvalidated)
    assert isinstance(accepted, ModuleProposal)
    original["fatigue"] = 0.9
    assert accepted.typed_payload.state_delta["fatigue"] == 0.3
    with pytest.raises(TypeError):
        accepted.typed_payload.state_delta["fatigue"] = 0.9


def packet(**changes: object) -> SimulationCommitPacket:
    fields = dict(
        actor_ref="character:char_a", from_tick=9, to_tick=10, expected_character_revision=2,
        source_revision_vector=dict(frame().source_revision_vector), proposal_refs=("proposal:fatigue:10",),
        owner_intent_refs=(), lock_ref="lock:world:character:char_a", lock_revision=3,
        read_set_digest=frame().read_set_digest, scope="public", idempotency_key="commit:10",
    )
    fields.update(changes)
    return SimulationCommitPacket(**fields)


def test_commit_packet_preserves_credentials_and_source_pins() -> None:
    candidate = packet()
    assert candidate.model_validate_json(candidate.model_dump_json()) == candidate
    with pytest.raises(TypeError):
        candidate.source_revision_vector["population:world:bakery"] = 99


@pytest.mark.parametrize("changes", [
    {"to_tick": 9}, {"to_tick": 8}, {"lock_revision": True},
    {"lock_ref": None}, {"expected_character_revision": None},
    {"proposal_refs": ("proposal:1", "proposal:1")},
    {"actor_ref": None, "cohort_ref": "cohort:bakery"},
])
def test_invalid_commit_credentials_or_window_are_rejected(changes: dict) -> None:
    with pytest.raises(ValidationError):
        packet(**changes)


def test_cohort_packet_does_not_carry_personal_credentials() -> None:
    candidate = packet(actor_ref=None, cohort_ref="cohort:bakery", expected_character_revision=None,
                       lock_ref=None, lock_revision=None)
    assert candidate.actor_ref is None
    assert candidate.cohort_ref == "cohort:bakery"


def test_intersection_packet_binds_original_lock_generation() -> None:
    candidate = IntersectionPacket(
        intersection_ref="intersection:1", actor_ref="character:char_a", trigger_kind="player_nearby",
        group_ref="cohort:bakery", last_confirmed_tick=9, continuity_revision=2,
        source_revision_vector=dict(frame().source_revision_vector), hard_constraints=("constraint:care",),
        unresolved_proposals=("proposal:1",), required_code_refs=("code:care",), target_fidelity="B3",
        lock_ref="lock:world:character:char_a", lock_revision=3,
    )
    assert candidate.model_validate_json(candidate.model_dump_json()) == candidate
    with pytest.raises(ValidationError):
        candidate.lock_revision = 4
