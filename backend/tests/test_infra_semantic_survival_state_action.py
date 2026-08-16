from __future__ import annotations

from unittest.mock import patch

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_authority import SemanticSettlementAuthority, SemanticSurvivalStateActionCommand
from app.gameplay.semantic_registry import SemanticRegistry, TagAssignment, TagDefinition
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.survival_runtime import SurvivalAuthority, SurvivalState


ACTOR = "character:ava"
STREAM = f"gameplay:survival:{ACTOR}"
OWNER = SurvivalAuthority._PRINCIPAL


def _registry(*, register_actions: bool = True) -> SemanticRegistry:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:character", category="type", version="1"))
    registry.assign_tag(TagAssignment(entity_ref=ACTOR, tag_ref="type:character", source_ref="fixture", revision=1))
    if register_actions:
        registry.register_survival_state_action_effects()
    return registry


def _open_cold(store: GameplayEventStore) -> None:
    result = SurvivalAuthority(store=store).apply_effect_state(
        command=GameplayCommandEnvelope(
            command_id="command:survival:action:seed",
            command_type="gameplay.survival.apply_state",
            command_version=1,
            principal_ref=OWNER,
            actor_ref=ACTOR,
            project_ref="project:demo",
            idempotency_key="survival:action:seed",
            expected_revisions={STREAM: 0},
            causation_id="cause:survival:action:seed",
            correlation_id="corr:survival:action:seed",
            source_ref="proposal:fixture",
            submitted_at="fixture",
            pinned_revisions={"semantic": 1},
            payload={},
        ),
        application=EffectApplication(
            effect_ref="effect:cold_exposure",
            target_component_ref=ACTOR,
            magnitude=100,
            stack_key="cold",
            expires_at_tick=8,
            causal_chain_id="chain:survival:action:seed",
        ),
        resistance=ResistanceProfile(effect_ref="effect:cold_exposure", source_ref=ACTOR, modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:cold", stack_policy="add", stack_limit=2, expiry_policy="scheduled"),
    )
    assert result.committed


def _open_fatigue(store: GameplayEventStore) -> None:
    result = SurvivalAuthority(store=store).apply_effect_state(
        command=GameplayCommandEnvelope(
            command_id="command:survival:fatigue:seed", command_type="gameplay.survival.apply_state",
            command_version=1, principal_ref=OWNER, actor_ref=ACTOR, project_ref="project:demo",
            idempotency_key="survival:fatigue:seed", expected_revisions={STREAM: 0},
            causation_id="cause:survival:fatigue:seed", correlation_id="corr:survival:fatigue:seed",
            source_ref="proposal:fixture", submitted_at="fixture", pinned_revisions={"semantic": 1}, payload={},
        ),
        application=EffectApplication(effect_ref="effect:fatigue_exposure", target_component_ref=ACTOR, magnitude=100, stack_key="fatigue", expires_at_tick=8, causal_chain_id="chain:fatigue"),
        resistance=ResistanceProfile(effect_ref="effect:fatigue_exposure", source_ref=ACTOR, modifier_basis_points=0, revision=1),
        definition=StateDefinition(state_ref="state:fatigued", stack_policy="refresh", stack_limit=1, expiry_policy="scheduled", transform_targets=("state:recovering",)),
    )
    assert result.committed


def _command(registry: SemanticRegistry, **overrides: object) -> SemanticSurvivalStateActionCommand:
    snapshot = registry.build_snapshot(ACTOR, source_revision_vector={"semantic": 1})
    values: dict[str, object] = {
        "command_id": "command:semantic:state-action:1",
        "idempotency_key": "semantic:state-action:1",
        "principal_ref": "authority:semantic",
        "owner_ref": OWNER,
        "stream_id": STREAM,
        "expected_revision": 2,
        "effect_ref": "effect:state_dispel",
        "target_ref": ACTOR,
        "state_ref": "state:cold",
        "semantic_snapshot": snapshot,
        "expected_snapshot_digest": snapshot.digest,
        "reason_ref": "reason:remedy",
        "privacy_scope": "project",
    }
    values.update(overrides)
    return SemanticSurvivalStateActionCommand(**values)


def test_semantic_survival_state_dispel_commits_existing_owner_events() -> None:
    store = GameplayEventStore()
    _open_cold(store)
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(_command(registry))

    assert result.committed
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.survival.state_dispelled",
        "gameplay.survival.obligation_cancelled",
    ]
    assert (ACTOR, "state:cold") not in SurvivalAuthority(store=store).projector().states


