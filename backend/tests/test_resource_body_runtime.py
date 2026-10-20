from __future__ import annotations

from pathlib import Path
from hashlib import sha256

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.resource_body_runtime import (
    GameplayActionRequirement,
    GameplayActionSettlementCommand,
    RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
    ResourceBoundsMigrationAuthorityService,
    ResourceBoundsMigrationRequest,
    ResourceBodyActionSettlementService,
    ResourceBodyRuntimeError,
    ResourceBodyRuntimeProjector,
    ResourceDefinition,
    ResourceDefinitionRegistry,
    ResourceReservationAuthorityService,
    ResourceReservationCommand,
)
from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.resource_materialization import (
    CharacterResourceMaterializationCaller,
    ResourceMaterializationAuthorityService,
)


ACTOR = "actor:char_a"
RESOURCE_STREAM = f"gameplay:resources:{ACTOR}"
BODY_STREAM = f"gameplay:body:{ACTOR}"
PROFILE_DIR = Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"
MATERIALIZATION_ACTOR = "char_a"
MATERIALIZATION_RESOURCE_STREAM = f"gameplay:resources:{MATERIALIZATION_ACTOR}"


def _append(store: GameplayEventStore, *, command_id: str, stream_id: str, event_type: str, payload: dict[str, object]) -> None:
    result = store.append_batch(
        {
            "transaction_id": f"tx:{command_id}",
            "command_id": command_id,
            "expected_stream_revisions": {stream_id: store.get_stream_head(stream_id)},
            "pinned_revisions": {},
            "events": [
                {
                    "event_id": f"evt:{command_id}",
                    "event_type": event_type,
                    "schema_version": 1,
                    "stream_id": stream_id,
                    "stream_revision": 0,
                    "global_sequence": 0,
                    "transaction_id": f"tx:{command_id}",
                    "command_id": command_id,
                    "causation_id": command_id,
                    "correlation_id": "corr:resource-body",
                    "visibility_policy": "authority_only",
                    "payload": payload,
                }
            ],
            "idempotency_record": {
                "principal_ref": "resource-body-test-authority",
                "idempotency_key": command_id,
                "payload_digest": f"sha256:{command_id}",
            },
            "outbox_entries": [],
            "result_digest": f"sha256:{command_id}",
            "projection_refresh_hints": [],
        }
    )
    assert result.committed is True


def _materialize_stamina(store: GameplayEventStore, current: int) -> None:
    _append(
        store,
        command_id="cmd:materialize:stamina",
        stream_id=RESOURCE_STREAM,
        event_type="gameplay.resource.materialized",
        payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "minimum": 0, "maximum": 10, "current": current},
    )


def _materialize_mana(store: GameplayEventStore, current: int) -> None:
    _append(
        store,
        command_id="cmd:materialize:mana",
        stream_id=RESOURCE_STREAM,
        event_type="gameplay.resource.materialized",
        payload={"actor_ref": ACTOR, "resource_id": "core.mana", "minimum": 0, "maximum": 10, "current": current},
    )


def _migration_definitions() -> ResourceDefinitionRegistry:
    definitions = ResourceDefinitionRegistry()
    definitions.register(ResourceDefinition(resource_id="core.stamina", definition_version="1.0.0", minimum=0, maximum=10))
    definitions.register(ResourceDefinition(resource_id="core.stamina", definition_version="2.0.0", minimum=0, maximum=6))
    return definitions


def _materialize_versioned_stamina(store: GameplayEventStore, current: int) -> None:
    _append(
        store,
        command_id="cmd:materialize:versioned-stamina",
        stream_id=RESOURCE_STREAM,
        event_type="gameplay.resource.materialized",
        payload={
            "actor_ref": ACTOR,
            "resource_id": "core.stamina",
            "definition_version": "1.0.0",
            "minimum": 0,
            "maximum": 10,
            "current": current,
        },
    )


def test_v2_materialization_exposes_capacity_lock_debt_and_modifier_ledger():
    store = GameplayEventStore()
    _append(store, command_id="cmd:v2", stream_id=RESOURCE_STREAM,
            event_type="gameplay.resource.materialized", payload={
                "actor_ref": ACTOR, "resource_id": "core.stamina", "minimum": 0,
                "maximum": 10, "current": 7, "definition_version": "v2",
                "resource_schema": "resource.v2", "capacity": 10, "base_capacity": 10,
                "locked": 0, "debt": 0, "debt_ceiling": 0,
                "modifier_ledger": [], "modifier_ledger_digest": "sha256:" + sha256(b"[]").hexdigest(),
            })
    entry = ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events()).entries["core.stamina"]
    assert (entry.capacity, entry.base_capacity, entry.locked, entry.debt, entry.debt_ceiling) == (10, 10, 0, 0, 0)
    assert entry.modifier_ledger_digest == "sha256:" + sha256(b"[]").hexdigest()


def test_v2_materialization_rejects_tampered_capacity_or_debt():
    store = GameplayEventStore()
    _append(store, command_id="cmd:v2-bad", stream_id=RESOURCE_STREAM,
            event_type="gameplay.resource.materialized", payload={
                "actor_ref": ACTOR, "resource_id": "core.stamina", "minimum": 0,
                "maximum": 10, "current": 7, "resource_schema": "resource.v2",
                "capacity": 10, "base_capacity": 10, "locked": 0, "debt": 1,
                "debt_ceiling": 0, "modifier_ledger": [],
                "modifier_ledger_digest": "sha256:" + "0" * 64,
            })
    with pytest.raises(ResourceBodyRuntimeError):
        ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events())


