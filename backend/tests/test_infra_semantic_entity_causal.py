from __future__ import annotations

import pytest

from app.gameplay.entity_causal_projection import EntityCausalProjection
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent
from app.gameplay.semantic_authority import SemanticEffectCommand, SemanticSettlementAuthority
from app.gameplay.semantic_registry import (
    MetaRuleDefinition,
    RuleEvaluationInput,
    SemanticRegistry,
    SemanticRegistryError,
    SemanticSelector,
    TagAssignment,
    TagDefinition,
)
from app.gameplay.shared_contracts import EffectProposal


def _event(
    event_id: str,
    *,
    sequence: int,
    revision: int,
    causation_id: str,
    payload: dict[str, object],
) -> GameplayEvent:
    return GameplayEvent(
        event_id=event_id,
        event_type="world.frost.applied",
        schema_version=1,
        stream_id="farm:frost:1",
        stream_revision=revision,
        global_sequence=sequence,
        transaction_id=f"tx:{event_id}",
        command_id=f"cmd:{event_id}",
        causation_id=causation_id,
        correlation_id="corr:infra:1",
        visibility_policy="authority_only",
        payload=payload,
    )


def _registry() -> SemanticRegistry:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:thing", category="type", version="1"))
    registry.register_tag(TagDefinition(tag_ref="material:wood", category="material", parent_refs=("type:thing",), version="1", specificity=1))
    registry.register_tag(TagDefinition(tag_ref="substance:oak", category="substance", parent_refs=("material:wood",), parameter_schema={"ignition": "int"}, version="1", specificity=2))
    registry.register_tag(TagDefinition(tag_ref="property:flammable", category="property", parameter_schema={"ignition": "int"}, version="1", specificity=3))
    registry.assign_tag(TagAssignment(entity_ref="door:oak:1", tag_ref="substance:oak", parameter_values={"ignition": 451}, source_ref="fixture", revision=1))
    registry.assign_tag(TagAssignment(entity_ref="door:oak:1", tag_ref="property:flammable", parameter_values={"ignition": 451}, source_ref="fixture", revision=1))
    return registry


def test_snapshot_inheritance_selector_and_digest_are_deterministic() -> None:
    registry = _registry()
    first = registry.build_snapshot("door:oak:1", component_refs=("door_leaf",), policy_context_ref="policy:1", source_revision_vector={"semantic": 1})
    second = registry.build_snapshot("door:oak:1", component_refs=("door_leaf",), policy_context_ref="policy:1", source_revision_vector={"semantic": 1})

    assert first == second
    assert first.digest.startswith("sha256:")
    assert set(("type:thing", "material:wood", "substance:oak", "property:flammable")).issubset(first.resolved_tags)
    assert registry.select((first,), SemanticSelector(entity_kind="door", require_all_tags=("material:wood",), component_scope="door_leaf")) == (first,)


def test_semantic_registry_rejects_cycle_unknown_and_same_specificity_conflict_without_mutation() -> None:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="tag:a", category="type", parent_refs=("tag:b",), version="1"))
    registry.register_tag(TagDefinition(tag_ref="tag:b", category="type", version="1"))
    with pytest.raises(SemanticRegistryError, match="cycle"):
        registry.register_tag(TagDefinition(tag_ref="tag:b2", category="type", parent_refs=("tag:b2",), version="1"))
    with pytest.raises(SemanticRegistryError, match="unknown"):
        registry.assign_tag(TagAssignment(entity_ref="thing:1", tag_ref="tag:nope", source_ref="fixture", revision=1))
    with pytest.raises(ValueError, match="category"):
        TagDefinition(tag_ref="tag:invalid", category="arbitrary", version="1")
    with pytest.raises(ValueError, match="operator"):
        SemanticSelector(parameter_predicates={"temperature": {"script": "unsafe"}})

    conflict = SemanticRegistry()
    conflict.register_tag(TagDefinition(tag_ref="tag:x", category="property", parameter_schema={"value": "int"}, version="1", specificity=1))
    conflict.register_tag(TagDefinition(tag_ref="tag:y", category="property", parameter_schema={"value": "int"}, version="1", specificity=1))
    conflict.assign_tag(TagAssignment(entity_ref="thing:1", tag_ref="tag:x", parameter_values={"value": 1}, source_ref="a", revision=1))
    conflict.assign_tag(TagAssignment(entity_ref="thing:1", tag_ref="tag:y", parameter_values={"value": 2}, source_ref="b", revision=1))
    with pytest.raises(SemanticRegistryError, match="conflict"):
        conflict.build_snapshot("thing:1")


