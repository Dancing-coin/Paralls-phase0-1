"""Read-only participant capture for admitted settlement and custody paths.

The caller owns the serialized execution boundary. This module does not retry
commands, finish migrations, dispatch work, or obtain domain write authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from fractions import Fraction

from .batch_settlement import _digest


_ECONOMY_TEMPORAL_EVENT_TYPES = frozenset({
    "gameplay.economy.scheduled_transfer_obligation_opened",
    "gameplay.economy.scheduled_transfer_obligation_settled",
    "gameplay.economy.scheduled_transfer_obligation_cancelled",
    "gameplay.economy.scheduled_transfer_obligation_expired",
    "gameplay.economy.tax_due_recorded",
    "gameplay.economy.tax_obligation_opened",
    "gameplay.economy.tax_obligation_settled",
    "gameplay.economy.tax_obligation_cancelled",
    "gameplay.economy.tax_obligation_expired",
})

_ECONOMY_RANDOM_EVENT_TYPES = frozenset({
    "gameplay.economy.random_entropy_anchor_created@1",
    "gameplay.economy.random_result_committed@1",
})

_ECOLOGY_TEMPORAL_EVENT_TYPES = frozenset({
    "gameplay.ecology.crop_state_obligation_opened",
    "gameplay.ecology.crop_state_obligation_settled",
    "gameplay.ecology.crop_state_obligation_cancelled",
    "gameplay.ecology.crop_state_expired",
    "gameplay.ecology.drought_process_advanced",
    "gameplay.ecology.drought_state_applied",
    "gameplay.ecology.drought_state_obligation_opened",
    "gameplay.ecology.drought_state_obligation_settled",
    "gameplay.ecology.drought_state_expired",
})

_RESOURCE_EVENT_TYPES = frozenset({
    "gameplay.resource.materialized", "gameplay.resource.adjusted", "gameplay.resource.recovered",
    "gameplay.resource.converted", "gameplay.resource.bounds_migrated",
    "gameplay.resource.reservation_created", "gameplay.resource.reservation_consumed",
    "gameplay.resource.reservation_released", "gameplay.resource.lock_created",
    "gameplay.resource.lock_consumed", "gameplay.resource.lock_released",
    "gameplay.resource.modifier_attached", "gameplay.resource.modifier_detached",
})

_EQUIPMENT_EVENT_TYPES = frozenset({
    "gameplay.equipment.activation_started", "gameplay.equipment.activation_ended",
})

_LIFE_STATE_EVENT = "gameplay.character.life_state_changed"

_INVENTORY_EVENT_TYPES = frozenset({
    "gameplay.inventory.container_created", "gameplay.inventory.item_instantiated",
    "gameplay.inventory.mill_flour_output_received@1", "gameplay.inventory.harvest_received@1",
    "gameplay.inventory.grain_harvest_received@1", "gameplay.inventory.production_output_received@1",
    "gameplay.inventory.output_received", "gameplay.inventory.item_moved",
    "gameplay.inventory.item_transferred_out", "gameplay.inventory.item_transferred_in",
    "gameplay.inventory.item_equipped", "gameplay.inventory.item_unequipped",
    "gameplay.inventory.reservation_created", "gameplay.inventory.reservation_consumed",
    "gameplay.inventory.reservation_released", "gameplay.inventory.commerce_capacity_reserved",
    "gameplay.inventory.commerce_capacity_released",
    "gameplay.inventory.custody_reserved_for_commerce", "gameplay.inventory.delivery_committed",
    "gameplay.inventory.delivery_rejected", "gameplay.inventory.delivery_cancelled",
})


def _ecology_temporal_events(store, *, boundary_sequence=None):
    """Select only the two Population-admitted Ecology expiry lifecycles."""
    return [
        event for event in store.read_events()
        if event.event_type in _ECOLOGY_TEMPORAL_EVENT_TYPES
        and (boundary_sequence is None or event.global_sequence <= boundary_sequence)
    ]


def _ecology_temporal_participant(store, *, boundary_sequence=None):
    """Capture registered frost/drought lifecycle facts for replay."""
    from app.world_runtime.obligations import (
        ObligationLifecycleContractRegistry,
        ObligationLifecycleProjection,
    )

    events = _ecology_temporal_events(store, boundary_sequence=boundary_sequence)
    policy_refs = {
        "policy:ecology_frost_crop_state_expiry@1",
        "policy:ecology_drought_state_expiry@1",
    }
    registrations = tuple(
        registration for registration in ObligationLifecycleContractRegistry.closed_registrations()
        if registration.policy_ref in policy_refs
    )
    view = ObligationLifecycleProjection(registrations).rebuild(events)
    state = dict(open=_json(view.open), terminal=_json(view.terminal),
                 source_revision_vector=_json(view.source_revision_vector))
    refs = [dict(
        event_id=event.event_id,
        global_sequence=event.global_sequence,
        stream_id=event.stream_id,
        stream_revision=event.stream_revision,
        transaction_id=event.transaction_id,
        event_type=event.event_type,
        payload_digest=_digest(_json(event.payload)),
    ) for event in events]
    return dict(
        schema_version=1,
        scope="project:ecology-temporal",
        owner_ref="authority:ecology",
        policy_refs=sorted(policy_refs),
        event_refs=refs,
        state=state,
        view_digest=_digest(state),
        reconstruction_api="ObligationLifecycleProjection.rebuild",
    )


def _validate_ecology_temporal_participant(store, saved, *, boundary_sequence=None):
    """Validate the Ecology lifecycle scope against the bounded event cut."""
    bounded = _ecology_temporal_events(store, boundary_sequence=boundary_sequence)
    if saved is None:
        if bounded:
            raise ValueError("replay_ecology_temporal_participant_scope_mismatch")
        return
    if saved.get("schema_version") != 1:
        raise ValueError("replay_decoder_unsupported")
    if (saved.get("scope") != "project:ecology-temporal"
            or saved.get("owner_ref") != "authority:ecology"
            or saved.get("policy_refs") != [
                "policy:ecology_drought_state_expiry@1",
                "policy:ecology_frost_crop_state_expiry@1",
            ]
            or saved.get("reconstruction_api") != "ObligationLifecycleProjection.rebuild"):
        raise ValueError("replay_saved_ecology_temporal_scope_mismatch")
    expected = _ecology_temporal_participant(store, boundary_sequence=boundary_sequence)
    if expected is None:
        raise ValueError("replay_saved_ecology_temporal_projection_mismatch")
    if saved.get("event_refs") != expected["event_refs"]:
        raise ValueError("replay_saved_ecology_temporal_event_ref_mismatch")
    if saved.get("state") != expected["state"] or saved.get("view_digest") != expected["view_digest"]:
        raise ValueError("replay_saved_ecology_temporal_projection_mismatch")


def _economy_temporal_events(store, *, boundary_sequence=None):
    """Select the admitted temporal Economy facts and their atomic side effects.

    The lifecycle records and account debits/credits are one owner transaction.
    Selecting by transaction preserves the actual settlement without admitting
    unrelated Economy commerce, wage, or policy events into this participant.
    """
    all_events = list(store.read_events())
    bounded = [event for event in all_events
               if boundary_sequence is None or event.global_sequence <= boundary_sequence]
    lifecycle = [event for event in bounded if event.event_type in _ECONOMY_TEMPORAL_EVENT_TYPES]
    transaction_ids = {event.transaction_id for event in lifecycle}
    selected = [event for event in bounded
                if event.event_type in _ECONOMY_TEMPORAL_EVENT_TYPES
                or event.transaction_id in transaction_ids and event.stream_id == "gameplay:economy"
                and event.event_type in {"gameplay.economy.account_debited", "gameplay.economy.account_credited"}]
    return sorted({event.event_id: event for event in selected}.values(),
                  key=lambda event: (event.global_sequence, event.event_id))


def _economy_temporal_participant(store, *, boundary_sequence=None):
    """Capture the two registered Economy temporal policies as a replay scope."""
    from app.world_runtime.obligations import (
        ObligationLifecycleContractRegistry,
        ObligationLifecycleProjection,
    )

    events = _economy_temporal_events(store, boundary_sequence=boundary_sequence)
    policy_refs = {
        "policy:economy_scheduled_account_transfer@1",
        "policy:economy_tax_due@1",
    }
    registrations = tuple(
        registration for registration in ObligationLifecycleContractRegistry.closed_registrations()
        if registration.policy_ref in policy_refs
    )
    view = ObligationLifecycleProjection(registrations).rebuild(events)
    revisions = dict(view.source_revision_vector)
    event_refs = [dict(
        event_id=event.event_id,
        global_sequence=event.global_sequence,
        stream_id=event.stream_id,
        stream_revision=event.stream_revision,
        transaction_id=event.transaction_id,
        event_type=event.event_type,
        payload_digest=_digest(_json(event.payload)),
    ) for event in events]
    state = dict(open=_json(view.open), terminal=_json(view.terminal),
                 source_revision_vector=_json(revisions))
    return dict(
        schema_version=1,
        scope="project:economy-temporal",
        owner_ref="actor_gameplay.economy_domain",
        policy_refs=sorted(policy_refs),
        event_refs=event_refs,
        state=state,
        view_digest=_digest(state),
        reconstruction_api="ObligationLifecycleProjection.rebuild",
    )


def _validate_economy_temporal_participant(store, saved, *, boundary_sequence=None):
    """Validate a saved Economy temporal scope against bounded durable facts."""
    bounded_events = _economy_temporal_events(store, boundary_sequence=boundary_sequence)
    if saved is None:
        if bounded_events:
            raise ValueError("replay_economy_temporal_participant_scope_mismatch")
        return
    if saved.get("schema_version") != 1:
        raise ValueError("replay_decoder_unsupported")
    if (saved.get("scope") != "project:economy-temporal"
            or saved.get("owner_ref") != "actor_gameplay.economy_domain"
            or saved.get("policy_refs") != [
                "policy:economy_scheduled_account_transfer@1", "policy:economy_tax_due@1"
            ]
            or saved.get("reconstruction_api") != "ObligationLifecycleProjection.rebuild"):
        raise ValueError("replay_saved_economy_temporal_scope_mismatch")
    expected_refs = [dict(
        event_id=event.event_id,
        global_sequence=event.global_sequence,
        stream_id=event.stream_id,
        stream_revision=event.stream_revision,
        transaction_id=event.transaction_id,
        event_type=event.event_type,
        payload_digest=_digest(_json(event.payload)),
    ) for event in bounded_events]
    if saved.get("event_refs") != expected_refs:
        raise ValueError("replay_saved_economy_temporal_event_ref_mismatch")
    expected = _economy_temporal_participant(store, boundary_sequence=boundary_sequence)
    if expected is None or saved.get("state") != expected["state"]:
        raise ValueError("replay_saved_economy_temporal_projection_mismatch")
    if saved.get("view_digest") != expected["view_digest"]:
        raise ValueError("replay_saved_economy_temporal_projection_mismatch")


def _json(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return {field.name: _json(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    if isinstance(value, Fraction):
        return str(value)
    return value


def _economy_random_participant(store, *, boundary_sequence=None):
    """Rebuild private random facts without placing their payload in the manifest."""
    from app.gameplay.economy_runtime import EconomyProjector

    events = [event for event in store.read_events()
              if event.event_type.startswith("gameplay.economy.random_")
              and (boundary_sequence is None or event.global_sequence <= boundary_sequence)]
    for event in events:
        if (event.event_type not in _ECONOMY_RANDOM_EVENT_TYPES
                or event.stream_id != "gameplay:economy" or event.schema_version != 1
                or event.visibility_policy != "authority_only"):
            raise ValueError("replay_economy_random_event_scope_invalid")
        transaction = store.get_transaction(event.transaction_id)
        if (transaction is None or transaction.idempotency_record.principal_ref != "actor_gameplay.economy_domain"
                or event not in transaction.events
                or not store.transaction_owns_event(transaction_id=event.transaction_id,
                    event_id=event.event_id, principal_ref="actor_gameplay.economy_domain")):
            raise ValueError("replay_economy_random_event_provenance_invalid")
        try:
            persisted = store.get_event(event.event_id)
        except KeyError as exc:
            raise ValueError("replay_economy_random_event_provenance_invalid") from exc
        if persisted != event:
            raise ValueError("replay_economy_random_event_provenance_invalid")
    view = EconomyProjector().rebuild(events)
    refs = [dict(event_id=event.event_id, global_sequence=event.global_sequence,
        stream_id=event.stream_id, stream_revision=event.stream_revision,
        transaction_id=event.transaction_id, event_type=event.event_type,
        event_digest=_digest(_json(event))) for event in events]
    results = {ref: _digest(_json(payload)) for ref, payload in view.random_results.items()}
    state = dict(result_digests=results, result_count=len(results), event_refs=refs)
    return dict(schema_version=1, scope="project:economy-random-private",
        owner_ref="actor_gameplay.economy_domain", **state,
        view_digest=_digest(state), reconstruction_api="EconomyProjector.rebuild")


def _validate_economy_random_participant(store, saved, *, boundary_sequence=None):
    expected = _economy_random_participant(store, boundary_sequence=boundary_sequence)
    if saved is None:
        if expected["event_refs"]:
            raise ValueError("replay_economy_random_participant_scope_mismatch")
        return
    if saved.get("schema_version") != 1:
        raise ValueError("replay_decoder_unsupported")
    if saved != expected:
        raise ValueError("replay_saved_economy_random_projection_mismatch")


def _historical_resource_definitions(store, events, *, boundary_sequence):
    from app.gameplay.resource_body_runtime import ResourceDefinition, ResourceDefinitionRegistry

    registry = ResourceDefinitionRegistry()
    registered = {}
    for event in events:
        if event.event_type != "gameplay.resource.bounds_migrated":
            continue
        snapshots = event.payload.get("definition_snapshots")
        if (not isinstance(snapshots, dict) or set(snapshots) != {"source", "target"}
                or event.payload.get("definition_snapshots_digest") != _digest(snapshots)):
            raise ValueError("resource_definition_registry_required")
        transaction = store.get_transaction(event.transaction_id)
        completed = next((item for item in transaction.events
            if item.event_type == "gameplay.resource_migration.completed"
            and item.stream_id == f"gameplay:resource-migration-control:{event.payload.get('actor_ref')}"
            and item.payload.get("migration_id") == event.payload.get("migration_id")
            and item.payload.get("request_digest") == event.payload.get("request_digest")
            and isinstance(item.payload.get("resource_ids"), list)
            and event.payload.get("resource_id") in item.payload["resource_ids"]
            and item.visibility_policy == "authority_only"
            and item.schema_version == 1
            and item.global_sequence <= boundary_sequence), None) if transaction is not None else None
        if (transaction is None or transaction.idempotency_record.principal_ref != "resource_migration_owner"
                or event.visibility_policy != "authority_only"
                or event not in transaction.events
                or not store.transaction_owns_event(transaction_id=event.transaction_id,
                    event_id=event.event_id, principal_ref="resource_migration_owner")
                or completed is None):
            raise ValueError("resource_migration_definition_provenance_invalid")
        try:
            persisted_event = store.get_event(event.event_id)
            persisted_completion = store.get_event(completed.event_id)
        except KeyError as exc:
            raise ValueError("resource_migration_definition_provenance_invalid") from exc
        if persisted_event != event or persisted_completion != completed:
            raise ValueError("resource_migration_definition_provenance_invalid")
        try:
            source = ResourceDefinition.model_validate(snapshots["source"])
            target = ResourceDefinition.model_validate(snapshots["target"])
        except (TypeError, ValueError) as exc:
            raise ValueError("resource_migration_definition_snapshot_invalid") from exc
        if (source.resource_id != event.payload.get("resource_id")
                or target.resource_id != source.resource_id
                or source.definition_version != event.payload.get("from_definition_version")
                or target.definition_version != event.payload.get("to_definition_version")):
            raise ValueError("resource_migration_definition_snapshot_invalid")
        for definition in (source, target):
            key = (definition.resource_id, definition.definition_version)
            prior = registered.get(key)
            if prior is not None and prior != definition:
                raise ValueError("resource_migration_definition_conflict")
            if prior is None:
                registry.register(definition)
                registered[key] = definition
    return registry if registered else None


def _resource_participant(store, *, boundary_sequence=None):
    """Rebuild every committed Resource actor represented at the bounded cut."""
    from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector

    events = [event for event in store.read_events()
              if (event.stream_id.startswith("gameplay:resources:") or event.event_type in _RESOURCE_EVENT_TYPES)
              and (boundary_sequence is None or event.global_sequence <= boundary_sequence)]
    grouped = {}
    refs = []
    for event in events:
        actor_ref = event.stream_id.removeprefix("gameplay:resources:")
        if (not event.stream_id.startswith("gameplay:resources:") or not actor_ref
                or event.event_type not in _RESOURCE_EVENT_TYPES
                or event.schema_version != 1
                or event.payload.get("actor_ref") != actor_ref):
            raise ValueError("replay_resource_event_scope_unsupported")
        grouped.setdefault(actor_ref, []).append(event)
        refs.append(dict(event_id=event.event_id, global_sequence=event.global_sequence,
            stream_id=event.stream_id, stream_revision=event.stream_revision,
            transaction_id=event.transaction_id, event_type=event.event_type,
            event_digest=_digest(_json(event))))
    definitions = _historical_resource_definitions(store, events,
        boundary_sequence=boundary_sequence if boundary_sequence is not None else store.get_last_global_sequence())
    projector = ResourceBodyRuntimeProjector(resource_definitions=definitions)
    actors = {}
    for actor_ref, actor_events in sorted(grouped.items()):
        projection = projector.rebuild_resources(actor_ref, actor_events)
        actors[actor_ref] = dict(entries=_json(projection.entries),
            reservations=_json(projection.reservations), locks=_json(projection.locks),
            source_revision_vector=_json(projection.source_revision_vector),
            projection_revision=projection.projection_revision,
            reconstruction_api="ResourceBodyRuntimeProjector.rebuild_resources")
    state = dict(actors=actors, event_refs=refs)
    return dict(schema_version=1, scope="project:resource-entry", event_refs=refs, actors=actors,
        view_digest=_digest(state), reconstruction_api="ResourceBodyRuntimeProjector.rebuild_resources")


def _validate_resource_participant(store, saved, *, boundary_sequence=None):
    expected = _resource_participant(store, boundary_sequence=boundary_sequence)
    if saved is None:
        if expected["event_refs"]:
            raise ValueError("replay_resource_participant_scope_mismatch")
        return
    if saved.get("schema_version") != 1:
        raise ValueError("replay_decoder_unsupported")
    for key in ("scope", "event_refs", "actors", "view_digest", "reconstruction_api"):
        if saved.get(key) != expected.get(key):
            raise ValueError("replay_saved_resource_projection_mismatch")


def validate_resource_checkpoint_tail(store, saved, current, start, end):
    """Compare Resource's own checkpoint decoder with its bounded full rebuild."""
    from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector, ResourceEntry, ResourceStateProjection

    if saved is None and current is None:
        return
    bounded_events = [event for event in store.read_events()
                      if event.stream_id.startswith("gameplay:resources:") and event.global_sequence <= end]
    definitions = _historical_resource_definitions(store, bounded_events, boundary_sequence=end)
    projector = ResourceBodyRuntimeProjector(resource_definitions=definitions)
    actors = current["actors"] if current is not None else {}
    for actor_ref, expected in actors.items():
        events = [event for event in store.read_stream(f"gameplay:resources:{actor_ref}")
                  if event.global_sequence <= end]
        row = saved["actors"].get(actor_ref) if saved is not None else None
        checkpoint = None
        if row is not None:
            entries = {}
            for resource_id, entry in row["entries"].items():
                fields = dict(entry, modifier_ledger=tuple(entry["modifier_ledger"]))
                entries[resource_id] = ResourceEntry(**fields)
            checkpoint = ResourceStateProjection(actor_ref=actor_ref, entries=entries,
                reservations={key: tuple(value) for key, value in row["reservations"].items()},
                locks={key: tuple(value) for key, value in row["locks"].items()},
                source_revision_vector=row["source_revision_vector"], projection_revision=row["projection_revision"])
        tail = projector.rebuild_resources(actor_ref,
            [event for event in events if event.global_sequence > start], checkpoint=checkpoint)
        rebuilt = dict(entries=_json(tail.entries), reservations=_json(tail.reservations),
            locks=_json(tail.locks), source_revision_vector=_json(tail.source_revision_vector),
            projection_revision=tail.projection_revision,
            reconstruction_api="ResourceBodyRuntimeProjector.rebuild_resources")
        if rebuilt != expected:
            raise ValueError("replay_resource_checkpoint_tail_mismatch")


