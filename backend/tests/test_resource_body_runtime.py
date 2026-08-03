from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
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


ACTOR = "actor:char_a"
RESOURCE_STREAM = f"gameplay:resources:{ACTOR}"
BODY_STREAM = f"gameplay:body:{ACTOR}"


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
        authority_principal="gameplay_authority",
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
    assert service.apply(command, projector.rebuild_resources(ACTOR, store.read_events())).idempotency_status == "new_commit"
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
