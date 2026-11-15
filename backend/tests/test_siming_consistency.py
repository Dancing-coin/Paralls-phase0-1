import pytest

from app.models.siming_event import SimingInput
from app.services.siming_runtime import SimingRuntime
from test_siming_llm_runtime import make_visual_fact_event


def projected_plan(runtime=None, **payload):
    runtime = runtime or SimingRuntime()
    event = make_visual_fact_event(**payload)
    return runtime, runtime.plan_initial(SimingInput(input_type="visual_fact_event", source_event=event))


def validate(plan):
    from app.services.siming_consistency import SimingConsistencyValidator
    effects = plan.effects
    return SimingConsistencyValidator().validate(
        effects.state_tree, effects.global_situation, effects.narrative_snapshot,
        current_tick=effects.state_tree.sim_tick_ts,
        narrative_revision=effects.narrative_state.revision,
    )


def test_all_consistent_without_mutating_live_models():
    runtime, plan = projected_plan()
    assert validate(plan) == []
    assert runtime._state_tree.latest_snapshot is None
    assert runtime._global_situation.snapshots == {}
    assert runtime._narrative_core._revision_by_room == {}


def test_actor_missing_in_global_situation():
    _, plan = projected_plan()
    plan.effects.global_situation.actor_ids = []
    findings = validate(plan)
    assert any(item.category == "actor_state" and item.entity_id == "global_situation" for item in findings)


def test_tick_mismatch():
    _, plan = projected_plan()
    plan.effects.global_situation.sim_tick_ts -= 1
    assert any(item.category == "tick_mismatch" for item in validate(plan))


@pytest.mark.parametrize("part", ["global_situation", "narrative_snapshot"])
def test_scope_and_event_mismatch(part):
    _, plan = projected_plan()
    getattr(plan.effects, part).room_id = "other_room"
    assert any(item.category == "scope_mismatch" for item in validate(plan))
    _, plan = projected_plan()
    if part == "global_situation":
        plan.effects.global_situation.authority_event_refs = ["other_event"]
    else:
        plan.effects.narrative_snapshot.source_event_id = "other_event"
    assert any(item.category == "event_missing" for item in validate(plan))


def test_revision_drift_is_detected_without_comparing_different_clocks():
    runtime, first = projected_plan()
    runtime.install_planned_state(first.effects)
    _, second = projected_plan(runtime)
    assert second.effects.narrative_snapshot.sim_tick_ts != second.effects.state_tree.sim_tick_ts
    assert validate(second) == []
    second.effects.narrative_state = second.effects.narrative_state.model_copy(update={"revision": 99})
    assert any(item.category == "revision_drift" for item in validate(second))


def test_drift_blocks_install_before_any_state_is_written(caplog):
    from app.services.siming_consistency import SimingConsistencyError
    runtime, plan = projected_plan()
    plan.effects.global_situation.actor_ids = []
    with pytest.raises(SimingConsistencyError):
        runtime.install_planned_state(plan.effects)
    assert runtime._state_tree.latest_snapshot is None
    assert runtime._narrative_core._revision_by_room == {}
    assert runtime._global_situation.snapshots == {}
    assert "siming_state_inconsistent" in caplog.text


def test_sync_tick_and_empty_tick_validate_only_applicable_projections():
    runtime = SimingRuntime()
    assert runtime.tick([]).outputs == []
    event = make_visual_fact_event()
    runtime.tick([SimingInput(input_type="visual_fact_event", source_event=event)])
    assert runtime._global_situation.snapshots
    assert runtime._state_tree.latest_snapshot.source_event_id == event.event_id
