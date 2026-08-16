from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_authority import (
    SemanticConstructionMaintenanceDispelCommand,
    SemanticSettlementAuthority,
)
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.semantic_registry import SemanticRegistry


FACILITY = "facility:maintenance-action:1"
STREAM = f"gameplay:construction_production:{FACILITY}"


def _open_maintenance_state() -> tuple[GameplayEventStore, SemanticRegistry]:
    store = GameplayEventStore()
    construction = ConstructionProductionAuthority(store=store)
    facility = Facility(
        facility_ref=FACILITY,
        plot_ref="plot:maintenance-action:1",
        facility_kind="bakery",
        condition=1.0,
    )
    assert construction.settle_facility_acquisition(
        plot=Plot(
            plot_ref=facility.plot_ref,
            jurisdiction_ref="jurisdiction:maintenance-action:1",
            owner_ref="organization:maintenance-action:1",
        ),
        facility=facility,
        command_id="facility:maintenance-action:acquire",
        idempotency_key="facility:maintenance-action:acquire",
        causation_id="cause:maintenance-action:acquire",
        correlation_id="corr:maintenance-action:acquire",
    ).committed
    assert construction.apply_maintenance_state(
        command_id="maintenance-action:apply",
        idempotency_key="maintenance-action:apply",
        facility_ref=FACILITY,
        expected_revision=1,
        causation_id="cause:maintenance-action:apply",
        correlation_id="corr:maintenance-action:apply",
        source_ref="proposal:maintenance-action",
        submitted_at="2026-08-15T00:00:00Z",
        pinned_revisions={"semantic": 1},
        semantic_snapshot_digest="sha256:maintenance-action",
        application=EffectApplication(
            effect_ref="effect:maintenance_required",
            target_component_ref=FACILITY,
            magnitude=1,
            stack_key="maintenance",
            causal_chain_id="chain:maintenance-action",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:maintenance_required",
            source_ref=FACILITY,
            modifier_basis_points=0,
            revision=1,
        ),
        definition=StateDefinition(
            state_ref="state:maintenance_due",
            stack_policy="replace",
            stack_limit=1,
            expiry_policy="none",
        ),
    ).committed
    state_event_id = store.read_events()[-1].event_id
    assert construction.open_maintenance_state_obligation(
        state_event_id=state_event_id,
        due_tick=8,
        expected_revision=2,
        idempotency_key="maintenance-action:open",
        correlation_id="corr:maintenance-action:open",
    ).committed
    registry = SemanticRegistry()
    registry.register_construction_maintenance_state_action_effect()
    return store, registry


def _command(registry: SemanticRegistry) -> SemanticConstructionMaintenanceDispelCommand:
    snapshot = registry.build_snapshot(FACILITY, source_revision_vector={"semantic": 1})
    return SemanticConstructionMaintenanceDispelCommand(
        command_id="semantic:maintenance-action:dispel",
        idempotency_key="semantic:maintenance-action:dispel",
        principal_ref="authority:semantic",
        owner_ref="actor_gameplay.construction_production_domain",
        stream_id=STREAM,
        expected_revision=3,
        effect_ref="effect:maintenance_state_dispel",
        target_ref=FACILITY,
        state_ref="state:maintenance_due",
        semantic_snapshot=snapshot,
        expected_snapshot_digest=snapshot.digest,
        reason_ref="rule:maintenance-action:dispel",
        privacy_scope="project",
    )


def _zero_write_snapshot(store: GameplayEventStore) -> dict[str, object]:
    snapshot = store.export_snapshot()
    return {
        "events": snapshot["events"],
        "outbox": snapshot["outbox"],
        "idempotency": snapshot["idempotency"],
    }


def _assert_zero_write(before: dict[str, object], store: GameplayEventStore) -> None:
    assert _zero_write_snapshot(store) == before


def test_semantic_construction_maintenance_dispel_clears_state_and_cancels_open_obligation_in_one_batch() -> None:
    store, registry = _open_maintenance_state()

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_construction_maintenance_state_action(
        _command(registry)
    )

    assert result.committed
    assert [event.event_type for event in store.read_events()][-2:] == [
        "gameplay.construction_production.maintenance_state_dispelled",
        "gameplay.construction_production.maintenance_state_obligation_cancelled",
    ]
    assert ConstructionProductionAuthority(store=store).projector().maintenance_states == {}


def test_semantic_construction_maintenance_dispel_replays_exact_duplicate_without_write() -> None:
    store, registry = _open_maintenance_state()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    command = _command(registry)
    first = authority.settle_registered_construction_maintenance_state_action(command)

    before = _zero_write_snapshot(store)
    replayed = authority.settle_registered_construction_maintenance_state_action(command)

    assert first.committed
    assert replayed.committed
    assert replayed.idempotency_status == "duplicate_replayed"
    assert replayed.committed_event_ids == first.committed_event_ids
    _assert_zero_write(before, store)