def test_v2_modifier_ledger_attach_detach_replays_and_updates_capacity():
    store = GameplayEventStore()
    ledger = [{"modifier_ref": "mod:pack", "operation": "capacity_delta", "amount": 5, "source_event_id": "evt:source", "template_id": "resource-capacity:pack@1"}]
    digest = "sha256:" + sha256(__import__("json").dumps(ledger, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    _append(store, command_id="cmd:v2-ledger", stream_id=RESOURCE_STREAM,
            event_type="gameplay.resource.materialized", payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "minimum": 0, "maximum": 10, "current": 7, "definition_version": "v2", "resource_schema": "resource.v2", "capacity": 10, "base_capacity": 10, "locked": 0, "debt": 0, "debt_ceiling": 0, "modifier_ledger": [], "modifier_ledger_digest": "sha256:" + sha256(b"[]").hexdigest()})
    _append(store, command_id="cmd:attach", stream_id=RESOURCE_STREAM, event_type="gameplay.resource.modifier_attached", payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "modifier": ledger[0]})
    projection = ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events())
    assert projection.entries["core.stamina"].capacity == 15
    assert projection.entries["core.stamina"].modifier_ledger_digest == digest
    _append(store, command_id="cmd:detach", stream_id=RESOURCE_STREAM, event_type="gameplay.resource.modifier_detached", payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "modifier": ledger[0]})
    final = ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events()).entries["core.stamina"]
    assert final.capacity == 10 and final.modifier_ledger == ()


def test_recovery_modifier_does_not_recompute_capacity_from_base():
    store = GameplayEventStore()
    _append(store, command_id="cmd:recovery-modifier-materialize", stream_id=RESOURCE_STREAM,
            event_type="gameplay.resource.materialized", payload={
                "actor_ref": ACTOR, "resource_id": "core.stamina", "minimum": 0,
                "maximum": 10, "current": 7, "definition_version": "v2",
                "resource_schema": "resource.v2", "capacity": 10, "base_capacity": 5,
                "locked": 0, "debt": 0, "debt_ceiling": 0, "modifier_ledger": [],
                "modifier_ledger_digest": "sha256:" + sha256(b"[]").hexdigest(),
            })
    modifier = {
        "modifier_ref": "mod:recovery", "operation": "recovery_delta", "amount": 2,
        "source_event_id": "evt:recovery", "template_id": "recovery:source@1",
        "effective_world_tick": 10,
    }
    _append(store, command_id="cmd:recovery-modifier-attach", stream_id=RESOURCE_STREAM,
            event_type="gameplay.resource.modifier_attached", payload={
                "actor_ref": ACTOR, "resource_id": "core.stamina", "modifier": modifier,
            })
    entry = ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events()).entries["core.stamina"]
    assert entry.capacity == 10
    _append(store, command_id="cmd:recovery-modifier-detach", stream_id=RESOURCE_STREAM,
            event_type="gameplay.resource.modifier_detached", payload={
                "actor_ref": ACTOR, "resource_id": "core.stamina", "modifier": modifier,
                "effective_world_tick": 15,
            })
    detached = ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events()).entries["core.stamina"]
    assert detached.capacity == 10 and detached.current == 7


def _migration_request(projection_revision: str) -> ResourceBoundsMigrationRequest:
    return ResourceBoundsMigrationRequest(
        actor_ref=ACTOR,
        resource_id="core.stamina",
        from_definition_version="1.0.0",
        to_definition_version="2.0.0",
        expected_projection_revision=projection_revision,
        migration_digest="sha256:" + "a" * 64,
        migrator_code_digest=RESOURCE_BOUNDS_CLAMP_MIGRATOR_CODE_DIGEST,
    )


def _command(command_id: str, *, cost: int = 3) -> GameplayActionSettlementCommand:
    return GameplayActionSettlementCommand(
        command_id=command_id,
        actor_ref=ACTOR,
        authority_principal="resource_body_action_authority",
        idempotency_key=command_id,
        payload_digest=f"sha256:{command_id}",
        causation_id=command_id,
        correlation_id="corr:resource-body",
        requirement=GameplayActionRequirement(
            action_ref="skill:sword_slash",
            stamina_resource_id="core.stamina",
            stamina_cost=cost,
            required_function_id="grip.right",
        ),
    )


def test_action_settlement_rejects_forged_command_principal_without_writes() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    projector = ResourceBodyRuntimeProjector()
    command = _command("cmd:slash:forged-principal").model_copy(
        update={"authority_principal": "gameplay_authority"}
    )
    before = store.export_snapshot()

    result = ResourceBodyActionSettlementService(store=store).settle(
        command,
        resources=projector.rebuild_resources(ACTOR, store.read_events()),
        body=projector.rebuild_body(ACTOR, store.read_events()),
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )

    assert result.accepted is False
    assert result.reason_code == "authority_principal_mismatch"
    assert store.export_snapshot() == before