def test_causal_projection_derives_parent_and_children_without_writes() -> None:
    first = _event("evt:frost", sequence=1, revision=1, causation_id="cmd:weather", payload={"entity_ref": "environment:weather:1", "entity_kind": "environment", "status_refs": ["frosting"], "affected_entity_refs": ["farm:1"], "evidence_refs": ["evidence:weather:1"]})
    second = _event("evt:crop-loss", sequence=2, revision=2, causation_id="evt:frost", payload={"entity_ref": "farm:1", "entity_kind": "farm", "status_refs": ["crop_loss"], "causal_parent_refs": ["evt:frost"], "affected_entity_refs": ["farm:1"], "relationship": {"relationship_ref": "relationship:owner", "source_ref": "farm:1", "target_ref": "actor:owner", "relation_kind": "owned_by", "visibility_scope": "authority_only"}})

    projection = EntityCausalProjection().rebuild([second, first])
    assert projection.causal_parents("evt:crop-loss")[0].event_ref == "evt:frost"
    assert projection.causal_children("evt:frost")[0].event_ref == "evt:crop-loss"
    assert projection.dossier("farm:1")["digest"].startswith("sha256:")
    assert "farm:1" in projection.things



def test_causal_projection_incremental_replay_matches_full_rebuild() -> None:
    first = _event("evt:frost", sequence=1, revision=1, causation_id="cmd:weather", payload={"entity_ref": "environment:weather:1", "entity_kind": "environment", "status_refs": ["frosting"], "affected_entity_refs": ["farm:1"], "evidence_refs": ["evidence:weather:1"]})
    second = _event("evt:crop-loss", sequence=2, revision=2, causation_id="evt:frost", payload={"entity_ref": "farm:1", "entity_kind": "farm", "status_refs": ["crop_loss"], "causal_parent_refs": ["evt:frost"], "affected_entity_refs": ["farm:1"]})
    full = EntityCausalProjection().rebuild([first, second])
    checkpoint = EntityCausalProjection().rebuild([first])
    replayed = EntityCausalProjection().rebuild([second], initial=checkpoint)
    assert replayed.causal_events == full.causal_events
    assert replayed.entities == full.entities


def test_rejected_projection_input_does_not_mutate_existing_projection() -> None:
    projection = EntityCausalProjection().rebuild([_event("evt:ok", sequence=1, revision=1, causation_id="cmd:root", payload={"entity_ref": "farm:1", "entity_kind": "farm"})])
    before = projection.dossier("farm:1")
    with pytest.raises(ValueError):
        projection.rebuild([_event("evt:bad", sequence=2, revision=2, causation_id="evt:ok", payload={"entity_ref": {"invalid": True}, "entity_kind": "farm"})], initial=projection)
    assert projection.dossier("farm:1") == before


def test_semantic_effect_authority_commits_once_then_replays_scoped_causal_projection() -> None:
    registry = _registry()
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    snapshot = registry.build_snapshot(
        "door:oak:1",
        component_refs=("door_leaf",),
        policy_context_ref="policy:1",
        source_revision_vector={"semantic": 1},
    )
    command = SemanticEffectCommand(
        command_id="semantic:ignite:1",
        idempotency_key="semantic:ignite:1",
        principal_ref="authority:environment",
        owner_ref="authority:door",
        stream_id="door:oak:1",
        expected_revision=0,
        effect_ref="effect:ignite",
        target_ref="door:oak:1",
        semantic_snapshot=snapshot,
        expected_snapshot_digest=snapshot.digest,
        causal_parent_refs=("event:weather:1",),
        evidence_refs=("evidence:weather:1",),
        privacy_scope="project",
    )

    first = authority.settle(command)
    duplicate = authority.settle(command)

    assert first.committed is True
    assert first.idempotency_status == "new_commit"
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 1
    assert len(store.list_outbox()) == 1
    scoped = authority.project_scope("door:oak:1", scope="public")
    assert scoped["causal_event_refs"] == tuple(first.committed_event_ids)
    assert scoped["evidence_refs"] == ()
    full = authority.replay_projection()
    checkpoint = authority.replay_projection(checkpoint_at=1)
    assert full.projection_hash == checkpoint.projection_hash


def test_semantic_effect_authority_rejects_stale_digest_and_private_scope_without_writes() -> None:
    registry = _registry()
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    snapshot = registry.build_snapshot("door:oak:1", policy_context_ref="policy:1")
    command = SemanticEffectCommand(
        command_id="semantic:ignite:bad",
        idempotency_key="semantic:ignite:bad",
        principal_ref="authority:environment",
        owner_ref="authority:door",
        stream_id="door:oak:1",
        expected_revision=0,
        effect_ref="effect:ignite",
        target_ref="door:oak:1",
        semantic_snapshot=snapshot,
        expected_snapshot_digest="sha256:wrong",
        privacy_scope="private_evidence",
    )

    rejected = authority.settle(command)

    assert rejected.committed is False
    assert rejected.failure is not None
    assert rejected.failure.error_code == "semantic_snapshot_digest_mismatch"
    assert store.read_events() == []
    assert store.list_outbox() == []


def _semantic_authority_command(*, expected_revision: int = 0, privacy_scope: str = "project"):
    registry = _registry()
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    snapshot = registry.build_snapshot("door:oak:1", policy_context_ref="policy:1", source_revision_vector={"semantic": 1})
    command = SemanticEffectCommand(
        command_id="semantic:separate:1",
        idempotency_key="semantic:separate:1",
        principal_ref="authority:environment",
        owner_ref="authority:door",
        stream_id="door:oak:1",
        expected_revision=expected_revision,
        effect_ref="effect:ignite",
        target_ref="door:oak:1",
        semantic_snapshot=snapshot,
        expected_snapshot_digest=snapshot.digest,
        evidence_refs=("evidence:weather:1",),
        privacy_scope=privacy_scope,
    )
    return authority, store, command