def _equipment_state(projection):
    return dict(activations=_json(projection.activations), active_by_slot=_json(projection.active_by_slot),
        ended_activation_ids=_json(projection.ended_activation_ids),
        source_revision_vector=_json(projection.source_revision_vector),
        projection_revision=projection.projection_revision,
        reconstruction_api="EquipmentProjector.rebuild")


def _inventory_domain_state(projection):
    return dict(items=_json(projection.items), containers=_json(projection.containers),
        locations=_json(projection.locations), reservations=_json(projection.reservations),
        capacity_reservations=_json(projection.capacity_reservations),
        source_revision_vector=_json(projection.source_revision_vector),
        projection_revision=projection.projection_revision,
        reconstruction_api="InventoryProjector.rebuild")


def _inventory_domain_participant(store, authority, *, boundary_sequence=None):
    from app.gameplay.inventory_runtime import InventoryProjector

    events = [event for event in store.read_events()
              if (event.stream_id.startswith("gameplay:inventory:")
                  or event.event_type.startswith("gameplay.inventory."))
              and (boundary_sequence is None or event.global_sequence <= boundary_sequence)]
    if authority is None or getattr(authority, "_store", None) is not store:
        raise ValueError("replay_inventory_domain_authority_missing")
    grouped = {}
    refs = []
    for event in events:
        actor_ref = event.stream_id.removeprefix("gameplay:inventory:")
        if (not event.stream_id.startswith("gameplay:inventory:") or not actor_ref
                or event.event_type not in _INVENTORY_EVENT_TYPES or event.schema_version != 1
                or event.payload.get("actor_ref") != actor_ref):
            raise ValueError("replay_inventory_domain_event_scope_unsupported")
        grouped.setdefault(actor_ref, []).append(event)
        refs.append(dict(event_id=event.event_id, global_sequence=event.global_sequence,
            stream_id=event.stream_id, stream_revision=event.stream_revision,
            transaction_id=event.transaction_id, event_type=event.event_type,
            event_digest=_digest(_json(event))))
    all_events = {event.event_id: event for event in store.read_events()
                  if boundary_sequence is None or event.global_sequence <= boundary_sequence}
    projector = InventoryProjector(authority._registry)
    actors = {actor: _inventory_domain_state(projector.rebuild(
        actor, actor_events, referenced_events=all_events))
        for actor, actor_events in sorted(grouped.items())}
    return dict(schema_version=1, scope="project:inventory-domain", event_refs=refs, actors=actors,
        view_digest=_digest(dict(actors=actors, event_refs=refs)),
        reconstruction_api="InventoryProjector.rebuild")