def test_right_arm_injury_blocks_learned_action_without_consuming_stamina() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    _append(
        store,
        command_id="cmd:injure:right-arm",
        stream_id=BODY_STREAM,
        event_type="gameplay.body.injury_applied",
        payload={
            "actor_ref": ACTOR,
            "injury_id": "injury:right-arm:fracture",
            "function_id": "grip.right",
            "capacity_ratio": 0,
        },
    )
    projector = ResourceBodyRuntimeProjector()
    resources = projector.rebuild_resources(ACTOR, store.read_events())
    body = projector.rebuild_body(ACTOR, store.read_events())

    result = ResourceBodyActionSettlementService(store=store).settle(
        _command("cmd:slash:injured"),
        resources=resources,
        body=body,
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )

    assert result.accepted is False
    assert result.reason_code == "body_function_unavailable"
    assert result.blocked_source_refs == ("evt:cmd:injure:right-arm",)
    assert len(store.read_events()) == 2
    assert projector.rebuild_resources(ACTOR, store.read_events()).entries["core.stamina"].current == 7


def test_insufficient_stamina_rejects_without_action_or_resource_events() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 2)
    projector = ResourceBodyRuntimeProjector()
    result = ResourceBodyActionSettlementService(store=store).settle(
        _command("cmd:slash:tired"),
        resources=projector.rebuild_resources(ACTOR, store.read_events()),
        body=projector.rebuild_body(ACTOR, store.read_events()),
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )

    assert result.accepted is False
    assert result.reason_code == "resource_insufficient"
    assert result.blocked_source_refs == ("evt:cmd:materialize:stamina",)
    assert [event.event_type for event in store.read_events()] == ["gameplay.resource.materialized"]


def test_success_consumes_stamina_and_settles_action_in_one_atomic_batch() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    projector = ResourceBodyRuntimeProjector()
    result = ResourceBodyActionSettlementService(store=store).settle(
        _command("cmd:slash:success"),
        resources=projector.rebuild_resources(ACTOR, store.read_events()),
        body=projector.rebuild_body(ACTOR, store.read_events()),
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )

    assert result.accepted is True
    assert result.append_result is not None
    assert result.append_result.committed_event_ids == [
        "evt:cmd:slash:success:resource-body:1",
        "evt:cmd:slash:success:resource-body:2",
    ]
    transaction = store.read_transactions()[-1]
    assert [event.event_type for event in transaction.events] == ["gameplay.resource.adjusted", "gameplay.action.settled"]
    assert projector.rebuild_resources(ACTOR, store.read_events()).entries["core.stamina"].current == 4


def test_recovery_restores_function_without_relearning_and_stale_projection_fails_closed() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    _append(
        store,
        command_id="cmd:injure:right-arm",
        stream_id=BODY_STREAM,
        event_type="gameplay.body.injury_applied",
        payload={"actor_ref": ACTOR, "injury_id": "injury:right-arm", "function_id": "grip.right", "capacity_ratio": 0},
    )
    projector = ResourceBodyRuntimeProjector()
    stale_resources = projector.rebuild_resources(ACTOR, store.read_events())
    injured_body = projector.rebuild_body(ACTOR, store.read_events())
    _append(
        store,
        command_id="cmd:recover:right-arm",
        stream_id=BODY_STREAM,
        event_type="gameplay.body.injury_recovered",
        payload={"actor_ref": ACTOR, "injury_id": "injury:right-arm"},
    )

    stale = ResourceBodyActionSettlementService(store=store).settle(
        _command("cmd:slash:stale"),
        resources=stale_resources,
        body=injured_body,
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )
    restored = ResourceBodyActionSettlementService(store=store).settle(
        _command("cmd:slash:restored"),
        resources=projector.rebuild_resources(ACTOR, store.read_events()),
        body=projector.rebuild_body(ACTOR, store.read_events()),
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )

    assert stale.reason_code == "state_revision_conflict"
    assert restored.accepted is True


def test_projector_rejects_resource_boundary_and_unordered_body_events() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    _append(
        store,
        command_id="cmd:overdraw",
        stream_id=RESOURCE_STREAM,
        event_type="gameplay.resource.adjusted",
        payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "delta": -8, "reason_ref": "test"},
    )
    with pytest.raises(ResourceBodyRuntimeError, match="resource_boundary_violation"):
        ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events())

    store = GameplayEventStore()
    _append(
        store,
        command_id="cmd:recover:missing",
        stream_id=BODY_STREAM,
        event_type="gameplay.body.injury_recovered",
        payload={"actor_ref": ACTOR, "injury_id": "injury:missing"},
    )
    with pytest.raises(ResourceBodyRuntimeError, match="injury_recover_before_apply"):
        ResourceBodyRuntimeProjector().rebuild_body(ACTOR, store.read_events())


