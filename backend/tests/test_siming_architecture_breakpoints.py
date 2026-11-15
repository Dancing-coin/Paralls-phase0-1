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