def _validate_inventory_domain_participant(store, authority, saved, *, boundary_sequence=None):
    expected = _inventory_domain_participant(store, authority, boundary_sequence=boundary_sequence)
    if saved is None:
        if expected["event_refs"]:
            raise ValueError("replay_inventory_domain_participant_scope_mismatch")
        return
    if saved.get("schema_version") != 1:
        raise ValueError("replay_decoder_unsupported")
    if saved != expected:
        raise ValueError("replay_saved_inventory_domain_projection_mismatch")


def validate_inventory_checkpoint_tail(store, authority, saved, current, start, end):
    from app.gameplay.inventory_runtime import (CommerceCapacityReservation, InventoryContainer,
        InventoryItem, InventoryProjection, InventoryProjector, InventoryReservation)

    if saved is None and current is None:
        return
    if (current is None or saved is None and bool(current["event_refs"])
            or saved is not None and not set(saved["actors"]) <= set(current["actors"])):
        raise ValueError("replay_inventory_domain_checkpoint_scope_mismatch")
    if authority is None or getattr(authority, "_store", None) is not store:
        raise ValueError("replay_inventory_domain_authority_missing")
    all_events = {event.event_id: event for event in store.read_events()
                  if event.global_sequence <= end}
    projector = InventoryProjector(authority._registry)
    for actor_ref, expected in current["actors"].items():
        row = saved["actors"].get(actor_ref) if saved is not None else None
        checkpoint = None
        if row is not None:
            checkpoint = InventoryProjection(actor_ref=actor_ref,
                items={key: InventoryItem(**value) for key, value in row["items"].items()},
                containers={key: InventoryContainer(**value) for key, value in row["containers"].items()},
                locations=row["locations"], source_revision_vector=row["source_revision_vector"],
                projection_revision=row["projection_revision"],
                reservations={key: InventoryReservation(**value) for key, value in row["reservations"].items()},
                capacity_reservations={key: CommerceCapacityReservation(**value)
                                       for key, value in row["capacity_reservations"].items()})
        events = [event for event in store.read_stream(f"gameplay:inventory:{actor_ref}")
                  if start < event.global_sequence <= end]
        projection = projector.rebuild(actor_ref, events, checkpoint=checkpoint, referenced_events=all_events)
        if _inventory_domain_state(projection) != expected:
            raise ValueError("replay_inventory_domain_checkpoint_tail_mismatch")


def _equipment_participant(store, *, boundary_sequence=None):
    """Rebuild the complete Equipment lifecycle scope at a committed cut."""
    from app.gameplay.equipment_runtime import EquipmentProjector

    events = [event for event in store.read_events()
              if (event.stream_id.startswith("gameplay:equipment:") or event.event_type in _EQUIPMENT_EVENT_TYPES)
              and (boundary_sequence is None or event.global_sequence <= boundary_sequence)]
    grouped = {}
    refs = []
    for event in events:
        actor_ref = event.stream_id.removeprefix("gameplay:equipment:")
        if (not event.stream_id.startswith("gameplay:equipment:") or not actor_ref
                or event.event_type not in _EQUIPMENT_EVENT_TYPES or event.schema_version != 1
                or event.payload.get("actor_ref") != actor_ref):
            raise ValueError("replay_equipment_event_scope_unsupported")
        grouped.setdefault(actor_ref, []).append(event)
        refs.append(dict(event_id=event.event_id, global_sequence=event.global_sequence,
            stream_id=event.stream_id, stream_revision=event.stream_revision,
            transaction_id=event.transaction_id, event_type=event.event_type,
            event_digest=_digest(_json(event))))
    projector = EquipmentProjector()
    actors = {actor: _equipment_state(projector.rebuild(actor, actor_events))
              for actor, actor_events in sorted(grouped.items())}
    return dict(schema_version=1, scope="project:equipment", event_refs=refs, actors=actors,
        view_digest=_digest(dict(actors=actors, event_refs=refs)), reconstruction_api="EquipmentProjector.rebuild")


def _validate_equipment_participant(store, saved, *, boundary_sequence=None):
    expected = _equipment_participant(store, boundary_sequence=boundary_sequence)
    if saved is None:
        if expected["event_refs"]:
            raise ValueError("replay_equipment_participant_scope_mismatch")
        return
    if saved.get("schema_version") != 1:
        raise ValueError("replay_decoder_unsupported")
    if saved != expected:
        raise ValueError("replay_saved_equipment_projection_mismatch")