def test_resource_owner_durable_reopen_full_and_checkpoint_tail_match(tmp_path) -> None:
    """The admitted resource owner must survive a real store restart and replay cut."""
    path = tmp_path / "resource-owner.sqlite3"
    store = DurableGameplayEventStore(path)
    _materialize_stamina(store, 7)
    projector = ResourceBodyRuntimeProjector()
    checkpoint = projector.rebuild_resources(ACTOR, store.read_events())
    action = ResourceBodyActionSettlementService(store=store).settle(
        _command("cmd:slash:durable"),
        resources=checkpoint,
        body=projector.rebuild_body(ACTOR, store.read_events()),
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )
    assert action.accepted is True
    receipt = store.get_by_idempotency("resource_body_action_authority", f"{ACTOR}:cmd:slash:durable")
    assert receipt is not None and receipt.committed is True
    before_restart = store.read_events()
    store.close()

    reopened = DurableGameplayEventStore(path)
    full = projector.rebuild_resources(ACTOR, reopened.read_events())
    checkpoint_last_global_sequence = max(
        event.global_sequence
        for event in reopened.read_events()
        if event.stream_id == RESOURCE_STREAM
        and event.global_sequence <= checkpoint.source_revision_vector.get(RESOURCE_STREAM, 0)
    )
    tail = projector.rebuild_resources(
        ACTOR,
        reopened.read_events(global_sequence_after=checkpoint_last_global_sequence),
        checkpoint=checkpoint,
    )
    assert full == tail
    assert full.entries["core.stamina"].current == 4
    assert len(reopened.read_events()) == len(before_restart)
    replayed_receipt = reopened.get_by_idempotency("resource_body_action_authority", f"{ACTOR}:cmd:slash:durable")
    assert replayed_receipt is not None and replayed_receipt.committed_event_ids == receipt.committed_event_ids
    reopened.close()


def test_resource_body_action_replays_exact_receipt_after_restart_and_rejects_changed_duplicate(tmp_path) -> None:
    path = tmp_path / "resource-action-receipt.sqlite3"
    store = DurableGameplayEventStore(path)
    _materialize_stamina(store, 7)
    projector = ResourceBodyRuntimeProjector()
    command = _command("cmd:slash:lost-response")
    initial_resources = projector.rebuild_resources(ACTOR, store.read_events())
    initial_body = projector.rebuild_body(ACTOR, store.read_events())
    first = ResourceBodyActionSettlementService(store=store).settle(
        command, resources=initial_resources, body=initial_body,
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )
    assert first.accepted and first.append_result is not None
    store.close()

    reopened = DurableGameplayEventStore(path)
    current_resources = projector.rebuild_resources(ACTOR, reopened.read_events())
    current_body = projector.rebuild_body(ACTOR, reopened.read_events())
    retry = ResourceBodyActionSettlementService(store=reopened).settle(
        command, resources=current_resources, body=current_body,
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )
    assert retry.accepted and retry.append_result is not None
    assert retry.append_result.committed_event_ids == first.append_result.committed_event_ids
    assert retry.append_result.idempotency_status == "duplicate_replayed"
    changed = command.model_copy(update={
        "requirement": command.requirement.model_copy(update={"stamina_cost": 4})
    })
    before = reopened.export_snapshot()
    rejected = ResourceBodyActionSettlementService(store=reopened).settle(
        changed, resources=current_resources, body=current_body,
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )
    assert not rejected.accepted and rejected.reason_code == "idempotency_key_reused"
    assert reopened.export_snapshot() == before
    reopened.close()


def test_reservation_reduces_available_then_consumes_or_releases_without_ghost_balance() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    _append(store, command_id="cmd:reserve", stream_id=RESOURCE_STREAM, event_type="gameplay.resource.reservation_created", payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "reservation_ref": "reservation:slash", "amount": 3})
    projector = ResourceBodyRuntimeProjector()
    reserved = projector.rebuild_resources(ACTOR, store.read_events()).entries["core.stamina"]
    assert (reserved.current, reserved.reserved, reserved.available) == (7, 3, 4)

    _append(store, command_id="cmd:release", stream_id=RESOURCE_STREAM, event_type="gameplay.resource.reservation_released", payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "reservation_ref": "reservation:slash"})
    released = projector.rebuild_resources(ACTOR, store.read_events()).entries["core.stamina"]
    assert (released.current, released.reserved, released.available) == (7, 0, 7)

    _append(store, command_id="cmd:reserve:consume", stream_id=RESOURCE_STREAM, event_type="gameplay.resource.reservation_created", payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "reservation_ref": "reservation:consume", "amount": 2})
    _append(store, command_id="cmd:consume", stream_id=RESOURCE_STREAM, event_type="gameplay.resource.reservation_consumed", payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "reservation_ref": "reservation:consume"})
    consumed = projector.rebuild_resources(ACTOR, store.read_events()).entries["core.stamina"]
    assert (consumed.current, consumed.reserved, consumed.available) == (5, 0, 5)


def test_reservation_authority_writes_once_and_rejects_insufficient_balance() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 3)
    projector = ResourceBodyRuntimeProjector()
    command = ResourceReservationCommand(command_id="cmd:reserve:authority", actor_ref=ACTOR, authority_principal="gameplay_authority", idempotency_key="reserve:authority", payload_digest="sha256:reserve:authority", causation_id="cmd:reserve:authority", correlation_id="corr:reservation", operation="reserve", resource_id="core.stamina", reservation_ref="reservation:authority", amount=2)
    service = ResourceReservationAuthorityService(store=store)

    assert service.apply(command, projector.rebuild_resources(ACTOR, store.read_events())).committed
    assert service.apply(command, projector.rebuild_resources(ACTOR, store.read_events())).idempotency_status == "duplicate_replayed"
    reserved = projector.rebuild_resources(ACTOR, store.read_events())
    assert (reserved.entries["core.stamina"].reserved, reserved.entries["core.stamina"].available) == (2, 1)
    with pytest.raises(ValueError, match="resource_insufficient"):
        service.apply(
            ResourceReservationCommand(command_id="cmd:reserve:too-much", actor_ref=ACTOR, authority_principal="gameplay_authority", idempotency_key="reserve:too-much", payload_digest="sha256:reserve:too-much", causation_id="cmd:reserve:too-much", correlation_id="corr:reservation", operation="reserve", resource_id="core.stamina", reservation_ref="reservation:too-much", amount=2),
            reserved,
        )
    consumed = service.apply(
        ResourceReservationCommand(command_id="cmd:consume:authority", actor_ref=ACTOR, authority_principal="gameplay_authority", idempotency_key="consume:authority", payload_digest="sha256:consume:authority", causation_id="cmd:consume:authority", correlation_id="corr:reservation", operation="consume", resource_id="core.stamina", reservation_ref="reservation:authority"),
        reserved,
    )
    assert consumed.committed
    final = projector.rebuild_resources(ACTOR, store.read_events()).entries["core.stamina"]
    assert (final.current, final.reserved, final.available) == (1, 0, 1)