def test_semantic_construction_maintenance_dispel_rejects_changed_duplicate_without_write() -> None:
    store, registry = _open_maintenance_state()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_construction_maintenance_state_action(_command(registry)).committed

    before = _zero_write_snapshot(store)
    changed = authority.settle_registered_construction_maintenance_state_action(
        _command(registry).model_copy(update={"reason_ref": "rule:maintenance-action:changed"})
    )

    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    _assert_zero_write(before, store)


def test_semantic_construction_maintenance_dispel_rejects_revision_conflict_without_write() -> None:
    store, registry = _open_maintenance_state()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_construction_maintenance_state_action(_command(registry)).committed

    before = _zero_write_snapshot(store)
    stale = authority.settle_registered_construction_maintenance_state_action(
        _command(registry).model_copy(
            update={
                "command_id": "semantic:maintenance-action:stale",
                "idempotency_key": "semantic:maintenance-action:stale",
            }
        )
    )

    assert not stale.committed
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    _assert_zero_write(before, store)


def test_semantic_construction_maintenance_dispel_rejects_nonproject_privacy_without_write() -> None:
    store, registry = _open_maintenance_state()
    authority = SemanticSettlementAuthority(store=store, registry=registry)

    before = _zero_write_snapshot(store)
    rejected = authority.settle_registered_construction_maintenance_state_action(
        _command(registry).model_copy(
            update={
                "command_id": "semantic:maintenance-action:privacy",
                "idempotency_key": "semantic:maintenance-action:privacy",
                "privacy_scope": "authority_only",
            }
        )
    )

    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == "semantic_construction_privacy_scope_denied"
    _assert_zero_write(before, store)


def test_semantic_construction_maintenance_dispel_uses_closed_state_contract_before_fragment_write() -> None:
    store, registry = _open_maintenance_state()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    contract = SemanticRegistry.require_closed_state_owner_contract(
        effect_ref="effect:maintenance_required",
        state_ref="state:maintenance_due",
    ).model_copy(
        update={
            "definition": StateDefinition(
                state_ref="state:maintenance_due",
                stack_policy="replace",
                stack_limit=1,
                expiry_policy="none",
                dispel_allowed=False,
            )
        }
    )

    before = _zero_write_snapshot(store)
    with patch.object(
        SemanticRegistry,
        "require_closed_state_owner_contract",
        return_value=contract,
    ):
        rejected = authority.settle_registered_construction_maintenance_state_action(_command(registry))

    assert not rejected.committed
    assert rejected.failure is not None and rejected.failure.error_code == "state_dispel_not_allowed"
    _assert_zero_write(before, store)


def test_semantic_construction_maintenance_dispel_rejects_transform_without_write() -> None:
    store, registry = _open_maintenance_state()
    authority = SemanticSettlementAuthority(store=store, registry=registry)

    before = _zero_write_snapshot(store)
    rejected = authority.settle_registered_construction_maintenance_state_action(
        _command(registry).model_copy(
            update={
                "command_id": "semantic:maintenance-action:transform",
                "idempotency_key": "semantic:maintenance-action:transform",
                "effect_ref": "effect:state_transform_recovery",
            }
        )
    )

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "semantic_construction_maintenance_state_action_route_unknown"
    _assert_zero_write(before, store)


def test_semantic_construction_maintenance_dispel_rejects_unknown_effect_without_write() -> None:
    store, registry = _open_maintenance_state()
    authority = SemanticSettlementAuthority(store=store, registry=registry)

    before = _zero_write_snapshot(store)
    rejected = authority.settle_registered_construction_maintenance_state_action(
        _command(registry).model_copy(
            update={
                "command_id": "semantic:maintenance-action:unknown",
                "idempotency_key": "semantic:maintenance-action:unknown",
                "effect_ref": "effect:unregistered",
            }
        )
    )

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "semantic_construction_maintenance_state_action_route_unknown"
    _assert_zero_write(before, store)


def test_semantic_construction_maintenance_dispel_checkpoint_tail_replay_matches_full_projection() -> None:
    store, registry = _open_maintenance_state()
    authority = SemanticSettlementAuthority(store=store, registry=registry)
    assert authority.settle_registered_construction_maintenance_state_action(_command(registry)).committed

    construction = ConstructionProductionAuthority(store=store)
    full = construction.projector()
    checkpoint_tail = construction.projector(checkpoint_at=3)

    assert full.maintenance_states == {}
    assert checkpoint_tail.maintenance_states == {}
    assert full.source_revision_vector == checkpoint_tail.source_revision_vector
from unittest.mock import patch