def validate_equipment_checkpoint_tail(store, saved, current, start, end):
    """Restore Equipment's saved domain projection and apply only its tail."""
    from app.gameplay.equipment_runtime import EquipmentActivation, EquipmentProjection, EquipmentProjector

    if saved is None and current is None:
        return
    if (current is None or saved is None and bool(current["event_refs"])
            or saved is not None and not set(saved["actors"]) <= set(current["actors"])):
        raise ValueError("replay_equipment_checkpoint_scope_mismatch")
    for actor_ref, expected in current["actors"].items():
        row = saved["actors"].get(actor_ref) if saved is not None else None
        checkpoint = None
        if row is not None:
            activations = {}
            for activation_id, activation in row["activations"].items():
                fields = dict(activation)
                for key in ("slot_keys", "ability_grant_ids", "modifier_instance_ids", "container_access_container_ids"):
                    fields[key] = tuple(fields[key])
                activations[activation_id] = EquipmentActivation(**fields)
            checkpoint = EquipmentProjection(actor_ref=actor_ref, activations=activations,
                active_by_slot=row["active_by_slot"], ended_activation_ids=tuple(row["ended_activation_ids"]),
                source_revision_vector=row["source_revision_vector"], projection_revision=row["projection_revision"])
        events = [event for event in store.read_stream(f"gameplay:equipment:{actor_ref}")
                  if start < event.global_sequence <= end]
        projection = EquipmentProjector().rebuild(actor_ref, events, checkpoint=checkpoint)
        if _equipment_state(projection) != expected:
            raise ValueError("replay_equipment_checkpoint_tail_mismatch")


def _inventory_participant(store, authority):
    """Capture the existing Inventory custody projection when it has facts.

    Inventory is optional for the admitted settlement scope.  We do not add an
    empty/synthetic participant to old captures; a participant is present only
    when the store contains real production-output custody events.
    """
    if authority is None:
        return None
    if getattr(authority, "_store", None) is not store:
        raise ValueError("replay_inventory_store_mismatch")
    event_type = "gameplay.inventory.production_output_received@1"
    events = [event for event in store.read_events() if event.event_type == event_type]
    if not events:
        return None
    view = authority.production_output_custody_view_for()
    rows = list(view.get("rows", ()))
    if len(rows) != len(events):
        raise ValueError("replay_inventory_projection_count_mismatch")
    event_refs = [dict(
            event_id=event.event_id,
            global_sequence=event.global_sequence,
            payload_digest=_digest(_json(event.payload)),
        ) for event in events]
    source_revision_vector = _json(view.get("source_revision_vector", {}))
    return dict(
        schema_version=1,
        scope=view.get("scope"),
        rows=_json(rows),
        event_refs=event_refs,
        source_revision_vector=source_revision_vector,
        view_digest=_digest(_json(view)),
        stream_id_prefix="gameplay:inventory:",
        reconstruction_api="InventoryAuthorityService.production_output_custody_view_for",
    )


_SOCIAL_EVENT_TYPES = frozenset({
    "gameplay.social.relationship_fact_recorded",
    "gameplay.social.knowledge_observed",
    "gameplay.social.visibility_revoked",
    "gameplay.social.population_signal_recorded@1",
})


def _social_events(store, *, boundary_sequence=None):
    from app.gameplay.p5.social_knowledge import _knowledge_stream, _relationship_stream, _PRINCIPAL

    events = []
    prefixes = (
        "gameplay.social.relationship_fact_recorded",
        "gameplay.social.knowledge_observed",
        "gameplay.social.visibility_revoked",
        "gameplay.social.population_signal_recorded",
    )
    for event in store.read_events():
        if (not event.event_type.startswith(prefixes)
                or boundary_sequence is not None and event.global_sequence > boundary_sequence):
            continue
        payload = event.payload
        if not isinstance(payload, dict):
            raise ValueError("replay_social_event_provenance_invalid")
        if event.event_type == "gameplay.social.relationship_fact_recorded":
            fields = (payload.get("source_ref"), payload.get("target_ref"), payload.get("relation_kind"))
            expected_stream = (_relationship_stream(source_ref=fields[0], target_ref=fields[1],
                                                   relation_kind=fields[2])
                               if all(isinstance(field, str) and field for field in fields) else None)
            expected_visibility = payload.get("visibility")
        elif event.event_type in {"gameplay.social.knowledge_observed", "gameplay.social.visibility_revoked"}:
            fields = (payload.get("knower_ref"), payload.get("fact_ref"))
            expected_stream = (_knowledge_stream(knower_ref=fields[0], fact_ref=fields[1])
                               if all(isinstance(field, str) and field for field in fields) else None)
            expected_visibility = ("authority_only" if event.event_type == "gameplay.social.visibility_revoked"
                                   else payload.get("visibility"))
        elif event.event_type == "gameplay.social.population_signal_recorded@1":
            signal_ref = payload.get("signal_ref")
            expected_stream = (f"gameplay:social:population:{signal_ref}"
                               if isinstance(signal_ref, str) and signal_ref else None)
            expected_visibility = "public"
        else:
            expected_stream = expected_visibility = None
        transaction = store.get_transaction(event.transaction_id)
        try:
            persisted = store.get_event(event.event_id)
        except KeyError as exc:
            raise ValueError("replay_social_event_provenance_invalid") from exc
        valid_visibility = (isinstance(expected_visibility, str)
                            and (expected_visibility in {"public", "authority_only"}
                                 or expected_visibility.startswith("actor:")
                                 and len(expected_visibility) > len("actor:")))
        if (event.event_type not in _SOCIAL_EVENT_TYPES or event.schema_version != 1
                or expected_stream is None or event.stream_id != expected_stream
                or not valid_visibility or event.visibility_policy != expected_visibility
                or transaction is None or event not in transaction.events or persisted != event
                or not store.transaction_owns_event(
                    transaction_id=event.transaction_id, event_id=event.event_id,
                    principal_ref=_PRINCIPAL)):
            raise ValueError("replay_social_event_provenance_invalid")
        events.append(event)
    return events


def _social_participant(store, authority, *, recipient_ref, now):
    """Capture one real recipient-scoped Social projection."""
    if authority is None:
        return None
    if getattr(authority, "_store", None) is not store:
        raise ValueError("replay_social_store_mismatch")
    events = _social_events(store)
    view = authority.view_for(recipient_ref=recipient_ref, now=now)
    event_refs = [dict(event_id=event.event_id, global_sequence=event.global_sequence,
                       stream_id=event.stream_id, stream_revision=event.stream_revision,
                       payload_digest=_digest(_json(event.payload))) for event in events]
    return dict(schema_version=1, recipient_ref=recipient_ref, now=now,
                projection=_json(view), event_refs=event_refs,
                source_revision_vector=_json(view.source_revision_vector),
                projection_hash=view.projection_hash,
                reconstruction_api="SocialFactAuthority.view_for")


_SOCIAL_DELIVERY_EVENT_TYPES = frozenset({
    "gameplay.social.delivery_recorded@1",
    "gameplay.social.delivery_expired@1",
})


def _social_delivery_events(store, *, boundary_sequence=None):
    from app.gameplay.p5.social_delivery import _PRINCIPAL, _delivery_stream

    events = []
    for event in store.read_events():
        if (not event.event_type.startswith("gameplay.social.delivery_")
                or boundary_sequence is not None and event.global_sequence > boundary_sequence):
            continue
        recipient = event.payload.get("recipient_ref")
        delivery = event.payload.get("delivery_ref")
        transaction = store.get_transaction(event.transaction_id)
        try:
            persisted = store.get_event(event.event_id)
        except KeyError as exc:
            raise ValueError("replay_social_delivery_event_provenance_invalid") from exc
        if (event.event_type not in _SOCIAL_DELIVERY_EVENT_TYPES or event.schema_version != 1
                or not isinstance(recipient, str) or not recipient
                or not isinstance(delivery, str) or not delivery
                or event.stream_id != _delivery_stream(recipient, delivery)
                or event.visibility_policy != f"actor:{recipient}"
                or transaction is None or event not in transaction.events or persisted != event
                or not store.transaction_owns_event(
                    transaction_id=event.transaction_id, event_id=event.event_id,
                    principal_ref=_PRINCIPAL)):
            raise ValueError("replay_social_delivery_event_provenance_invalid")
        events.append(event)
    return events


def _social_delivery_scope_recipients(store, *, boundary_sequence=None):
    from app.gameplay.p5.social_delivery_caller import GovernmentPublicMillingSocialDeliveryCaller

    caller = GovernmentPublicMillingSocialDeliveryCaller(store=store)
    recipients = {event.payload["recipient_ref"] for event in _social_delivery_events(
        store, boundary_sequence=boundary_sequence)
        if event.event_type == "gameplay.social.delivery_recorded@1"}
    for event in store.read_events():
        if boundary_sequence is not None and event.global_sequence > boundary_sequence:
            continue
        if event.event_type == caller.NOTICE_TYPE:
            recipient = caller._bound_receiver(event)
            if recipient is not None:
                recipients.add(recipient)
    return tuple(sorted(recipients))


def _unbound_social_delivery_participant(now):
    if type(now) is not int or now < 0:
        raise ValueError("replay_social_delivery_time_invalid")
    return dict(schema_version=1, scope="project:social-delivery-unbound",
                recipient_ref=None, now=now, projection=None, projection_hash=None,
                event_refs=[], source_revision_vector={},
                reconstruction_api="SocialDeliveryAuthority.view_for")