def test_reservation_authority_rejects_unknown_or_wrong_resource_release_before_write() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 3)
    projector = ResourceBodyRuntimeProjector()
    service = ResourceReservationAuthorityService(store=store)
    current = projector.rebuild_resources(ACTOR, store.read_events())

    unknown = ResourceReservationCommand(
        command_id="cmd:release:unknown", actor_ref=ACTOR,
        authority_principal="gameplay_authority", idempotency_key="release:unknown",
        payload_digest="sha256:release:unknown", causation_id="cause:release:unknown",
        correlation_id="corr:reservation", operation="release", resource_id="core.stamina",
        reservation_ref="reservation:missing",
    )
    before = len(store.read_events())
    with pytest.raises(ValueError, match="resource_reservation_unknown"):
        service.apply(unknown, current)
    assert len(store.read_events()) == before

    _append(store, command_id="cmd:reserve:wrong-resource", stream_id=RESOURCE_STREAM,
            event_type="gameplay.resource.reservation_created",
            payload={"actor_ref": ACTOR, "resource_id": "core.stamina",
                     "reservation_ref": "reservation:owned", "amount": 1})
    _materialize_mana(store, 3)
    current = projector.rebuild_resources(ACTOR, store.read_events())
    wrong_resource = unknown.model_copy(update={
        "command_id": "cmd:release:wrong-resource",
        "idempotency_key": "release:wrong-resource",
        "payload_digest": "sha256:release:wrong-resource",
        "causation_id": "cause:release:wrong-resource",
        "resource_id": "core.mana",
        "reservation_ref": "reservation:owned",
    })
    before = len(store.read_events())
    with pytest.raises(ValueError, match="resource_reservation_unknown"):
        service.apply(wrong_resource, current)
    assert len(store.read_events()) == before


def test_character_template_materialization_uses_real_profile_source_and_writes_all_resources() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    caller = CharacterResourceMaterializationCaller(
        authority=ResourceMaterializationAuthorityService(store=store, registry=registry),
    )
    result = caller.materialize(
        actor_ref=MATERIALIZATION_ACTOR,
        world_ref="world:bakery",
        timeline_ref="timeline:main",
        world_tick=0,
        idempotency_key="resource-materialize:char_a:1",
        expected_revision=0,
    )
    assert result.committed
    events = store.read_stream(MATERIALIZATION_RESOURCE_STREAM)
    assert [event.payload["resource_id"] for event in events] == [
        "core.stamina", "core.mana", "core.action_points"
    ]
    assert all(event.payload["template_ref"] == "character-template:char_a" for event in events)
    assert all(event.visibility_policy == "authority_only" for event in events)
    projection = ResourceBodyRuntimeProjector().rebuild_resources(MATERIALIZATION_ACTOR, store.read_events())
    assert set(projection.entries) == {"core.stamina", "core.mana", "core.action_points"}
    before_duplicate = store.export_snapshot()
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        caller.materialize(
            actor_ref=MATERIALIZATION_ACTOR,
            world_ref="world:bakery",
            timeline_ref="timeline:main",
            world_tick=1,
            idempotency_key="resource-materialize:char_a:1",
            expected_revision=3,
        )
    assert store.export_snapshot() == before_duplicate


def test_character_template_materialization_rejects_changed_source_and_replays_after_durable_reopen(tmp_path) -> None:
    path = tmp_path / "resource-materialization.sqlite3"
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    store = DurableGameplayEventStore(path)
    authority = ResourceMaterializationAuthorityService(store=store, registry=registry)
    caller = CharacterResourceMaterializationCaller(authority=authority)
    first = caller.materialize(
        actor_ref=MATERIALIZATION_ACTOR, world_ref="world:bakery", timeline_ref="timeline:main", world_tick=0,
        idempotency_key="resource-materialize:char_a:durable", expected_revision=0,
    )
    assert first.committed
    source = registry.resource_template_source(MATERIALIZATION_ACTOR, world_ref="world:bakery", timeline_ref="timeline:main")
    changed = source.model_copy(update={"binding_revision": "binding:changed@1"})
    with pytest.raises(ValueError, match="resource_template_source_changed"):
        authority.materialize(
            actor_ref=MATERIALIZATION_ACTOR, world_ref="world:bakery", timeline_ref="timeline:main", world_tick=0,
            source=changed, expected_revision=3,
            idempotency_key="resource-materialize:char_a:changed",
        )
    store.close()
    reopened = DurableGameplayEventStore(path)
    retry = ResourceMaterializationAuthorityService(store=reopened, registry=registry).materialize(
        actor_ref=MATERIALIZATION_ACTOR, world_ref="world:bakery", timeline_ref="timeline:main", world_tick=0,
        source=source, expected_revision=3,
        idempotency_key="resource-materialize:char_a:durable",
    )
    assert retry.committed and retry.idempotency_status == "duplicate_replayed"
    assert len(reopened.read_stream(MATERIALIZATION_RESOURCE_STREAM)) == 3
    reopened.close()


