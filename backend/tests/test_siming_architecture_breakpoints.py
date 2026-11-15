import pytest

from app.gameplay import event_schema_registry
from app.models.fact_type import FACT_TYPE_REGISTRY
from app.services.authority_graph_projector import HeavenlyAuthorityEventProjector
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_observe import SimingObservePipeline


def test_s3_projector_startup_rejects_unmapped_gameplay_schema(monkeypatch):
    existing = event_schema_registry.gameplay_schema_event_types()
    monkeypatch.setattr(event_schema_registry, "gameplay_schema_event_types",
                        lambda: (*existing, "gameplay.new_owner.unmapped@1"))
    with pytest.raises(RuntimeError, match="gameplay.new_owner.unmapped@1"):
        HeavenlyAuthorityEventProjector(InMemoryHeavenlyGraphAdapter(), scope_resolver=lambda _: None)


def test_s3_registry_covers_current_schemas_and_preserves_declared_domain():
    FACT_TYPE_REGISTRY.validate_event_type_coverage()
    assert HeavenlyAuthorityEventProjector._domain_for("gameplay.survival.body_changed") == "survival_body"
    assert HeavenlyAuthorityEventProjector._domain_for("gameplay.survival.undeclared") is None


def test_s2_observer_startup_rejects_unmapped_gameplay_schema(monkeypatch):
    monkeypatch.setattr(event_schema_registry, "gameplay_schema_event_types",
                        lambda: ("gameplay.new_owner.unmapped@1",))
    with pytest.raises(RuntimeError, match="gameplay.new_owner.unmapped@1"):
        SimingObservePipeline()


def test_s6_fallback_audit_carries_non_actor_eligibility():
    from test_siming_quality_monitor import make_state_tree
    from app.services.siming_fairness_audit import SimingFairnessAuditEngine
    tree = make_state_tree()
    tree.environment.summary.update(target_environment_id="env_lamp", target_object_id="obj_letter")
    snapshot = SimingFairnessAuditEngine().build_snapshot(tree)
    assert snapshot.eligible_environment_ids == ["env_lamp"]
    assert snapshot.eligible_object_ids == ["obj_letter"]


def test_s1_state_tree_reads_fields_from_typed_payload_schema():
    from app.models.fact_type import FactType
    from app.models.siming_runtime_state import ObservedSimingEvent
    from app.services import siming_state_tree
    from test_siming_agent_loop_runtime import make_visual_fact_event
    event = make_visual_fact_event(event_type="world_fact_event", payload_overrides={
        "room_ref": "env_custom", "person_ref": "actor_custom", "fact_ref": "fact:custom",
        "object_ref": "obj_custom",
    })
    schema = siming_state_tree.SimingPayloadSchema(
        environment_key="room_ref", actor_key="person_ref", fact_key="fact_ref", object_key="object_ref")
    tree = siming_state_tree.InMemorySimingStateTree(payload_schemas={FactType.WORLD_FACT: schema})
    snapshot = tree.plan_from_observed([ObservedSimingEvent.from_authority_event(event)], sim_tick_ts=301)
    assert snapshot.environment.summary["target_environment_id"] == "env_custom"
    assert snapshot.environment.summary["target_object_id"] == "obj_custom"
    assert snapshot.environment.summary["established_fact_id"] == "fact:custom"
    assert snapshot.character.summary["target_actor_id"] == "actor_custom"


def test_s1_state_tree_does_not_guess_undeclared_gameplay_payload_fields():
    from app.models.siming_runtime_state import ObservedSimingEvent
    from app.services.siming_state_tree import InMemorySimingStateTree
    from test_siming_agent_loop_runtime import make_visual_fact_event
    event = make_visual_fact_event(event_type="gameplay.inventory.item_instantiated@1")
    snapshot = InMemorySimingStateTree().plan_from_observed(
        [ObservedSimingEvent.from_authority_event(event)], sim_tick_ts=301)
    assert snapshot.character.summary["target_actor_id"] is None


@pytest.mark.parametrize("actors, expected", [(["actor_z", "actor_a"], "actor_a"), ([], None)])
def test_s8_visual_tick_uses_actual_roster_or_emits_no_action(actors, expected):
    from app.models.siming_event import SimingInput
    from app.services.siming_runtime import SimingRuntime
    from test_siming_llm_runtime import make_visual_fact_event
    runtime = SimingRuntime(actor_roster_resolver=lambda event: actors)
    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event(target_actor_id=None))])
    dispatches = [output for output in result.outputs if output.output_type == "dispatch_intent"]
    if expected is None:
        assert not dispatches
        assert any(output.selected_path == "no_action" for output in result.outputs)
    else:
        assert dispatches[0].payload["target_actor_id"] == expected


def test_s8_explicit_empty_roster_overrides_event_target_and_filters_blocked_actors():
    from app.services.siming_runtime import SimingRuntime
    from test_siming_llm_policy import make_snapshot
    from test_siming_llm_runtime import make_visual_fact_event
    event = make_visual_fact_event(target_actor_id="char_b")
    snapshot = make_snapshot()
    assert not SimingRuntime(actor_roster_resolver=lambda _: [])._policy_snapshot_for_event(event, snapshot).eligible_actor_ids
    snapshot = make_snapshot(eligible_actor_ids=[], blocked_actor_ids=["actor_locked"])
    result = SimingRuntime(actor_roster_resolver=lambda _: ["actor_locked", "actor_ok"])._policy_snapshot_for_event(event, snapshot)
    assert result.eligible_actor_ids == ["actor_ok"]


def test_s8_environment_attention_uses_roster_and_empty_roster_is_audited():
    from app.models.siming_event import SimingInput
    from app.services.siming_runtime import SimingRuntime
    from test_siming_agent_loop_runtime import make_visual_fact_event
    event = make_visual_fact_event(event_type="esm_result_event", payload_overrides={
        "target_actor_id": None, "result_type": "environment_state_result"})
    for actors in (["actor_custom"], []):
        result = SimingRuntime(actor_roster_resolver=lambda _: actors).tick([
            SimingInput(input_type="esm_result_event", source_event=event)])
        dispatches = [output for output in result.outputs if output.output_type == "dispatch_intent"]
        if actors:
            assert dispatches[0].payload["target_actor_id"] == "actor_custom"
        else:
            assert not dispatches
            assert any(audit.reason == "no_eligible_actor" for audit in result.audit_records)


def test_s8_roster_changes_invalidate_provider_pin():
    from app.models.siming_event import SimingInput
    from app.services.siming_runtime import SimingRuntime
    from test_siming_llm_runtime import make_visual_fact_event
    actors = ["actor_first"]
    runtime = SimingRuntime(actor_roster_resolver=lambda _: actors,
                            actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    pending = runtime.prepare_tick(SimingInput(input_type="visual_fact_event",
        source_event=make_visual_fact_event(target_actor_id=None)))
    from app.services.siming_continuation import run_siming_provider
    completion = run_siming_provider(runtime._llm_provider, pending.job.request_json)
    actors[:] = ["actor_second"]
    outcome = runtime.commit_provider_result(pending.job, completion)
    assert outcome.status == "zero_write"
    assert outcome.reason == "stale_pin"