def _social_delivery_participant(store, authority, *, recipient_ref, now, boundary_sequence=None):
    """Capture a real recipient delivery projection, if one exists."""
    if authority is None:
        return None
    if getattr(authority, "_store", None) is not store:
        raise ValueError("replay_social_delivery_store_mismatch")
    if isinstance(recipient_ref, tuple):
        if (len(recipient_ref) < 2 or recipient_ref != tuple(sorted(set(recipient_ref)))
                or recipient_ref != _social_delivery_scope_recipients(
                    store, boundary_sequence=boundary_sequence)):
            raise ValueError("replay_social_delivery_multiple_scopes_invalid")
        recipients = {recipient: _social_delivery_participant(
            store, authority, recipient_ref=recipient, now=now, boundary_sequence=boundary_sequence)
            for recipient in recipient_ref}
        refs = sorted((ref for value in recipients.values() for ref in value["event_refs"]),
                      key=lambda ref: ref["global_sequence"])
        return dict(schema_version=1, scope="project:social-delivery-multi",
                    recipient_refs=list(recipient_ref), now=now, recipients=recipients,
                    event_refs=refs, view_digest=_digest(recipients),
                    reconstruction_api="SocialDeliveryAuthority.view_for")
    if recipient_ref is None:
        if _social_delivery_events(store, boundary_sequence=boundary_sequence):
            raise ValueError("replay_social_delivery_scope_unbound")
        return _unbound_social_delivery_participant(now)
    events = [event for event in _social_delivery_events(store, boundary_sequence=boundary_sequence)
              if event.payload["recipient_ref"] == recipient_ref]
    view = authority.view_for(recipient_ref=recipient_ref, world_now=now, checkpoint_at=boundary_sequence)
    refs = [dict(event_id=event.event_id, global_sequence=event.global_sequence,
                 stream_id=event.stream_id, stream_revision=event.stream_revision,
                 transaction_id=event.transaction_id, event_type=event.event_type,
                 payload_digest=_digest(_json(event.payload))) for event in events]
    return dict(schema_version=1, scope="project:social-delivery", recipient_ref=recipient_ref,
                now=now, projection=_json(view), projection_hash=view.projection_hash,
                event_refs=refs, source_revision_vector=_json(view.source_revision_vector),
                reconstruction_api="SocialDeliveryAuthority.view_for")


_PRESENCE_EVENT_TYPES = frozenset({
    "population.presence.spawned",
    "population.presence.despawned",
})


def _presence_participant(store, authority, *, boundary_sequence=None):
    """Capture canonical Population presence only when real owner facts exist."""
    if authority is None:
        return None
    if getattr(authority, "store", None) is not store:
        raise ValueError("replay_presence_store_mismatch")
    events = [event for event in store.read_events()
              if event.event_type in _PRESENCE_EVENT_TYPES
              and (boundary_sequence is None or event.global_sequence <= boundary_sequence)]
    for event in events:
        world = str(event.payload.get("world_ref", ""))
        character = str(event.payload.get("character_ref", ""))
        incarnation = event.payload.get("incarnation")
        if not world or not character or type(incarnation) is not int:
            raise ValueError("replay_saved_presence_projection_mismatch")
    rows = []
    worlds = sorted({str(event.payload["world_ref"]) for event in events})
    for world in worlds:
        projection = authority.projection(world, checkpoint_at=boundary_sequence)
        rows.extend(
            dict(world_ref=world, character_ref=character, **value)
            for character, value in sorted(projection.items())
        )
    refs = [dict(event_id=event.event_id, global_sequence=event.global_sequence,
                 stream_id=event.stream_id, stream_revision=event.stream_revision,
                 transaction_id=event.transaction_id, event_type=event.event_type,
                 payload_digest=_digest(_json(event.payload))) for event in events]
    return dict(schema_version=1, scope="project:population-presence", rows=_json(rows),
                event_refs=refs, view_digest=_digest(_json(rows)),
                reconstruction_api="PopulationPresenceAuthority.projection")


def _life_state_events(store, *, boundary_sequence=None):
    return [event for event in store.read_events()
            if (event.stream_id.startswith("gameplay:character:life:")
                or event.event_type == _LIFE_STATE_EVENT)
            and (boundary_sequence is None or event.global_sequence <= boundary_sequence)]


def _life_state_rows(store, events, *, checkpoint=None):
    rows = {actor: dict(row) for actor, row in (checkpoint or {}).items()}
    for event in events:
        actor = event.stream_id.removeprefix("gameplay:character:life:")
        payload = event.payload
        if (not event.stream_id.startswith("gameplay:character:life:") or not actor
                or event.event_type != _LIFE_STATE_EVENT or event.schema_version not in {1, 2}
                or event.visibility_policy != "project" or payload.get("actor_ref") != actor):
            raise ValueError("replay_life_state_event_scope_unsupported")
        previous = rows.get(actor, dict(state="unknown", incarnation=None,
                                        source_revision_vector={}, projection_revision=0))
        state = payload.get("to_state")
        if (payload.get("from_state") != previous["state"] or state not in {"alive", "dead"}
                or previous["state"] == "dead" or state == previous["state"]):
            raise ValueError("replay_life_state_transition_invalid")
        principal = ("authority:character:life-state:presence-admission" if state == "alive"
                     else "authority:character:life-state")
        if not store.transaction_owns_event(transaction_id=event.transaction_id,
                                             event_id=event.event_id, principal_ref=principal):
            raise ValueError("replay_life_state_owner_mismatch")
        incarnation = previous["incarnation"]
        if state == "alive":
            incarnation = payload.get("incarnation")
            activation = store.get_event(payload.get("source_activation_event_id", ""))
            presence = store.get_event(payload.get("source_presence_event_id", ""))
            activation_tx = store.get_transaction(activation.transaction_id)
            if (event.schema_version != 2 or type(incarnation) is not int or incarnation < 1
                    or activation.event_type != "population.activation.committed"
                    or presence.event_type != "population.presence.spawned"
                    or activation_tx is None or activation not in activation_tx.events
                    or not activation_tx.idempotency_record.principal_ref.startswith(
                        ("population:", "world_runtime."))
                    or not store.transaction_owns_event(
                        transaction_id=presence.transaction_id, event_id=presence.event_id,
                        principal_ref="population.presence_authority")
                    or activation.global_sequence >= presence.global_sequence
                    or presence.global_sequence >= event.global_sequence
                    or activation.payload.get("profile_ref") != actor
                    or presence.payload.get("character_ref") != actor
                    or presence.payload.get("incarnation") != incarnation
                    or presence.payload.get("source_activation_event_id") != activation.event_id
                    or activation.payload.get("world_ref") != presence.payload.get("world_ref")
                    or payload.get("world_ref") != presence.payload.get("world_ref")
                    or payload.get("source_activation_revision") != activation.stream_revision
                    or payload.get("source_presence_revision") != presence.stream_revision):
                raise ValueError("replay_life_state_source_mismatch")
        else:
            confirmation = store.get_event(payload.get("source_confirmation_event_id", ""))
            terminal = store.get_event(confirmation.payload.get("source_event_id", ""))
            if (confirmation.event_type != "gameplay.conflict.world_death_commit_confirmed"
                    or not store.transaction_owns_event(
                        transaction_id=confirmation.transaction_id,
                        event_id=confirmation.event_id,
                        principal_ref="authority:p5:investigation-conflict")
                    or terminal.event_type != "gameplay.conflict.terminal_outcome_recorded"
                    or not store.transaction_owns_event(
                        transaction_id=terminal.transaction_id,
                        event_id=terminal.event_id,
                        principal_ref="authority:p5:investigation-conflict")
                    or terminal.stream_id != confirmation.stream_id
                    or terminal.payload.get("terminal_kind") != "case_death"
                    or terminal.payload.get("actor_ref") != actor
                    or terminal.global_sequence >= confirmation.global_sequence
                    or confirmation.payload.get("source_revision") != terminal.stream_revision
                    or confirmation.global_sequence >= event.global_sequence
                    or confirmation.payload.get("target_actor_ref") != actor
                    or confirmation.payload.get("confirmed") is not True
                    or payload.get("source_confirmation_revision") != confirmation.stream_revision):
                raise ValueError("replay_life_state_source_mismatch")
        revisions = dict(previous["source_revision_vector"])
        revisions[event.stream_id] = event.stream_revision
        rows[actor] = dict(state=state, incarnation=incarnation,
                           source_revision_vector=revisions,
                           projection_revision=previous["projection_revision"] + 1)
    return rows


def _life_state_participant(store, *, boundary_sequence=None):
    events = _life_state_events(store, boundary_sequence=boundary_sequence)
    try:
        actors = _life_state_rows(store, events)
    except KeyError as exc:
        raise ValueError("replay_life_state_source_missing") from exc
    refs = [dict(event_id=event.event_id, global_sequence=event.global_sequence,
                 stream_id=event.stream_id, stream_revision=event.stream_revision,
                 transaction_id=event.transaction_id, event_type=event.event_type,
                 event_digest=_digest(_json(event))) for event in events]
    return dict(schema_version=1, scope="project:character-life-state", event_refs=refs,
                actors=actors, view_digest=_digest(dict(actors=actors, event_refs=refs)),
                reconstruction_api="life_state_event_projection")


def _validate_life_state_participant(store, saved, *, boundary_sequence=None):
    expected = _life_state_participant(store, boundary_sequence=boundary_sequence)
    if saved is None and not expected["event_refs"]:
        return
    if saved is None:
        raise ValueError("replay_life_state_participant_scope_mismatch")
    if saved != expected:
        raise ValueError("replay_saved_life_state_projection_mismatch")


def validate_life_state_checkpoint_tail(store, saved, current, start, end):
    if saved is None and current is None:
        return
    if saved is None or current is None:
        raise ValueError("replay_life_state_checkpoint_scope_mismatch")
    tail_events = [event for event in _life_state_events(store, boundary_sequence=end)
                   if event.global_sequence > start]
    try:
        rebuilt = _life_state_rows(store, tail_events, checkpoint=saved["actors"])
    except KeyError as exc:
        raise ValueError("replay_life_state_source_missing") from exc
    if rebuilt != current["actors"]:
        raise ValueError("replay_life_state_checkpoint_tail_mismatch")