def test_reservation_replays_durable_receipt_before_revision_check_and_rejects_changed_input(tmp_path) -> None:
    path = tmp_path / "resource-reservation-receipt.sqlite3"
    store = DurableGameplayEventStore(path)
    _materialize_stamina(store, 6)
    projector = ResourceBodyRuntimeProjector()
    command = ResourceReservationCommand(command_id="cmd:reserve:retry", actor_ref=ACTOR,
        authority_principal="gameplay_authority", idempotency_key="reserve:retry",
        payload_digest="sha256:caller-claimed-digest", causation_id="cause:reserve:retry",
        correlation_id="corr:reserve:retry", operation="reserve", resource_id="core.stamina",
        reservation_ref="reservation:retry", amount=2)
    first = ResourceReservationAuthorityService(store=store).apply(
        command, projector.rebuild_resources(ACTOR, store.read_events()))
    assert first.committed
    store.close()

    reopened = DurableGameplayEventStore(path)
    current = projector.rebuild_resources(ACTOR, reopened.read_events())
    retry = ResourceReservationAuthorityService(store=reopened).apply(command, current)
    assert retry.committed and retry.idempotency_status == "duplicate_replayed"
    assert retry.committed_event_ids == first.committed_event_ids
    changed = command.model_copy(update={"amount": 3})
    before = reopened.export_snapshot()
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        ResourceReservationAuthorityService(store=reopened).apply(changed, current)
    assert reopened.export_snapshot() == before
    reopened.close()


def test_reservation_changed_causation_and_correlation_cannot_reuse_receipt() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 6)
    projector = ResourceBodyRuntimeProjector()
    command = ResourceReservationCommand(
        command_id="cmd:reserve:causal", actor_ref=ACTOR, authority_principal="gameplay_authority",
        idempotency_key="reserve:causal", payload_digest="sha256:caller", causation_id="cause:one",
        correlation_id="corr:one", operation="reserve", resource_id="core.stamina",
        reservation_ref="reservation:causal", amount=2,
    )
    service = ResourceReservationAuthorityService(store=store)
    current = projector.rebuild_resources(ACTOR, store.read_events())
    assert service.apply(command, current).committed
    changed = command.model_copy(update={"causation_id": "cause:changed", "correlation_id": "corr:changed"})
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        service.apply(changed, current)


def test_action_changed_causation_and_correlation_cannot_reuse_receipt() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    projector = ResourceBodyRuntimeProjector()
    command = _command("cmd:action:causal")
    service = ResourceBodyActionSettlementService(store=store)
    resources = projector.rebuild_resources(ACTOR, store.read_events())
    body = projector.rebuild_body(ACTOR, store.read_events())
    first = service.settle(command, resources=resources, body=body, enabled_group_ids=("core.resources", "core.body_runtime"))
    assert first.accepted
    changed = command.model_copy(update={"causation_id": "cause:changed", "correlation_id": "corr:changed"})
    rejected = service.settle(changed, resources=resources, body=body, enabled_group_ids=("core.resources", "core.body_runtime"))
    assert not rejected.accepted and rejected.reason_code == "idempotency_key_reused"


def test_resource_checkpoint_plus_tail_rebuild_matches_full_projection() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    _append(store, command_id="cmd:checkpoint:reserve", stream_id=RESOURCE_STREAM, event_type="gameplay.resource.reservation_created", payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "reservation_ref": "reservation:checkpoint", "amount": 2})
    _append(store, command_id="cmd:checkpoint:consume", stream_id=RESOURCE_STREAM, event_type="gameplay.resource.reservation_consumed", payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "reservation_ref": "reservation:checkpoint"})
    events = store.read_events()
    projector = ResourceBodyRuntimeProjector()

    full = projector.rebuild_resources(ACTOR, events)
    checkpoint = projector.rebuild_resources(ACTOR, events[:1])
    checkpointed = projector.rebuild_resources(ACTOR, events[1:], checkpoint=checkpoint)

    assert checkpointed.entries == full.entries
    assert checkpointed.reservations == full.reservations == {}
    assert checkpointed.source_revision_vector == full.source_revision_vector


def test_body_checkpoint_plus_tail_rebuild_matches_full_projection() -> None:
    store = GameplayEventStore()
    _append(store, command_id="cmd:checkpoint:injury", stream_id=BODY_STREAM, event_type="gameplay.body.injury_applied", payload={"actor_ref": ACTOR, "injury_id": "injury:right", "function_id": "grip.right", "capacity_ratio": 0})
    _append(store, command_id="cmd:checkpoint:recover", stream_id=BODY_STREAM, event_type="gameplay.body.injury_recovered", payload={"actor_ref": ACTOR, "injury_id": "injury:right"})
    events = store.read_events()
    projector = ResourceBodyRuntimeProjector()

    full = projector.rebuild_body(ACTOR, events)
    checkpointed = projector.rebuild_body(ACTOR, events[1:], checkpoint=projector.rebuild_body(ACTOR, events[:1]))

    assert checkpointed.injuries == full.injuries == {}
    assert checkpointed.functions == full.functions == {}
    assert checkpointed.source_revision_vector == full.source_revision_vector


