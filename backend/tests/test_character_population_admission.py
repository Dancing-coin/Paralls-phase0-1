import pytest

from app.population_continuity.activation_policy import resolve_participation
from app.population_continuity.simulation_contracts import ParticipationPolicy
from app.population_continuity.world import WorldContinuityRuntime
from app.gameplay.event_schema_registry import EventSchemaRegistration
from test_population_handoff_continuity import HandoffCase
from test_population_member_ledger import ACTORS


@pytest.fixture
def admitted_case(tmp_path):
    case = HandoffCase(tmp_path)
    case.schemas.register(EventSchemaRegistration("population.world.resume", 1, "world:resume:1"))
    resolutions = {actor: resolve_participation(policies=(ParticipationPolicy(
        policy_ref="policy:prototype", revision="1", allowed_tiers=("B0", "B1", "B3")
            if actor == ACTORS[1] else ("B1", "B3"), allowed_modules=("needs",),
        b0_expiry_tick=100, review_tick=100),), tick=0) for actor in ACTORS}
    assert case.world.resume().committed
    case.world.configure_character_participation(resolutions=resolutions,
        activation_authority=case.authority, cohort_ref="cohort:test")
    try:
        yield case, resolutions
    finally:
        case.close()


def test_only_current_b0_member_advances_and_other_rows_stay_unchanged(admitted_case):
    case, _ = admitted_case
    cadence = case.world.build_population_cadence(window_start=0, window_end=1)
    before = {actor: dict(case.world.population_hot_state.read(actor.removeprefix("character:"))) for actor in ACTORS}
    projections = case.world.build_population_projections(cadence)
    assert tuple(item.payload["actor_ref"] for item in projections) == (ACTORS[1],)
    receipt = case.world.confirm_population_cadence(cadence)
    assert receipt.advanced_count == 1
    for actor in (ACTORS[0], ACTORS[2]):
        assert dict(case.world.population_hot_state.read(actor.removeprefix("character:"))) == before[actor]


def test_lock_appearing_after_preview_rejects_old_confirmation_without_advancing(admitted_case):
    case, _ = admitted_case
    cadence = case.world.build_population_cadence(window_start=0, window_end=1)
    case.world.build_population_projections(cadence)
    before = case.world.population_hot_state.export_rows()
    case.take_lock(ACTORS[1])
    with pytest.raises(ValueError, match="character_admission_stale"):
        case.world.confirm_population_cadence(cadence)
    assert case.world.population_hot_state.export_rows() == before


def test_held_personal_lock_excludes_b0_preview(admitted_case):
    case, _ = admitted_case
    case.take_lock(ACTORS[1])
    cadence = case.world.build_population_cadence(window_start=0, window_end=1)
    assert case.world.build_population_projections(cadence) == ()
    assert case.world.confirm_population_cadence(cadence).advanced_count == 0


def test_selective_recovery_preserves_each_actual_cursor_and_same_admission(admitted_case):
    case, resolutions = admitted_case
    cadence = case.world.build_population_cadence(window_start=0, window_end=1)
    case.world.build_population_projections(cadence)
    case.world.confirm_population_cadence(cadence)
    state = case.world.export_recovery_state()
    assert state["schema_version"] == 2
    assert state["active_b0_actor_ids"] == ["char_b"]
    restored = WorldContinuityRuntime(store=case.store, mode=case.mode, roster=case.roster)
    restored.configure_character_participation(resolutions=resolutions,
        activation_authority=case.authority, cohort_ref="cohort:test")
    restored.restore_recovery_state(state)
    assert restored.population_hot_state.export_rows() == case.world.population_hot_state.export_rows()
    assert restored.export_recovery_state() == state
    next_window = restored.build_population_cadence(window_start=1, window_end=2)
    assert tuple(item.payload["actor_ref"] for item in restored.build_population_projections(next_window)) == (ACTORS[1],)


def test_configuration_cannot_omit_or_add_a_resident(admitted_case):
    case, resolutions = admitted_case
    with pytest.raises(ValueError, match="character_participation_roster_mismatch"):
        case.world.configure_character_participation(resolutions={ACTORS[1]: resolutions[ACTORS[1]]},
            activation_authority=case.authority, cohort_ref="cohort:test")
