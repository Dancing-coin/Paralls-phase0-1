from __future__ import annotations

from app.gameplay.construction_production_runtime import ProductionRun, Recipe
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_authority import (
    SemanticProductionFinishCommand,
    SemanticSettlementAuthority,
)
from app.gameplay.semantic_registry import SemanticRegistry, TagAssignment, TagDefinition


def _registry() -> SemanticRegistry:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:facility", category="type", version="1"))
    registry.register_tag(
        TagDefinition(
            tag_ref="property:production_ready",
            category="property",
            version="1",
        )
    )
    registry.assign_tag(
        TagAssignment(
            entity_ref="facility:bakery:1",
            tag_ref="type:facility",
            source_ref="fixture",
            revision=1,
        )
    )
    registry.assign_tag(
        TagAssignment(
            entity_ref="facility:bakery:1",
            tag_ref="property:production_ready",
            source_ref="fixture",
            revision=1,
        )
    )
    return registry


def _command(*, expected_revision: int = 0, privacy_scope: str = "project"):
    registry = _registry()
    snapshot = registry.build_snapshot(
        "facility:bakery:1",
        policy_context_ref="policy:production:1",
        source_revision_vector={"semantic": 1, "production": expected_revision},
    )
    return registry, SemanticProductionFinishCommand(
        command_id="semantic:production-finish:1",
        idempotency_key="semantic:production-finish:1",
        principal_ref="authority:semantic",
        expected_revision=expected_revision,
        effect_ref="effect:production_due_finish",
        source_rule_ref="rule:production_due_finish:v1",
        rule_set_revision="rules:production:v1",
        trace_digest="sha256:trace",
        causal_chain_id="chain:production:1",
        semantic_snapshot=snapshot,
        expected_snapshot_digest=snapshot.digest,
        run=ProductionRun(
            run_ref="run:bakery:1",
            facility_ref="facility:bakery:1",
            recipe_ref="recipe:bread:1",
            started_tick=0,
            finish_tick=3,
            output_item="item:bread",
        ),
        recipe=Recipe(
            recipe_ref="recipe:bread:1",
            inputs={},
            output_item="item:bread",
            duration_ticks=3,
        ),
        tick=3,
        privacy_scope=privacy_scope,
    )


def test_semantic_production_finish_settles_only_through_owner_fragment_and_outbox() -> None:
    registry, command = _command()
    store = GameplayEventStore()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_production_finish(command)

    assert result.committed is True
    assert result.idempotency_status == "new_commit"
    assert [event.event_type for event in store.read_events()] == ["gameplay.construction_production.run_finished"]
    assert store.read_events()[0].payload["rule_set_revision"] == "rules:production:v1"
    assert len(store.list_outbox()) == 1


def test_semantic_production_finish_owner_decline_is_zero_write() -> None:
    registry, command = _command()
    store = GameplayEventStore()
    command = command.model_copy(update={"tick": 2}, deep=True)

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_production_finish(command)

    assert result.committed is False
    assert result.failure is not None
    assert result.failure.error_code == "production_not_due"
    assert store.read_events() == []
    assert store.list_outbox() == []


def test_semantic_production_finish_duplicate_is_idempotent() -> None:
    registry, command = _command()
    store = GameplayEventStore()
    authority = SemanticSettlementAuthority(store=store, registry=registry)

    authority.settle_production_finish(command)
    duplicate = authority.settle_production_finish(command)

    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 1


def test_semantic_production_finish_revision_conflict_is_zero_write() -> None:
    registry, command = _command(expected_revision=1)
    store = GameplayEventStore()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_production_finish(command)

    assert result.committed is False
    assert result.failure is not None
    assert result.failure.error_code == "revision_conflict"
    assert store.read_events() == []


def test_semantic_production_finish_private_evidence_is_zero_write() -> None:
    registry, command = _command(privacy_scope="private_evidence")
    store = GameplayEventStore()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_production_finish(command)

    assert result.committed is False
    assert result.failure is not None
    assert result.failure.error_code == "semantic_privacy_scope_denied"
    assert store.read_events() == []


def test_semantic_production_finish_checkpoint_tail_replay_matches_full() -> None:
    registry, command = _command()
    authority = SemanticSettlementAuthority(store=GameplayEventStore(), registry=registry)

    authority.settle_production_finish(command)

    assert authority.replay_projection().projection_hash == authority.replay_projection(checkpoint_at=1).projection_hash
