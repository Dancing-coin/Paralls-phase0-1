from __future__ import annotations

from app.gameplay.econ1_economy_runtime import EconomyAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_authority import SemanticSettlementAuthority, SemanticWageObligationCommand
from app.gameplay.semantic_registry import SemanticRegistry, TagAssignment, TagDefinition
from app.world_runtime.obligations import ObligationLifecycleProjection, ObligationLifecycleRegistration, ObligationSettlementCoordinator


WORKER = "character:ava"
STREAM = f"gameplay:economy:wage:{WORKER}"


def _registry(*, register_wage_row: bool = True) -> SemanticRegistry:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:character", category="type", version="1"))
    registry.assign_tag(TagAssignment(entity_ref=WORKER, tag_ref="type:character", source_ref="fixture", revision=1))
    if register_wage_row:
        registry.register_wage_accrual_due_effect()
    return registry


def _command(registry: SemanticRegistry, **overrides: object) -> SemanticWageObligationCommand:
    snapshot = registry.build_snapshot(WORKER, source_revision_vector={"semantic": 1})
    values: dict[str, object] = {
        "command_id": "command:semantic:wage:1",
        "idempotency_key": "semantic:wage:1",
        "principal_ref": "authority:semantic",
        "owner_ref": EconomyAuthority._PRINCIPAL,
        "stream_id": STREAM,
        "expected_revision": 0,
        "effect_ref": "effect:wage_accrual_due",
        "target_ref": WORKER,
        "semantic_snapshot": snapshot,
        "expected_snapshot_digest": snapshot.digest,
        "privacy_scope": "project",
        "accrual_ref": "accrual:semantic:1",
        "organization_ref": "organization:bakery",
        "work_evidence_refs": ("evidence:production:1",),
        "wage_amount_minor": 75,
        "due_tick": 4,
        "policy_revision": "1",
    }
    values.update(overrides)
    return SemanticWageObligationCommand(**values)


def _registration() -> ObligationLifecycleRegistration:
    return ObligationLifecycleRegistration(
        policy_ref="policy:economy_wage_accrual",
        policy_revision="1",
        owner_ref=EconomyAuthority._PRINCIPAL,
        stream_pattern="gameplay:economy:wage:{worker_ref}",
        opened_event_type="gameplay.economy.wage_obligation_opened",
        settled_event_type="gameplay.economy.wage_obligation_settled",
        cancelled_event_type="gameplay.economy.wage_obligation_cancelled",
        visibility_scope="project",
    )


def test_semantic_wage_effect_opens_existing_economy_obligation() -> None:
    store = GameplayEventStore()
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_wage_obligation(_command(registry))

    assert result.committed
    event = store.read_events()[0]
    assert event.event_type == "gameplay.economy.wage_obligation_opened"
    assert event.payload["semantic_effect_ref"] == "effect:wage_accrual_due"
    lifecycle = ObligationLifecycleProjection((_registration(),)).rebuild(store.read_events())
    assert lifecycle.open["obligation:economy:wage:character:ava:accrual:semantic:1"].due_tick == 4


def test_semantic_wage_effect_rejects_unknown_effect_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_wage_obligation(
        _command(registry, effect_ref="effect:unregistered")
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "semantic_effect_owner_route_unknown"
    assert store.read_events() == []


def test_semantic_wage_effect_rejects_unregistered_row_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry(register_wage_row=False)

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_wage_obligation(_command(registry))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "semantic_effect_owner_route_unknown"
    assert store.read_events() == []


def test_semantic_wage_effect_rejects_wrong_owner_without_write() -> None:
    registry = _registry()
    store = GameplayEventStore()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_wage_obligation(
        _command(registry, owner_ref="actor_gameplay.survival_domain")
    )

    assert not result.committed
    assert store.read_events() == []


def test_semantic_wage_effect_rejects_wrong_stream_without_write() -> None:
    registry = _registry()
    store = GameplayEventStore()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_wage_obligation(
        _command(registry, stream_id="gameplay:survival:character:ava")
    )

    assert not result.committed
    assert store.read_events() == []


def test_semantic_wage_effect_rejects_nonproject_privacy_without_write() -> None:
    registry = _registry()
    store = GameplayEventStore()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_wage_obligation(
        _command(registry, privacy_scope="authority_only")
    )

    assert not result.committed
    assert store.read_events() == []


def test_semantic_wage_effect_rejects_stale_vector_without_write() -> None:
    registry = _registry()
    stale_snapshot = registry.build_snapshot(WORKER, source_revision_vector={"semantic": 2})
    store = GameplayEventStore()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_wage_obligation(
        _command(registry, semantic_snapshot=stale_snapshot, expected_snapshot_digest=stale_snapshot.digest)
    )

    assert not result.committed
    assert store.read_events() == []


def test_semantic_wage_effect_preserves_duplicate_idempotency() -> None:
    store = GameplayEventStore()
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    command = _command(registry)

    first = authority.settle_registered_wage_obligation(command)
    duplicate = authority.settle_registered_wage_obligation(command)

    assert first.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 1


def test_semantic_wage_effect_rejects_changed_duplicate_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_wage_obligation(_command(registry)).committed

    result = authority.settle_registered_wage_obligation(_command(registry, wage_amount_minor=76))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 1


def test_semantic_wage_effect_rejects_malformed_wage_fields_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry()
    command = _command(registry).model_copy(update={"wage_amount_minor": 0})

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_wage_obligation(command)

    assert not result.committed
    assert store.read_events() == []


def test_semantic_wage_effect_rejects_stale_revision_without_write() -> None:
    store = GameplayEventStore()
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_wage_obligation(_command(registry)).committed

    result = authority.settle_registered_wage_obligation(
        _command(registry, command_id="command:semantic:wage:stale", idempotency_key="semantic:wage:stale")
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == 1


def test_semantic_wage_effect_outbox_is_project_scoped() -> None:
    store = GameplayEventStore()
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_wage_obligation(_command(registry)).committed

    assert {entry.audience for entry in store.list_outbox()} == {"project"}


def test_semantic_wage_effect_lifecycle_replays_full_and_checkpoint_tail() -> None:
    store = GameplayEventStore()
    registry = _registry()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_wage_obligation(_command(registry)).committed
    event = store.read_events()[0]
    obligation = ObligationLifecycleProjection((_registration(),)).rebuild(store.read_events()).open[
        "obligation:economy:wage:character:ava:accrual:semantic:1"
    ]
    from app.gameplay.shared_contracts import ScheduledObligation

    due = ScheduledObligation(
        obligation_id=obligation.obligation_id,
        owner_ref=obligation.owner_ref,
        due_tick=obligation.due_tick,
        policy_revision=obligation.policy_revision,
        status="due",
        source_refs=("policy:economy_wage_accrual",),
        idempotency_key="semantic:wage:settle:1",
        expected_revisions={STREAM: event.stream_revision},
        visibility_scope="project",
    )
    coordinator = ObligationSettlementCoordinator(store=store, lifecycle_registrations=(_registration(),))
    plan = coordinator.plan_settle(
        obligation=due,
        fragments=(EconomyAuthority(store=store).build_wage_obligation_settlement_fragment(obligation=due),),
        principal_ref="world_runtime.caller",
    )
    assert plan.ready and plan.owner_commit_batch is not None
    assert EconomyAuthority(store=store).commit_obligation_batch(plan.owner_commit_batch).committed

    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=1).projection_hash