def capture_participants(store, coordinator, driver, consumer, batch_refs, *, inventory_authority=None,
                         social_authority=None, social_recipient_ref=None, social_now=None,
                         social_delivery_authority=None, social_delivery_recipient_ref=None,
                         social_delivery_now=None, presence_authority=None):
    """Capture required inputs and reconstruction references; missing means incomplete."""
    if driver is None or consumer is None or coordinator is None:
        raise ValueError("replay_required_participant_missing")
    if driver.world_runtime.store is not store or consumer.service._store is not store:
        raise ValueError("replay_participant_store_mismatch")
    refs = tuple(sorted(batch_refs))
    if not refs or len(refs) != len(set(refs)):
        raise ValueError("replay_batch_scope_invalid")
    consumer._check_open()
    timeline = driver.clock.timeline
    batches, revisions, dependencies = {}, {}, {}
    for ref in refs:
        plan = coordinator.load(ref)
        if plan.timeline_ref != timeline.timeline_id or plan.frozen_window is None:
            raise ValueError("replay_batch_timeline_mismatch")
        plan.frozen_window.validate(plan)
        if plan.predecessor_batch_ref is not None and plan.predecessor_batch_ref not in refs:
            raise ValueError("replay_batch_predecessor_missing")
        saved = store.get_projection_checkpoint(f"batch-input:{ref}")
        if saved.projector_version != "1" or saved.projection_schema_version != 1:
            raise ValueError("replay_participant_decoder_unsupported")
        operations = []
        cursor = 0
        claim_context = _json(plan.frozen_window)
        claim_context["window"].pop("settlement_idempotency_key")
        for operation in plan.ordered_operations():
            adapter = coordinator.adapters.get((operation.owner_ref, operation.owner_contract_ref))
            if adapter is None or adapter.store is not store:
                raise ValueError("replay_required_owner_missing")
            command = operation.command
            claim = store.get_projection_checkpoint(
                f"batch-operation:{_digest((operation.owner_ref, command.idempotency_key))}")
            if claim is None or claim.projector_id != "world_runtime.batch_operation@1":
                raise ValueError("replay_batch_claim_missing")
            if claim.projector_version != "1" or claim.projection_schema_version != 1:
                raise ValueError("replay_participant_decoder_unsupported")
            expected_claim = _digest(dict(operation=operation.input_digest, window=claim_context,
                rules=plan.definition_and_rule_pins, plan_revision=plan.plan_revision,
                dependencies=sorted((a, b) for a, b in plan.dependency_edges if b == operation.operation_ref),
                ordering=plan.ordering_policy_ref, failure=plan.failure_policy_ref))
            if claim.projection_hash != expected_claim:
                raise ValueError("replay_batch_claim_digest_mismatch")
            receipt = adapter.query(operation)
            if receipt is None and any(event.command_id == command.command_id
                    for stream in command.expected_revisions for event in store.read_stream(stream)):
                raise ValueError("replay_owner_receipt_missing")
            owner_events = [store.get_event(event_id) for event_id in receipt.committed_event_ids] if receipt and receipt.committed else []
            if any(event is None or not store.transaction_owns_event(
                    transaction_id=event.transaction_id, event_id=event.event_id,
                    principal_ref=operation.owner_ref) for event in owner_events):
                raise ValueError("replay_owner_receipt_invalid")
            for stream in command.expected_revisions:
                revisions[stream] = store.get_stream_head(stream)
            # Preserve external historical references rather than adding new owners.
            for stream, revision in command.read_set_revisions.items():
                events = store.read_stream(stream, from_revision=revision, limit=1) if revision else []
                producer = next((candidate for candidate in plan.operations
                    if (candidate.operation_ref, operation.operation_ref) in plan.dependency_edges
                    and candidate.command.expected_revisions.get(stream, -2) + 1 == revision), None)
                if revision and (not events or events[0].stream_revision != revision) and producer is None:
                    raise ValueError("replay_dependency_revision_missing")
                dependencies[f"{stream}@{revision}"] = dict(
                    stream_id=stream, owner_revision=revision,
                    pending_producer_ref=producer.operation_ref if producer is not None and not events else None,
                    event_ref=events[0].event_id if events else None,
                    event_digest=_digest(_json(events[0])) if events else None,
                    reconstruction_api="GameplayEventStore.read_stream", schema_version=1)
            operations.append(dict(operation_ref=operation.operation_ref, owner_ref=operation.owner_ref,
                owner_contract_ref=operation.owner_contract_ref, input_digest=operation.input_digest,
                claim=_json(claim), expected_revisions=dict(command.expected_revisions),
                receipt=_json(receipt) if receipt is not None else None,
                owner_events=_json(owner_events)))
            if receipt is not None and receipt.committed and cursor == len(operations) - 1:
                cursor += 1
        batches[ref] = dict(input=_json(saved), frozen_input=_json(saved), operations=operations,
                            claims=[operation["claim"] for operation in operations],
                            receipts={operation["operation_ref"]: operation["receipt"] for operation in operations},
                            recovery_cursor=cursor,
                            stage="completed" if cursor == len(operations) else "pending_recovery")
    world = driver.world_runtime
    population_stream = f"population-cadence:{world.mode.world_ref}"
    population_events = store.read_stream(population_stream)
    population_state = world.export_recovery_state()
    if population_state["confirmed_tick"] != driver.current_tick:
        raise ValueError("replay_population_cursor_incomplete")
    latest = population_events[-1] if population_events else None
    confirmed_pins = latest.payload.get("time_pins") if latest is not None else None
    if driver.current_tick and (latest is None or confirmed_pins is None):
        raise ValueError("replay_population_confirmation_missing")
    status_actors = {}
    for actor, binding in sorted(consumer.bindings.items()):
        if binding is None:
            raise ValueError("replay_status_binding_missing")
        consumer.context(driver, actor)
        stream = f"gameplay:status_tags:{actor}"
        events = store.read_stream(stream)
        if any(event.schema_version != 1 for event in events):
            raise ValueError("replay_participant_decoder_unsupported")
        projection = consumer.service.projector.rebuild(actor, events)
        revisions[stream] = store.get_stream_head(stream)
        definitions = {event.payload["tag_id"] for event in events if "tag_id" in event.payload}
        status_actors[actor] = dict(binding=_json(binding), projection=_json(projection),
            definitions={tag: _json(consumer.service.projector.registry.resolve(tag)) for tag in sorted(definitions)},
            stream_id=stream, reconstruction_api="StatusTagProjector.rebuild", schema_version=1)
    migration_stream = f"temporal-activation:{timeline.timeline_id}"
    migration_events = store.read_stream(migration_stream)
    if any(event.schema_version != 1 for event in migration_events):
        raise ValueError("replay_participant_decoder_unsupported")
    pending = bool(migration_events and migration_events[-1].event_type.endswith(".prepared"))
    if pending != driver.migration_pending:
        raise ValueError("replay_migration_state_incomplete")
    revisions[population_stream] = store.get_stream_head(population_stream)
    revisions[migration_stream] = store.get_stream_head(migration_stream)
    inventory = _inventory_participant(store, inventory_authority)
    inventory_domain = _inventory_domain_participant(store, inventory_authority)
    resource = _resource_participant(store)
    equipment = _equipment_participant(store)
    economy_temporal = _economy_temporal_participant(store)
    economy_random = _economy_random_participant(store)
    ecology_temporal = _ecology_temporal_participant(store)
    if any(event.event_type in _PRESENCE_EVENT_TYPES for event in store.read_events()) and presence_authority is None:
        raise ValueError("replay_presence_participant_missing")
    presence = _presence_participant(store, presence_authority)
    life_state = _life_state_participant(store)
    result = dict(schema_version=1, versions={"participant_manifest": 1, "batch_input": 1,
        "batch_operation": 1, "population_recovery": 1, "status_events": 1, "migration_events": 1,
        "economy_temporal": 1, "ecology_temporal": 1},
        timeline=_json(timeline), profile=_json(driver.clock.temporal_profile),
        mapping=_json(driver.mapping), confirmed_tick=driver.current_tick, window_ticks=driver.window_size,
        owner_revisions=revisions, batches=batches, external_dependencies=dependencies,
        population=dict(schema_version=1, confirmed_tick=driver.current_tick, confirmed_time_pins=_json(confirmed_pins),
            mode=_json(world.mode), roster=_json(world.roster),
            authorized_actor_refs=sorted(world.authorized_actor_refs) if world.authorized_actor_refs is not None else None,
            stream_id=population_stream, event_ref=latest.event_id if latest else None,
            recovery_state=population_state,
            reconstruction_api="WorldContinuityRuntime.restore_recovery_state;RuntimeCadencePublisher._restore"),
        status=dict(schema_version=1, actors=status_actors, pending_work=_json(consumer.pending_work())),
        migration=dict(schema_version=1, stream_id=migration_stream, pending=pending,
            events=_json(migration_events), reconstruction_api="temporal_migration.restore_clock"),
        random_context=dict(status="not_applicable", reason="Admitted settlement commands, status work and migration use frozen structured inputs; no random draw or provider invocation.", t07="not_verified"))
    if inventory is not None:
        result["inventory"] = inventory
    if inventory_domain is not None:
        result["inventory_domain"] = inventory_domain
        result["versions"]["inventory_domain"] = 1
    if resource is not None:
        result["resource"] = resource
        result["versions"]["resource"] = 1
    if equipment is not None:
        result["equipment"] = equipment
        result["versions"]["equipment"] = 1
    result["economy_temporal"] = economy_temporal
    result["economy_random"] = economy_random
    result["versions"]["economy_random"] = 1
    if economy_random["event_refs"]:
        result["random_context"] = dict(
            status="bounded_owner_result" if economy_random["result_count"] else "bounded_owner_anchor_pending",
            reason="Private Economy owner random facts are reconstructed in the bounded cut; production demand is unverified.",
            t07="not_verified")
    result["ecology_temporal"] = ecology_temporal
    if social_authority is not None:
        if social_recipient_ref is None or social_now is None:
            raise ValueError("replay_social_scope_missing")
        social = _social_participant(
            store, social_authority, recipient_ref=social_recipient_ref, now=social_now)
        if social is not None:
            result["social"] = social
    if social_delivery_authority is not None:
        if social_delivery_now is None:
            raise ValueError("replay_social_delivery_scope_missing")
        delivery = _social_delivery_participant(
            store, social_delivery_authority,
            recipient_ref=social_delivery_recipient_ref, now=social_delivery_now)
        if delivery is not None:
            result["social_delivery"] = delivery
            result["versions"]["social_delivery"] = 1
    if presence is not None:
        result["presence"] = presence
        result["versions"]["presence"] = 1
    if life_state is not None:
        result["life_state"] = life_state
        result["versions"]["life_state"] = 1
    return result