def test_semantic_authority_success_writes_one_event_and_outbox_entry() -> None:
    authority, store, command = _semantic_authority_command()
    result = authority.settle(command)
    assert result.committed is True
    assert result.idempotency_status == "new_commit"
    assert len(store.read_events()) == 1
    assert len(store.list_outbox()) == 1


def test_semantic_authority_duplicate_replays_without_second_write() -> None:
    authority, store, command = _semantic_authority_command()
    authority.settle(command)
    result = authority.settle(command)
    assert result.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 1


def test_semantic_authority_scoped_projection_redacts_evidence_from_public() -> None:
    authority, _, command = _semantic_authority_command()
    authority.settle(command)
    assert authority.project_scope("door:oak:1", scope="public")["evidence_refs"] == ()
    assert authority.project_scope("door:oak:1", scope="authority")["evidence_refs"] == ("evidence:weather:1",)


def test_semantic_authority_checkpoint_tail_replay_matches_full() -> None:
    authority, _, command = _semantic_authority_command()
    authority.settle(command)
    assert authority.replay_projection().projection_hash == authority.replay_projection(checkpoint_at=1).projection_hash


def test_semantic_authority_revision_conflict_is_zero_write() -> None:
    authority, store, command = _semantic_authority_command(expected_revision=1)
    result = authority.settle(command)
    assert result.failure is not None
    assert result.failure.error_code == "revision_conflict"
    assert store.read_events() == []


def test_semantic_authority_private_proposal_is_zero_write() -> None:
    authority, store, command = _semantic_authority_command(privacy_scope="private_evidence")
    result = authority.settle(command)
    assert result.failure is not None
    assert result.failure.error_code == "semantic_privacy_scope_denied"
    assert store.read_events() == []


def test_meta_rule_enforces_phase_conflict_chain_budget_and_filtered_trace() -> None:
    registry = _registry()
    proposal = EffectProposal(
        proposal_id="proposal:frost",
        effect_ref="effect:frost",
        target_refs=("door:oak:1",),
        source_rule_ref="rule:frost",
    )
    registry.register_meta_rule(
        MetaRuleDefinition(
            rule_ref="rule:frost",
            rule_version="1",
            trigger_selectors=("fact:frost",),
            guard_expression="always",
            phase="derive",
            priority=10,
            conflict_policy="exclusive",
            evaluation_budget=1,
            proposal_templates=(proposal,),
            trace_policy="authority_only",
            source_revision="rules:1",
        )
    )
    snapshot = registry.build_snapshot("door:oak:1", policy_context_ref="policy:1")
    trace = registry.evaluate(
        RuleEvaluationInput(
            trigger_ref="fact:frost",
            semantic_snapshot=snapshot,
            causal_chain_id="chain:frost",
            chain_depth=0,
            chain_budget=1,
            requested_trace_scope="public",
        )
    )
    assert trace.rule_refs == ("rule:frost",)
    assert trace.conflict_decisions["rule:frost"] == "proposal_only"
    assert trace.explanation_visibility == "summary"
    with pytest.raises(SemanticRegistryError, match="chain_budget"):
        registry.evaluate(
            RuleEvaluationInput(
                trigger_ref="fact:frost",
                semantic_snapshot=snapshot,
                causal_chain_id="chain:frost",
                chain_depth=1,
                chain_budget=1,
            )
        )


def test_meta_rule_closed_snapshot_guards_allow_registered_predicates_and_reject_free_expressions() -> None:
    registry = _registry()
    proposal = EffectProposal(proposal_id="proposal:guarded", effect_ref="effect:guarded", target_refs=("door:oak:1",), source_rule_ref="rule:guarded")
    registry.register_meta_rule(
        MetaRuleDefinition(
            rule_ref="rule:guarded",
            rule_version="1",
            trigger_selectors=("fact:heat",),
            guard_expression="tag:property:flammable",
            phase="derive",
            priority=1,
            conflict_policy="exclusive",
            evaluation_budget=1,
            proposal_templates=(proposal,),
            trace_policy="summary",
            source_revision="rules:1",
        )
    )
    snapshot = registry.build_snapshot("door:oak:1", statuses=("status:dry",))
    trace = registry.evaluate(RuleEvaluationInput(trigger_ref="fact:heat", semantic_snapshot=snapshot))
    assert trace.guard_results == {"rule:guarded": True}
    assert trace.proposal_digests
    with pytest.raises(ValueError, match="guard_expression_unsupported"):
        registry.register_meta_rule(
            MetaRuleDefinition(
                rule_ref="rule:unsafe",
                rule_version="1",
                trigger_selectors=("fact:heat",),
                guard_expression="__import__('os').system('write')",
                phase="derive",
                priority=2,
                conflict_policy="exclusive",
                evaluation_budget=1,
                trace_policy="none",
                source_revision="rules:1",
            )
        )
