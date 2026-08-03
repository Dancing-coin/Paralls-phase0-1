from __future__ import annotations

from hashlib import sha256
import json

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.patch_rule_settlement import (
    GameplayPatchRuleSettlementError,
    GameplayPatchRuleSettlementService,
    PatchRuleSettlementCommand,
    PatchRuleSettlementContext,
)
from app.gameplay.patch_runtime import (
    CapabilityRegistry,
    GameplayPatchManifest,
    GameplayPatchRegistry,
    GameplayRuleEvaluator,
    RuleDefinition,
    RuleEffectTemplate,
)
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector


ACTOR = "actor:patch-rule"


def _digest(payload: object) -> str:
    return "sha256:" + sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _materialize_stamina(store: GameplayEventStore, current: int = 10) -> None:
    assert store.append_batch(
        {
            "transaction_id": "tx:resource:init",
            "command_id": "cmd:resource:init",
            "expected_stream_revisions": {f"gameplay:resources:{ACTOR}": 0},
            "pinned_revisions": {},
            "events": [{"event_id": "evt:resource:init", "event_type": "gameplay.resource.materialized", "schema_version": 1, "stream_id": f"gameplay:resources:{ACTOR}", "stream_revision": 0, "global_sequence": 0, "transaction_id": "tx:resource:init", "command_id": "cmd:resource:init", "causation_id": "cmd:resource:init", "correlation_id": "corr:resource", "visibility_policy": "authority_only", "payload": {"actor_ref": ACTOR, "resource_id": "core.stamina", "minimum": 0, "maximum": 20, "current": current}}],
            "idempotency_record": {"principal_ref": "test", "idempotency_key": "resource:init", "payload_digest": "sha256:init"},
            "outbox_entries": [],
            "result_digest": "sha256:init",
            "projection_refresh_hints": [],
        }
    ).committed


def _registry(*, effect_type: str = "resource.consume", payload: dict[str, object] | None = None) -> GameplayPatchRegistry:
    rule = RuleDefinition(
        rule_id="rule:cost",
        rule_version="1",
        trigger="action.attempt",
        effect_templates=(RuleEffectTemplate(effect_type=effect_type, payload=payload or {"actor_ref": ACTOR, "resource_id": "core.stamina", "amount": 3}),),
    )
    manifest = GameplayPatchManifest(
        manifest_schema_version=1,
        patch_id="patch:cost",
        patch_version="1.0.0",
        patch_revision_id="patch:cost@1.0.0",
        content_digest="pending",
        author_id="author:repo",
        trust_policy_ref="trust:repo",
        rules=(rule,),
        granted_effect_types=(effect_type,),
    )
    manifest = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    return registry


def _command(registry: GameplayPatchRegistry, *, command_id: str = "cmd:patch:settle") -> PatchRuleSettlementCommand:
    active = registry.active_patch_set
    assert active is not None
    payload = {
        "command_id": command_id,
        "actor_ref": ACTOR,
        "authority_principal": "gameplay_patch_authority",
        "idempotency_key": f"key:{command_id}",
        "causation_id": command_id,
        "correlation_id": "corr:patch-rule",
        "trigger": "action.attempt",
        "authority_tick": 1,
        "pinned_registry_revision": active.registry_revision,
        "pinned_active_patch_set_revision": active.active_patch_set_revision,
        "projection_inputs": {"actor": {"stamina": 10}},
    }
    return PatchRuleSettlementCommand(**payload, payload_digest=_digest(payload))


def _context() -> PatchRuleSettlementContext:
    return PatchRuleSettlementContext(
        authority_principal="gameplay_patch_authority",
        enabled_group_ids=("core.resources",),
        world_config_revision="world:demo:v1",
        policy_revision="policy:demo:v1",
    )


def test_resource_consume_rule_settles_through_one_authority_batch() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store)
    registry = _registry()
    service = GameplayPatchRuleSettlementService(
        store=store,
        patch_registry=registry,
        evaluator=GameplayRuleEvaluator(patch_registry=registry, capability_registry=CapabilityRegistry()),
    )

    result = service.evaluate_and_settle(
        _command(registry),
        context=_context(),
        resources=ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events()),
    )

    assert result.accepted is True
    assert result.changed is True
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.resource.materialized",
        "gameplay.resource.adjusted",
        "gameplay.patch.rule_settled",
    ]
    assert ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events()).entries["core.stamina"].current == 7


def test_unsupported_effect_or_insufficient_resource_fails_without_any_settlement_write() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, current=2)
    registry = _registry()
    service = GameplayPatchRuleSettlementService(store=store, patch_registry=registry, evaluator=GameplayRuleEvaluator(patch_registry=registry, capability_registry=CapabilityRegistry()))
    resources = ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events())

    with pytest.raises(GameplayPatchRuleSettlementError, match="resource_insufficient"):
        service.evaluate_and_settle(_command(registry), context=_context(), resources=resources)
    assert len(store.read_events()) == 1

    unsupported = _registry(effect_type="ownership.transfer", payload={"actor_ref": ACTOR})
    unsupported_service = GameplayPatchRuleSettlementService(store=store, patch_registry=unsupported, evaluator=GameplayRuleEvaluator(patch_registry=unsupported, capability_registry=CapabilityRegistry()))
    with pytest.raises(GameplayPatchRuleSettlementError, match="patch_effect_type_not_settleable"):
        unsupported_service.evaluate_and_settle(_command(unsupported, command_id="cmd:patch:unsupported"), context=_context(), resources=resources)
    assert len(store.read_events()) == 1


def test_stale_patch_revision_rejects_before_rule_or_resource_write() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store)
    registry = _registry()
    service = GameplayPatchRuleSettlementService(store=store, patch_registry=registry, evaluator=GameplayRuleEvaluator(patch_registry=registry, capability_registry=CapabilityRegistry()))
    command = _command(registry).model_copy(update={"pinned_active_patch_set_revision": "sha256:stale"})

    with pytest.raises(GameplayPatchRuleSettlementError, match="patch_active_set_revision_conflict"):
        service.evaluate_and_settle(command, context=_context(), resources=ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events()))
    assert len(store.read_events()) == 1