def test_resource_bounds_migration_is_typed_replayable_and_checkpoint_safe() -> None:
    store = GameplayEventStore()
    definitions = _migration_definitions()
    _materialize_versioned_stamina(store, 8)
    projector = ResourceBodyRuntimeProjector(resource_definitions=definitions)
    before = projector.rebuild_resources(ACTOR, store.read_events())
    plan = ResourceBoundsMigrationAuthorityService(definitions=definitions).plan(_migration_request(before.projection_revision), before)

    assert plan.expected_stream_revision == 1
    assert plan.payload["previous_current"] == 8
    assert plan.payload["next_current"] == 6
    assert plan.payload["lost_amount"] == 2
    _append(
        store,
        command_id="cmd:migrate:stamina-bounds",
        stream_id=RESOURCE_STREAM,
        event_type=plan.event_type,
        payload=dict(plan.payload),
    )

    events = store.read_events()
    full = projector.rebuild_resources(ACTOR, events)
    checkpointed = projector.rebuild_resources(ACTOR, events[1:], checkpoint=projector.rebuild_resources(ACTOR, events[:1]))
    entry = full.entries["core.stamina"]
    assert (entry.definition_version, entry.current, entry.minimum, entry.maximum, entry.reserved) == ("2.0.0", 6, 0, 6, 0)
    assert checkpointed == full


def test_resource_bounds_migration_rejects_reservations_and_tampered_replay() -> None:
    store = GameplayEventStore()
    definitions = _migration_definitions()
    _materialize_versioned_stamina(store, 8)
    projector = ResourceBodyRuntimeProjector(resource_definitions=definitions)
    before = projector.rebuild_resources(ACTOR, store.read_events())
    _append(
        store,
        command_id="cmd:reserve:migration",
        stream_id=RESOURCE_STREAM,
        event_type="gameplay.resource.reservation_created",
        payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "reservation_ref": "reservation:migration", "amount": 1},
    )
    reserved = projector.rebuild_resources(ACTOR, store.read_events())
    with pytest.raises(ResourceBodyRuntimeError, match="reservations_present"):
        ResourceBoundsMigrationAuthorityService(definitions=definitions).plan(_migration_request(reserved.projection_revision), reserved)

    plan = ResourceBoundsMigrationAuthorityService(definitions=definitions).plan(_migration_request(before.projection_revision), before)
    _append(store, command_id="cmd:migrate:valid", stream_id=RESOURCE_STREAM, event_type=plan.event_type, payload=dict(plan.payload))
    tampered = store.read_events()[-1].model_copy(
        update={"event_id": "evt:migrate:tampered", "stream_revision": 3, "global_sequence": 3, "payload": {**plan.payload, "lost_amount": 0}},
        deep=True,
    )
    with pytest.raises(ResourceBodyRuntimeError, match="migration_policy_invalid"):
        projector.rebuild_resources(ACTOR, [store.read_events()[0], tampered])

def test_reservation_duplicate_rejects_changed_claimed_payload_digest() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 6)
    projector = ResourceBodyRuntimeProjector()
    command = ResourceReservationCommand(command_id="cmd:reserve:digest", actor_ref=ACTOR,
        authority_principal="gameplay_authority", idempotency_key="reserve:digest",
        payload_digest="sha256:caller", causation_id="cause:reserve:digest",
        correlation_id="corr:reserve:digest", operation="reserve", resource_id="core.stamina",
        reservation_ref="reservation:digest", amount=2)
    service = ResourceReservationAuthorityService(store=store)
    current = projector.rebuild_resources(ACTOR, store.read_events())
    assert service.apply(command, current).committed
    before = store.export_snapshot()
    changed = command.model_copy(update={"payload_digest": "sha256:tampered"})
    with pytest.raises(ValueError, match="idempotency_key_reused"):
        service.apply(changed, current)
    assert store.export_snapshot() == before


@pytest.mark.parametrize("corruption", ["event", "result", "transaction"])
def test_reservation_duplicate_rejects_corrupt_persisted_receipt(monkeypatch, corruption) -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 6)
    projector = ResourceBodyRuntimeProjector()
    command = ResourceReservationCommand(command_id="cmd:reserve:corrupt", actor_ref=ACTOR,
        authority_principal="gameplay_authority", idempotency_key="reserve:corrupt",
        payload_digest="sha256:caller", causation_id="cause:reserve:corrupt",
        correlation_id="corr:reserve:corrupt", operation="reserve", resource_id="core.stamina",
        reservation_ref="reservation:corrupt", amount=2)
    service = ResourceReservationAuthorityService(store=store)
    current = projector.rebuild_resources(ACTOR, store.read_events())
    first = service.apply(command, current)
    assert first.committed
    before = store.export_snapshot()
    if corruption == "result":
        damaged = first.model_copy(update={"committed_event_ids": []}, deep=True)
        monkeypatch.setattr(store, "get_by_idempotency", lambda *args: damaged)
    elif corruption == "transaction":
        monkeypatch.setattr(store, "get_transaction", lambda *args: None)
    else:
        transaction = store.get_transaction(first.transaction_id)
        event = transaction.events[0].model_copy(update={"visibility_policy": "project"}, deep=True)
        damaged = transaction.model_copy(update={"events": [event]}, deep=True)
        monkeypatch.setattr(store, "get_transaction", lambda *args: damaged)
    with pytest.raises(ValueError, match="resource_reservation_receipt_incomplete"):
        service.apply(command, current)
    assert store.export_snapshot() == before