def validate_saved_participants(store, manifest, batch_refs, boundary_sequence=None, *, inventory_authority=None,
                                social_authority=None, social_delivery_authority=None,
                                presence_authority=None):
    """Verify historical participant claims against durable facts, never submit work."""
    _validate_resource_participant(store, manifest.get("resource"), boundary_sequence=boundary_sequence)
    _validate_life_state_participant(store, manifest.get("life_state"), boundary_sequence=boundary_sequence)
    _validate_economy_random_participant(store, manifest.get("economy_random"),
        boundary_sequence=boundary_sequence)
    _validate_equipment_participant(store, manifest.get("equipment"), boundary_sequence=boundary_sequence)
    _validate_inventory_domain_participant(store, inventory_authority, manifest.get("inventory_domain"),
        boundary_sequence=boundary_sequence)
    from app.gameplay.econ1_economy_runtime import EconomyAuthority
    from app.gameplay.organization_government_runtime import OrganizationAuthority
    from app.gameplay.status_tags import StatusTagAuthorityService, StatusTagDefinition, StatusTagRegistry
    from app.population_continuity.models import WorldModeProfile
    from app.population_continuity.roster import PopulationRoster
    from app.population_continuity.siming_contracts import PopulationCadenceInput
    from app.population_continuity.world import WorldContinuityRuntime
    from .batch_settlement import BatchSettlementCoordinator, OrganizationWindowBatchAdapter, EconomyWageBatchAdapter

    def historical(stream):
        events = store.read_stream(stream)
        if boundary_sequence is not None:
            events = [event for event in events if event.global_sequence <= boundary_sequence]
        expected = manifest["owner_revisions"].get(stream)
        if expected is None or expected != (events[-1].stream_revision if events else 0):
            raise ValueError("replay_saved_owner_revision_mismatch")
        return events

    coordinator = BatchSettlementCoordinator(adapters=(
        OrganizationWindowBatchAdapter(owner=OrganizationAuthority(store=store), store=store),
        EconomyWageBatchAdapter(owner=EconomyAuthority(store=store), store=store)))
    if set(manifest["batches"]) != set(batch_refs):
        raise ValueError("replay_saved_batch_scope_mismatch")
    required_dependencies = set()
    for ref in batch_refs:
        saved = manifest["batches"][ref]
        actual = store.get_projection_checkpoint(f"batch-input:{ref}")
        if actual is None or _json(actual) != saved["frozen_input"]:
            raise ValueError("replay_saved_frozen_input_mismatch")
        if saved["input"] != saved["frozen_input"]:
            raise ValueError("replay_saved_frozen_input_mismatch")
        plan = coordinator.load(ref)
        plan.frozen_window.validate(plan)
        cursor = 0
        for index, operation in enumerate(plan.ordered_operations()):
            required_dependencies.update(f"{stream}@{revision}"
                for stream, revision in operation.command.read_set_revisions.items())
            adapter = coordinator.adapters[(operation.owner_ref, operation.owner_contract_ref)]
            result = adapter.query(operation)
            events = [store.get_event(event_id) for event_id in result.committed_event_ids] if result and result.committed else []
            if events and boundary_sequence is not None and min(event.global_sequence for event in events) > boundary_sequence:
                result = None
            if _json(result) != saved["receipts"][operation.operation_ref]:
                raise ValueError("replay_saved_receipt_mismatch")
            for stream in operation.command.expected_revisions:
                prefix = historical(stream)
                if result is None and any(event.command_id == operation.command.command_id for event in prefix):
                    raise ValueError("replay_owner_receipt_missing")
            claim_id = f"batch-operation:{_digest((operation.owner_ref, operation.command.idempotency_key))}"
            claim = store.get_projection_checkpoint(claim_id)
            if claim is None or _json(claim) != saved["claims"][index]:
                raise ValueError("replay_saved_claim_mismatch")
            if result is not None and result.committed and cursor == index:
                cursor += 1
            details = saved["operations"][index]
            expected_events = events if result is not None and result.committed else []
            if details != dict(operation_ref=operation.operation_ref, owner_ref=operation.owner_ref,
                    owner_contract_ref=operation.owner_contract_ref, input_digest=operation.input_digest,
                    claim=_json(claim), expected_revisions=dict(operation.command.expected_revisions),
                    receipt=_json(result), owner_events=_json(expected_events)):
                raise ValueError("replay_saved_operation_mismatch")
        if saved["recovery_cursor"] != cursor or saved["stage"] != ("completed" if cursor == len(plan.operations) else "pending_recovery"):
            raise ValueError("replay_saved_batch_cursor_mismatch")
    if set(manifest["external_dependencies"]) != required_dependencies:
        raise ValueError("replay_saved_dependency_missing")
    for dependency in manifest["external_dependencies"].values():
        if dependency["schema_version"] != 1:
            raise ValueError("replay_decoder_unsupported")
        revision = dependency["owner_revision"]
        events = store.read_stream(dependency["stream_id"], from_revision=revision, limit=1) if revision else []
        event = events[0] if events else None
        if event is not None and boundary_sequence is not None and event.global_sequence > boundary_sequence:
            event = None
        if (dependency["event_ref"] != (event.event_id if event else None)
                or dependency["event_digest"] != (_digest(_json(event)) if event else None)
                or event is None and revision and not dependency["pending_producer_ref"]):
            raise ValueError("replay_saved_dependency_mismatch")
    work = []
    for actor, saved in manifest["status"]["actors"].items():
        registry = StatusTagRegistry()
        for definition in saved["definitions"].values():
            registry.register(StatusTagDefinition.model_validate(definition))
        service = StatusTagAuthorityService(store=store, registry=registry)
        projection = service.projector.rebuild(actor, historical(saved["stream_id"]))
        if _json(projection) != saved["projection"]:
            raise ValueError("replay_saved_status_projection_mismatch")
        work.extend(service.expiration_works(projection))
    if _json(tuple(work)) != manifest["status"]["pending_work"]:
        raise ValueError("replay_saved_status_work_mismatch")
    population = manifest["population"]
    population_events = historical(population["stream_id"])
    world = WorldContinuityRuntime(store=store, mode=WorldModeProfile.model_validate(population["mode"]),
        roster=PopulationRoster.model_validate(population["roster"]),
        authorized_actor_refs=frozenset(population["authorized_actor_refs"]) if population["authorized_actor_refs"] is not None else None)
    for event in population_events:
        cadence = PopulationCadenceInput.model_validate(event.payload["cadence"])
        # Domain due entries are frozen evidence from this cadence, not re-evaluated owners.
        for actor, obligation, _, _ in world._population_due_index.export_entries():
            if obligation.startswith("projection:organization-window-due:"):
                world.complete_due_population_work(actor, obligation)
        for actor, obligation, due_tick, revision in event.payload.get("domain_due_entries", []):
            world.requeue_due_population_work(actor, obligation, due_tick, revision=revision)
        world.confirm_population_cadence(cadence)
    if world.export_recovery_state() != population["recovery_state"]:
        raise ValueError("replay_saved_population_state_mismatch")
    latest = population_events[-1] if population_events else None
    if (population["confirmed_tick"] != (latest.payload["cadence"]["window_end"] if latest else 0)
            or population["confirmed_time_pins"] != (latest.payload.get("time_pins") if latest else None)):
        raise ValueError("replay_saved_population_cursor_mismatch")
    if manifest["confirmed_tick"] != population["confirmed_tick"]:
        raise ValueError("replay_saved_population_cursor_mismatch")
    pins = population["confirmed_time_pins"]
    # A migration may be committed at this same canonical boundary, so the latest
    # cadence's historical pins remain distinct from the currently active pins.
    migration = manifest["migration"]
    migration_events = historical(migration["stream_id"])
    if _json(migration_events) != migration["events"]:
        raise ValueError("replay_saved_migration_mismatch")
    pending = bool(migration_events and migration_events[-1].event_type.endswith(".prepared"))
    if migration["pending"] != pending:
        raise ValueError("replay_saved_migration_mismatch")
    committed = [event for event in migration_events if event.event_type.endswith(".committed")]
    if committed:
        request = committed[-1].payload["request"]
        if manifest["profile"] != request["profile"] or manifest["mapping"] != request["mapping"]:
            raise ValueError("replay_saved_migration_pins_mismatch")
    elif pins is not None and (manifest["profile"]["revision"] != pins["profile_revision"]
            or manifest["mapping"]["revision"] != pins["mapping_revision"]):
        raise ValueError("replay_saved_migration_pins_mismatch")
    for saved in manifest["status"]["actors"].values():
        binding = saved["binding"]
        if (binding["timeline_id"] != manifest["timeline"]["timeline_id"]
                or binding["profile_revision"] != manifest["profile"]["revision"]
                or binding["mapping_revision"] != manifest["mapping"]["revision"]):
            raise ValueError("replay_saved_status_binding_mismatch")
    saved_inventory = manifest.get("inventory")
    custody_type = "gameplay.inventory.production_output_received@1"
    all_custody_events = [event for event in store.read_events() if event.event_type == custody_type]
    bounded_events = [event for event in all_custody_events
                      if boundary_sequence is None or event.global_sequence <= boundary_sequence]
    if bool(bounded_events) != (saved_inventory is not None):
        raise ValueError("replay_inventory_participant_scope_mismatch")
    if saved_inventory is not None:
        if inventory_authority is None or getattr(inventory_authority, "_store", None) is not store:
            raise ValueError("replay_inventory_participant_missing")
        if saved_inventory.get("schema_version") != 1:
            raise ValueError("replay_decoder_unsupported")
        if (saved_inventory.get("scope") != "project"
                or saved_inventory.get("stream_id_prefix") != "gameplay:inventory:"
                or saved_inventory.get("reconstruction_api") != "InventoryAuthorityService.production_output_custody_view_for"):
            raise ValueError("replay_saved_inventory_scope_mismatch")
        saved_refs = list(saved_inventory.get("event_refs", ()))
        expected_refs = [dict(
            event_id=event.event_id,
            global_sequence=event.global_sequence,
            payload_digest=_digest(_json(event.payload)),
        ) for event in bounded_events]
        if saved_refs != expected_refs:
            raise ValueError("replay_saved_inventory_event_ref_mismatch")
        current_view = inventory_authority.production_output_custody_view_for()
        if current_view.get("scope") != "project":
            raise ValueError("replay_saved_inventory_scope_mismatch")
        expected_rows = [dict(event.payload) for event in bounded_events]
        if _json(saved_inventory.get("rows")) != _json(expected_rows):
            raise ValueError("replay_saved_inventory_projection_mismatch")
        expected_revisions = {}
        all_events = {event.event_id: event for event in store.read_events()}
        for event in bounded_events:
            expected_revisions[event.stream_id] = max(expected_revisions.get(event.stream_id, 0), event.stream_revision)
            source_id = str(event.payload.get("source_certification_event_id", ""))
            source = all_events.get(source_id)
            if (source is None
                    or source.event_type != "gameplay.construction_production.production_output_certified@1"
                    or source.stream_revision != event.payload.get("source_certification_revision")
                    or boundary_sequence is not None and source.global_sequence > boundary_sequence):
                raise ValueError("replay_saved_inventory_source_missing")
            expected_revisions[source.stream_id] = max(expected_revisions.get(source.stream_id, 0), source.stream_revision)
        if saved_inventory.get("source_revision_vector") != expected_revisions:
            raise ValueError("replay_saved_inventory_revision_mismatch")
        expected_view = dict(scope="project", rows=tuple(expected_rows), source_revision_vector=expected_revisions)
        if saved_inventory.get("view_digest") != _digest(_json(expected_view)):
            raise ValueError("replay_saved_inventory_projection_mismatch")
        if boundary_sequence is None and _json(current_view) != _json(expected_view):
            raise ValueError("replay_saved_inventory_projection_mismatch")
    _validate_economy_temporal_participant(
        store, manifest.get("economy_temporal"), boundary_sequence=boundary_sequence
    )
    _validate_ecology_temporal_participant(
        store, manifest.get("ecology_temporal"), boundary_sequence=boundary_sequence
    )
    saved_social = manifest.get("social")
    actual_events = {event.event_id: event for event in _social_events(
        store, boundary_sequence=boundary_sequence)}
    if saved_social is None and actual_events:
        raise ValueError("replay_social_participant_scope_mismatch")
    if saved_social is not None:
        if social_authority is None or getattr(social_authority, "_store", None) is not store:
            raise ValueError("replay_social_participant_missing")
        if saved_social.get("schema_version") != 1:
            raise ValueError("replay_social_decoder_unsupported")
        refs = list(saved_social.get("event_refs", ()))
        if len(refs) != len(actual_events):
            raise ValueError("replay_saved_social_event_scope_mismatch")
        for ref in refs:
            event = actual_events.get(ref.get("event_id"))
            if event is None or event.global_sequence != ref.get("global_sequence"):
                raise ValueError("replay_saved_social_event_ref_mismatch")
            if event.stream_id != ref.get("stream_id") or event.stream_revision != ref.get("stream_revision"):
                raise ValueError("replay_saved_social_revision_mismatch")
            if _digest(_json(event.payload)) != ref.get("payload_digest"):
                raise ValueError("replay_saved_social_event_digest_mismatch")
        if boundary_sequence is None:
            view_authority = social_authority
        else:
            historical_events = tuple(event for event in store.read_events()
                                      if event.global_sequence <= boundary_sequence)

            class _HistoricalSocialStore:
                def read_events(self, **kwargs):
                    return list(historical_events)

            from app.gameplay.p5.social_knowledge import SocialFactAuthority
            view_authority = SocialFactAuthority(
                registry=social_authority._registry,
                store=_HistoricalSocialStore(),
                package_registry=getattr(social_authority, "_package_registry", None),
            )
        view = view_authority.view_for(recipient_ref=saved_social["recipient_ref"], now=saved_social["now"])
        if _json(view) != saved_social.get("projection") or view.projection_hash != saved_social.get("projection_hash"):
            raise ValueError("replay_saved_social_projection_mismatch")
        if _json(view.source_revision_vector) != saved_social.get("source_revision_vector"):
            raise ValueError("replay_saved_social_revision_mismatch")
    saved_delivery = manifest.get("social_delivery")
    bounded_delivery_events = _social_delivery_events(store, boundary_sequence=boundary_sequence)
    if saved_delivery is None and bounded_delivery_events:
        raise ValueError("replay_social_delivery_participant_scope_mismatch")
    if saved_delivery is not None:
        if saved_delivery.get("scope") == "project:social-delivery-unbound":
            if (bounded_delivery_events or saved_delivery != _unbound_social_delivery_participant(
                    saved_delivery.get("now"))):
                raise ValueError("replay_social_delivery_participant_scope_mismatch")
            saved_delivery = None
        elif saved_delivery.get("scope") == "project:social-delivery-multi":
            if social_delivery_authority is None or getattr(social_delivery_authority, "_store", None) is not store:
                raise ValueError("replay_social_delivery_participant_missing")
            refs = saved_delivery.get("recipient_refs")
            if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
                raise ValueError("replay_social_delivery_multiple_scopes_invalid")
            expected = _social_delivery_participant(
                store, social_delivery_authority, recipient_ref=tuple(refs),
                now=saved_delivery.get("now"), boundary_sequence=boundary_sequence)
            if saved_delivery != expected:
                raise ValueError("replay_saved_social_delivery_projection_mismatch")
            saved_delivery = None
    if saved_delivery is not None:
        if social_delivery_authority is None or getattr(social_delivery_authority, "_store", None) is not store:
            raise ValueError("replay_social_delivery_participant_missing")
        if saved_delivery.get("schema_version") != 1 or saved_delivery.get("scope") != "project:social-delivery":
            raise ValueError("replay_social_delivery_decoder_unsupported")
        recipient = saved_delivery.get("recipient_ref")
        if (not isinstance(recipient, str)
                or any(event.payload.get("recipient_ref") != recipient
                       for event in bounded_delivery_events)):
            raise ValueError("replay_social_delivery_participant_scope_mismatch")
        now = saved_delivery.get("now")
        expected = _social_delivery_participant(
            store, social_delivery_authority, recipient_ref=recipient, now=now,
            boundary_sequence=boundary_sequence)
        if expected is None:
            raise ValueError("replay_saved_social_delivery_scope_mismatch")
        for key in ("event_refs", "projection", "projection_hash", "source_revision_vector"):
            if saved_delivery.get(key) != expected.get(key):
                raise ValueError("replay_saved_social_delivery_projection_mismatch")
    presence_events = [event for event in store.read_events()
                       if event.event_type in _PRESENCE_EVENT_TYPES
                       and (boundary_sequence is None or event.global_sequence <= boundary_sequence)]
    saved_presence = manifest.get("presence")
    if presence_events and saved_presence is None:
        raise ValueError("replay_presence_participant_scope_mismatch")
    if saved_presence is not None:
        if (presence_authority is None and not presence_events
                and saved_presence == dict(schema_version=1, scope="project:population-presence",
                                           rows=[], event_refs=[], view_digest=_digest([]),
                                           reconstruction_api="PopulationPresenceAuthority.projection")):
            return manifest
        if presence_authority is None or getattr(presence_authority, "store", None) is not store:
            raise ValueError("replay_presence_participant_missing")
        if saved_presence.get("schema_version") != 1 or saved_presence.get("scope") != "project:population-presence":
            raise ValueError("replay_presence_decoder_unsupported")
        expected = _presence_participant(store, presence_authority, boundary_sequence=boundary_sequence)
        if expected is None or saved_presence.get("event_refs") != expected.get("event_refs"):
            raise ValueError("replay_saved_presence_event_scope_mismatch")
        if saved_presence.get("rows") != expected.get("rows") or saved_presence.get("view_digest") != expected.get("view_digest"):
            raise ValueError("replay_saved_presence_projection_mismatch")
    return manifest
