import pytest

from app.population_continuity.siming_contracts import PopulationProjection, PopulationReadSet
from app.services.siming_population_capability import PopulationSimulationCapability
from app.character_agent.services.character_continuity import CharacterRuntimeContinuityPort
from test_character_simulation_frame import read_set
from test_population_handoff_continuity import HandoffCase


@pytest.fixture
def public_handoff_case(tmp_path):
    case = HandoffCase(tmp_path)
    try:
        yield case
    finally:
        case.close()


def personal_inputs(lock, **updates):
    cadence = read_set().cadence
    payload = dict(actor_ref="character:char_a", candidate_kind="routine_work", fidelity_tier="B1", due=True,
        from_tick=cadence.window_start, to_tick=cadence.window_end,
        activation_lock_ref=lock.lock_ref, activation_lock_revision=lock.held_revision,
        state_deltas={}, presentation_seed={"task": "保护照护承诺"})
    payload.update(updates)
    return PopulationReadSet.from_inputs(cadence, (PopulationProjection(ref="projection:handoff:char_a",
        scope="public", revision_vector=dict(cadence.base_revision_vector), payload=payload),))


@pytest.mark.parametrize("tier", ["B1", "B2", "B3"])
def test_public_capability_forwards_current_personal_lock_credential(public_handoff_case, tier):
    lock = public_handoff_case.take_lock()
    inputs = personal_inputs(lock, fidelity_tier=tier)
    capability = PopulationSimulationCapability(continuity_port=CharacterRuntimeContinuityPort(public_handoff_case.core))
    cycle = capability.run_default_decision_cycle(inputs.cadence, inputs)
    assert cycle.status == "accepted"
    assert len(cycle.continuity_receipts) == 1
    assert cycle.continuity_receipts[0].status == "committed"
    assert public_handoff_case.core.get_continuity_revision("char_a") == 1
    assert public_handoff_case.core.get_character_activation_lock("char_a") == lock


@pytest.mark.parametrize("updates", [
    {"activation_lock_ref": "lock:other:character:char_a"},
    {"activation_lock_revision": 999}, {"activation_lock_revision": True},
    {"activation_lock_ref": None, "activation_lock_revision": None},
    {"activation_lock_revision": None}, {"fidelity_tier": "B0"},
])
def test_public_capability_rejects_wrong_or_b0_credential_without_core_write(public_handoff_case, updates):
    lock = public_handoff_case.take_lock()
    inputs = personal_inputs(lock, **updates)
    before = public_handoff_case.core.get_session_timeline("char_a")
    capability = PopulationSimulationCapability(continuity_port=CharacterRuntimeContinuityPort(public_handoff_case.core))
    cycle = capability.run_default_decision_cycle(inputs.cadence, inputs)
    assert cycle.status in {"requeue", "rejected"}
    assert public_handoff_case.core.get_session_timeline("char_a") == before


@pytest.mark.parametrize("updates", [
    {"activation_lock_ref": ["invalid"]}, {"activation_lock_revision": {"invalid": 1}},
    {"activation_lock_revision": None},
])
def test_malformed_credential_is_formal_requeue_when_no_lock_is_held(public_handoff_case, updates):
    lock = public_handoff_case.take_lock()
    assert public_handoff_case.release(lock).committed
    inputs = personal_inputs(lock, **updates)
    before = public_handoff_case.core.get_session_timeline("char_a")
    capability = PopulationSimulationCapability(continuity_port=CharacterRuntimeContinuityPort(public_handoff_case.core))
    cycle = capability.run_default_decision_cycle(inputs.cadence, inputs)
    assert cycle.status == "requeue"
    assert public_handoff_case.core.get_session_timeline("char_a") == before