def test_semantic_survival_state_transform_commits_fixed_recovery_owner_events() -> None:
    store = GameplayEventStore()
    _open_cold(store)
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        _command(registry, effect_ref="effect:state_transform_recovery")
    )

    assert result.committed
    assert [event.event_type for event in store.read_events()][-3:] == [
        "gameplay.survival.state_dispelled",
        "gameplay.survival.state_transformed",
        "gameplay.survival.obligation_cancelled",
    ]
    assert SurvivalAuthority(store=store).projector().states[(ACTOR, "state:recovering")] == SurvivalState(
        state_ref="state:recovering", effect_ref="effect:remedy", stacks=1, effective_magnitude=50
    )


def test_semantic_survival_fatigue_dispel_commits_existing_owner_events() -> None:
    store = GameplayEventStore()
    _open_fatigue(store)
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        _command(registry, state_ref="state:fatigued")
    )

    assert result.committed
    assert [event.event_type for event in store.read_events()][-2:] == ["gameplay.survival.state_dispelled", "gameplay.survival.obligation_cancelled"]


def test_semantic_survival_fatigue_transform_commits_fixed_recovery_owner_events() -> None:
    store = GameplayEventStore()
    _open_fatigue(store)
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        _command(registry, state_ref="state:fatigued", effect_ref="effect:state_transform_recovery")
    )

    assert result.committed
    assert [event.event_type for event in store.read_events()][-3:] == [
        "gameplay.survival.state_dispelled", "gameplay.survival.state_transformed", "gameplay.survival.obligation_cancelled"
    ]


def test_semantic_survival_fatigue_action_rejects_nonproject_privacy_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        _command(registry, state_ref="state:fatigued", privacy_scope="authority_only")
    )

    assert not result.committed
    assert result.failure and result.failure.error_code == "semantic_survival_state_action_route_mismatch"
    assert store.read_events() == []


def test_semantic_survival_fatigue_action_duplicate_revision_and_replay_are_closed() -> None:
    store = GameplayEventStore()
    _open_fatigue(store)
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    command = _command(registry, state_ref="state:fatigued")
    first = authority.settle_registered_survival_state_action(command)
    duplicate = authority.settle_registered_survival_state_action(command)
    stale = authority.settle_registered_survival_state_action(
        _command(registry, command_id="command:fatigue:stale", idempotency_key="fatigue:stale", state_ref="state:fatigued", expected_revision=1)
    )

    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert stale.failure and stale.failure.error_code == "revision_conflict"
    assert authority.replay_projection().projection_hash == authority.replay_projection(checkpoint_at=2).projection_hash


def test_registered_survival_action_contract_declares_fixed_recovery_target() -> None:
    contracts = SemanticRegistry.closed_state_owner_contracts()
    cold = next(contract for contract in contracts if contract.state_ref == "state:cold")

    assert cold.definition.dispel_allowed is True
    assert cold.definition.transform_targets == ("state:recovering",)


def test_semantic_survival_action_uses_the_closed_contract_before_owner_fragment_write() -> None:
    store = GameplayEventStore()
    _open_cold(store)
    registry = _registry()
    contract = SemanticRegistry.require_closed_survival_state_action_contract(state_ref="state:cold")
    denied_contract = contract.model_copy(
        update={"definition": contract.definition.model_copy(update={"dispel_allowed": False})}
    )

    with patch.object(
        SemanticRegistry,
        "require_closed_survival_state_action_contract",
        return_value=denied_contract,
    ):
        result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
            _command(registry)
        )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "state_dispel_not_allowed"
    assert len(store.read_events()) == 2