@pytest.mark.parametrize("corruption", ["changed_digest", "missing_event", "failed_receipt", "transaction_digest"])
def test_action_receipt_requires_original_complete_transaction(monkeypatch, corruption):
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    projector = ResourceBodyRuntimeProjector()
    command = _command("cmd:receipt-integrity")
    resources, body = projector.rebuild_resources(ACTOR, store.read_events()), projector.rebuild_body(ACTOR, store.read_events())
    owner = ResourceBodyActionSettlementService(store=store)
    first = owner.settle(command, resources=resources, body=body, enabled_group_ids=("core.resources", "core.body_runtime"))
    assert first.accepted
    if corruption == "changed_digest":
        command = command.model_copy(update={"payload_digest": "changed"})
    elif corruption in {"missing_event", "failed_receipt"}:
        receipt = first.append_result.model_copy(update={"committed_event_ids": first.append_result.committed_event_ids[1:]} if corruption == "missing_event" else {"committed": False})
        monkeypatch.setattr(store, "get_by_idempotency", lambda *args: receipt)
    else:
        transaction = store.get_transaction(first.append_result.transaction_id)
        monkeypatch.setattr(store, "get_transaction", lambda *args: transaction.model_copy(update={"result_digest": "damaged"}))
    result = owner.settle(command, resources=resources, body=body, enabled_group_ids=("core.resources", "core.body_runtime"))
    assert not result.accepted


def test_action_settlement_keeps_validated_resource_read_set(monkeypatch):
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    projector = ResourceBodyRuntimeProjector()
    resources, body = projector.rebuild_resources(ACTOR, store.read_events()), projector.rebuild_body(ACTOR, store.read_events())
    original = store.get_stream_head
    injected = False
    def racing_head(stream):
        nonlocal injected
        if stream == BODY_STREAM and not injected:
            injected = True
            _append(store, command_id="concurrent", stream_id=RESOURCE_STREAM, event_type="gameplay.resource.adjusted", payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "delta": -1})
        return original(stream)
    monkeypatch.setattr(store, "get_stream_head", racing_head)
    result = ResourceBodyActionSettlementService(store=store).settle(_command("race"), resources=resources, body=body, enabled_group_ids=("core.resources", "core.body_runtime"))
    assert not result.accepted


def test_v2_genesis_rejects_maximum_above_capacity():
    store = GameplayEventStore()
    _append(store, command_id="bad-capacity", stream_id=RESOURCE_STREAM, event_type="gameplay.resource.materialized", payload={"actor_ref": ACTOR, "resource_id": "core.stamina", "definition_version": "v2", "minimum": 0, "maximum": 10, "current": 1, "resource_schema": "resource.v2", "capacity": 5, "base_capacity": 5, "locked": 0, "debt": 0, "debt_ceiling": 0, "modifier_ledger": [], "modifier_ledger_digest": "sha256:"+sha256(b"[]").hexdigest()})
    with pytest.raises(ResourceBodyRuntimeError, match="resource_v2_materialization_invalid"):
        ResourceBodyRuntimeProjector().rebuild_resources(ACTOR, store.read_events())


def test_action_receipt_preserves_strict_legacy_head_contract(monkeypatch):
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    command = _command("legacy-head")
    projector = ResourceBodyRuntimeProjector()
    resources, body = projector.rebuild_resources(ACTOR, store.read_events()), projector.rebuild_body(ACTOR, store.read_events())
    append = store.append_batch
    def legacy_append(batch):
        batch = dict(batch)
        batch.pop("read_stream_revisions")
        batch["idempotency_record"] = dict(batch["idempotency_record"], payload_digest=command.payload_digest)
        batch["events"][1]["payload"].pop("request_digest_version")
        return append(batch)
    monkeypatch.setattr(store, "append_batch", legacy_append)
    owner = ResourceBodyActionSettlementService(store=store)
    first = owner.settle(command, resources=resources, body=body, enabled_group_ids=("core.resources", "core.body_runtime"))
    assert first.accepted
    retry = owner.settle(command, resources=resources, body=body, enabled_group_ids=())
    assert retry.accepted and retry.append_result.committed_event_ids == first.append_result.committed_event_ids
    changed = owner.settle(command.model_copy(update={"payload_digest": "different"}), resources=resources, body=body, enabled_group_ids=())
    assert not changed.accepted


def test_modern_action_receipt_cannot_use_legacy_digest_escape():
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    command = _command("modern-digest")
    projector = ResourceBodyRuntimeProjector()
    resources, body = projector.rebuild_resources(ACTOR, store.read_events()), projector.rebuild_body(ACTOR, store.read_events())
    owner = ResourceBodyActionSettlementService(store=store)
    first = owner.settle(command, resources=resources, body=body, enabled_group_ids=("core.resources", "core.body_runtime"))
    digest = store.get_transaction(first.append_result.transaction_id).idempotency_record.payload_digest
    retry = owner.settle(command.model_copy(update={"payload_digest": digest}), resources=resources, body=body, enabled_group_ids=())
    assert not retry.accepted