def test_semantic_survival_state_action_rejects_unknown_effect_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        _command(registry, effect_ref="effect:unregistered")
    )

    assert not result.committed
    assert store.read_events() == []


def test_semantic_survival_state_action_rejects_unregistered_route_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry(register_actions=False)

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(_command(registry))

    assert not result.committed
    assert store.read_events() == []


def test_semantic_survival_state_action_rejects_wrong_owner_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        _command(registry, owner_ref="actor_gameplay.econ1_economy_domain")
    )

    assert not result.committed
    assert store.read_events() == []


def test_semantic_survival_state_action_rejects_wrong_stream_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        _command(registry, stream_id="gameplay:economy:wage:character:ava")
    )

    assert not result.committed
    assert store.read_events() == []


def test_semantic_survival_state_action_rejects_private_scope_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        _command(registry, privacy_scope="authority_only")
    )

    assert not result.committed
    assert store.read_events() == []


def test_semantic_survival_state_action_rejects_stale_vector_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry()
    snapshot = registry.build_snapshot(ACTOR, source_revision_vector={"semantic": 2})

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        _command(registry, semantic_snapshot=snapshot, expected_snapshot_digest=snapshot.digest)
    )

    assert not result.committed
    assert store.read_events() == []


def test_semantic_survival_state_action_rejects_blank_reason_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        _command(registry, reason_ref=" ")
    )

    assert not result.committed
    assert store.read_events() == []


def test_semantic_survival_state_action_rejects_revision_conflict_without_write() -> None:
    store = GameplayEventStore()
    _open_cold(store)
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        _command(registry, expected_revision=1)
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == 2


def test_semantic_survival_state_action_rejects_changed_duplicate_without_write() -> None:
    store = GameplayEventStore()
    _open_cold(store)
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_survival_state_action(_command(registry)).committed

    result = authority.settle_registered_survival_state_action(
        _command(registry, effect_ref="effect:state_transform_recovery")
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 4


def test_semantic_survival_state_action_replays_exact_duplicate_without_write() -> None:
    store = GameplayEventStore()
    _open_cold(store)
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    command = _command(registry)
    first = authority.settle_registered_survival_state_action(command)

    replayed = authority.settle_registered_survival_state_action(command)

    assert first.committed
    assert replayed.committed
    assert replayed.idempotency_status == "duplicate_replayed"
    assert replayed.committed_event_ids == first.committed_event_ids
    assert len(store.read_events()) == 4


def test_semantic_survival_state_action_rejects_changed_snapshot_duplicate_without_write() -> None:
    store = GameplayEventStore()
    _open_cold(store)
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_survival_state_action(_command(registry)).committed
    registry.register_tag(TagDefinition(tag_ref="property:treated", category="property", version="1"))
    registry.assign_tag(TagAssignment(entity_ref=ACTOR, tag_ref="property:treated", source_ref="fixture", revision=2))
    changed_snapshot = registry.build_snapshot(ACTOR, source_revision_vector={"semantic": 1})

    result = authority.settle_registered_survival_state_action(
        _command(
            registry,
            semantic_snapshot=changed_snapshot,
            expected_snapshot_digest=changed_snapshot.digest,
        )
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 4


def test_semantic_survival_state_action_outbox_is_project_scoped() -> None:
    store = GameplayEventStore()
    _open_cold(store)
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_survival_state_action(_command(registry)).committed

    assert {entry.audience for entry in store.list_outbox()} == {"project"}


def test_semantic_survival_state_action_replays_full_and_checkpoint_tail() -> None:
    store = GameplayEventStore()
    _open_cold(store)
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_survival_state_action(_command(registry)).committed

    assert authority.replay_projection().projection_hash == authority.replay_projection(checkpoint_at=2).projection_hash
