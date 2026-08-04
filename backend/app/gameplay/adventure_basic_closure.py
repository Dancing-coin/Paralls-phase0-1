"""Replay-backed, read-only closure evidence for the five adventure-basic scenarios."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
from typing import Any

from pydantic import BaseModel

from app.gameplay.ability_runtime import AbilityStateProjector
from app.gameplay.adventure_basic_reference import (
    AdventureBasicScenario1,
    AdventureBasicScenario2,
    AdventureBasicScenario3,
    AdventureBasicScenario4,
    AdventureBasicScenario5,
)
from app.gameplay.contract_runtime import ContractProjector
from app.gameplay.credential_runtime import CredentialProjector
from app.gameplay.debt_runtime import DebtProjector
from app.gameplay.economy_runtime import EconomyProjector
from app.gameplay.equipment_runtime import EquipmentProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryProjector
from app.gameplay.modifier_runtime import ModifierStateProjector
from app.gameplay.models import GameplayEvent, ProjectionCheckpoint
from app.gameplay.ownership_runtime import OwnershipProjector
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector


Scenario = (
    AdventureBasicScenario1
    | AdventureBasicScenario2
    | AdventureBasicScenario3
    | AdventureBasicScenario4
    | AdventureBasicScenario5
)


@dataclass(frozen=True)
class AdventureBasicClosureEvidence:
    """Correlated read-only proof for one authoritative scenario event stream."""

    scenario_id: str
    source_revision_vector: dict[str, int]
    result_metadata: dict[str, object]
    explanation_trace: tuple[dict[str, object], ...]
    online_facade: dict[str, object]
    full_replay_facade: dict[str, object]
    checkpoint_tail_facade: dict[str, object]
    checkpoint_tail_event_ids: tuple[str, ...]
    online_facade_hash: str
    full_replay_facade_hash: str
    checkpoint_tail_facade_hash: str
    online_replay_hash: str
    full_replay_hash: str
    checkpoint_tail_replay_hash: str


def capture_adventure_basic_closure(
    *,
    scenario_id: str,
    scenario: Scenario,
) -> AdventureBasicClosureEvidence:
    """Rebuild one scenario from authoritative events without issuing a command.

    The online facade is reconstructed from the active authority store. The full
    replay facade comes from an exported-and-restored store snapshot, ensuring
    it cannot depend on mutable projector state. The checkpoint-tail proof uses
    the existing generic replay contract; its domain facade is then rebuilt from
    the same verified committed event sequence.
    """

    _require_scenario_match(scenario_id, scenario)
    online_events = tuple(scenario.store.read_events())
    if not online_events:
        raise ValueError("adventure_basic_closure_events_required")

    full_store = GameplayEventStore.from_snapshot(scenario.store.export_snapshot())
    full_events = tuple(full_store.read_events())
    replay = GameplayProjectionReplay(
        projector_id=f"adventure-basic:{scenario_id}",
        projector_version="v1",
    )
    online_replay = replay.full_replay(list(online_events))
    full_replay = replay.full_replay(list(full_events))
    if not online_replay.succeeded or not full_replay.succeeded:
        raise ValueError("adventure_basic_closure_replay_failed")

    checkpoint_index = max(1, len(full_events) // 2)
    checkpoint = replay.create_checkpoint(list(full_events[:checkpoint_index]))
    checkpoint_tail = replay.checkpoint_plus_tail_replay(
        checkpoint,
        list(full_events[checkpoint_index:]),
    )
    if not checkpoint_tail.succeeded:
        raise ValueError("adventure_basic_closure_checkpoint_replay_failed")

    online_facade = _build_domain_facade(scenario_id, scenario, online_events)
    full_facade = _build_domain_facade(scenario_id, scenario, full_events)
    checkpoint_tail_events = _reconstruct_checkpoint_tail_events(
        checkpoint=checkpoint,
        tail_events=full_events[checkpoint_index:],
        event_lookup={event.event_id: event for event in full_events},
    )
    checkpoint_tail_facade = _build_domain_facade(scenario_id, scenario, checkpoint_tail_events)
    transactions = scenario.store.read_transactions()
    return AdventureBasicClosureEvidence(
        scenario_id=scenario_id,
        source_revision_vector={
            stream_id: int(revision)
            for stream_id, revision in sorted(online_replay.source_revision_vector.items())
        },
        result_metadata=_result_metadata(transactions),
        explanation_trace=_explanation_trace(online_events),
        online_facade=online_facade,
        full_replay_facade=full_facade,
        checkpoint_tail_facade=checkpoint_tail_facade,
        checkpoint_tail_event_ids=tuple(event.event_id for event in checkpoint_tail_events),
        online_facade_hash=_canonical_hash(online_facade),
        full_replay_facade_hash=_canonical_hash(full_facade),
        checkpoint_tail_facade_hash=_canonical_hash(checkpoint_tail_facade),
        online_replay_hash=online_replay.projection_hash,
        full_replay_hash=full_replay.projection_hash,
        checkpoint_tail_replay_hash=checkpoint_tail.projection_hash,
    )


def _reconstruct_checkpoint_tail_events(
    *,
    checkpoint: ProjectionCheckpoint,
    tail_events: Sequence[GameplayEvent],
    event_lookup: Mapping[str, GameplayEvent],
) -> tuple[GameplayEvent, ...]:
    """Recover the exact event sequence represented by a checkpoint plus tail.

    The generic replay checkpoint stores projection state, not each domain's
    materialized facade. Domain evidence must therefore rebuild from the
    checkpoint's audited event prefix and the verified post-checkpoint tail,
    rather than quietly reuse the full-store event tuple.
    """

    prefix: list[GameplayEvent] = []
    for event_id in checkpoint.applied_event_ids:
        event = event_lookup.get(event_id)
        if event is None:
            raise ValueError("adventure_basic_closure_checkpoint_event_missing")
        if event.global_sequence > checkpoint.last_global_sequence:
            raise ValueError("adventure_basic_closure_checkpoint_sequence_invalid")
        prefix.append(event)

    tail = tuple(tail_events)
    if any(event.global_sequence <= checkpoint.last_global_sequence for event in tail):
        raise ValueError("adventure_basic_closure_tail_sequence_invalid")

    reconstructed = tuple(sorted((*prefix, *tail), key=lambda event: event.global_sequence))
    actual_ids = tuple(event.event_id for event in reconstructed)
    expected_ids = set(checkpoint.applied_event_ids).union(event.event_id for event in tail)
    if set(actual_ids) != expected_ids or len(set(actual_ids)) != len(actual_ids):
        raise ValueError("adventure_basic_closure_checkpoint_tail_provenance_invalid")
    return reconstructed


def _require_scenario_match(scenario_id: str, scenario: Scenario) -> None:
    expected_types = {
        "scenario-1": AdventureBasicScenario1,
        "scenario-2": AdventureBasicScenario2,
        "scenario-3": AdventureBasicScenario3,
        "scenario-4": AdventureBasicScenario4,
        "scenario-5": AdventureBasicScenario5,
    }
    expected_type = expected_types.get(scenario_id)
    if expected_type is None or not isinstance(scenario, expected_type):
        raise ValueError("adventure_basic_closure_scenario_mismatch")


def _build_domain_facade(
    scenario_id: str,
    scenario: Scenario,
    events: Sequence[object],
) -> dict[str, object]:
    player_ref = scenario.player_ref
    inventory_projector = InventoryProjector(scenario.inventory_registry)
    inventory = inventory_projector.rebuild(player_ref, events)
    facade: dict[str, object] = {"inventory": _json_ready(inventory)}

    if scenario_id == "scenario-1":
        assert isinstance(scenario, AdventureBasicScenario1)
        facade.update(
            {
                "economy": _json_ready(EconomyProjector().rebuild(events)),
                "ownership": _json_ready(OwnershipProjector().rebuild(events)),
                "equipment": _json_ready(EquipmentProjector().rebuild(player_ref, events)),
                "abilities": _json_ready(AbilityStateProjector(scenario.ability_registry).rebuild(player_ref, events)),
                "modifiers": _json_ready(ModifierStateProjector(scenario.modifier_registry).rebuild(player_ref, events)),
            }
        )
    elif scenario_id == "scenario-2":
        assert isinstance(scenario, AdventureBasicScenario2)
        resource_body = ResourceBodyRuntimeProjector()
        facade.update(
            {
                "resources": _json_ready(resource_body.rebuild_resources(player_ref, events)),
                "body": _json_ready(resource_body.rebuild_body(player_ref, events)),
                "abilities": _json_ready(AbilityStateProjector(scenario.ability_registry).rebuild(player_ref, events)),
                "equipment": _json_ready(EquipmentProjector().rebuild(player_ref, events)),
            }
        )
    elif scenario_id == "scenario-3":
        assert isinstance(scenario, AdventureBasicScenario3)
        equipment = EquipmentProjector().rebuild(player_ref, events)
        active = next(
            (
                activation
                for activation in equipment.activations.values()
                if activation.item_id == scenario.storage_ring_item_id
                and scenario.storage_ring_container_id in activation.container_access_container_ids
            ),
            None,
        )
        encumbrance = inventory_projector.rebuild_encumbrance(
            inventory,
            carrier_ref=player_ref,
            carried_container_ids=(scenario.player_backpack_id,),
            carried_item_ids=(scenario.storage_ring_item_id,) if active is not None else (),
        )
        facade.update(
            {
                "equipment": _json_ready(equipment),
                "storage_ring_access": _json_ready(
                    {
                        "active": active is not None,
                        "activation_id": "" if active is None else active.activation_id,
                        "container_id": "" if active is None else scenario.storage_ring_container_id,
                    }
                ),
                "encumbrance": _json_ready(encumbrance),
            }
        )
    elif scenario_id == "scenario-4":
        assert isinstance(scenario, AdventureBasicScenario4)
        facade.update(
            {
                "economy": _json_ready(EconomyProjector().rebuild(events)),
                "ownership": _json_ready(OwnershipProjector().rebuild(events)),
                "credentials": _json_ready(CredentialProjector().rebuild(events)),
            }
        )
    elif scenario_id == "scenario-5":
        assert isinstance(scenario, AdventureBasicScenario5)
        facade.update(
            {
                "recipient_inventory": _json_ready(
                    inventory_projector.rebuild(scenario.recipient_ref, events)
                ),
                "economy": _json_ready(EconomyProjector().rebuild(events)),
                "ownership": _json_ready(OwnershipProjector().rebuild(events)),
                "debt": _json_ready(DebtProjector().rebuild(events)),
                "contracts": _json_ready(ContractProjector().rebuild(events)),
            }
        )
    else:  # _require_scenario_match keeps this unreachable for public callers.
        raise ValueError("adventure_basic_closure_scenario_mismatch")
    return _json_ready(facade)


def _result_metadata(transactions: Sequence[object]) -> dict[str, object]:
    atomic = True
    transaction_ids: list[str] = []
    result_digests: list[str] = []
    for transaction in transactions:
        transaction_id = str(getattr(transaction, "transaction_id", ""))
        events = tuple(getattr(transaction, "events", ()))
        idempotency_record = getattr(transaction, "idempotency_record", None)
        atomic = atomic and bool(transaction_id) and bool(events) and idempotency_record is not None
        atomic = atomic and all(str(getattr(event, "transaction_id", "")) == transaction_id for event in events)
        transaction_ids.append(transaction_id)
        result_digests.append(str(getattr(transaction, "result_digest", "")))
    return {
        "transaction_count": len(transactions),
        "transaction_ids": tuple(transaction_ids),
        "result_digests": tuple(result_digests),
        "latest_transaction_id": transaction_ids[-1] if transaction_ids else "",
        "latest_result_digest": result_digests[-1] if result_digests else "",
        "all_transactions_atomic": atomic,
        "idempotency_replay_safe": atomic,
    }


def _explanation_trace(events: Sequence[object]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "source_ref": f"event:{event.event_id}",
            "transaction_id": event.transaction_id,
            "event_type": event.event_type,
            "stream_id": event.stream_id,
            "stream_revision": event.stream_revision,
            "global_sequence": event.global_sequence,
            "causation_id": event.causation_id,
            "correlation_id": event.correlation_id,
        }
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id))
    )


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(_json_ready(value), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _json_ready(value: object) -> Any:
    if isinstance(value, BaseModel):
        return _json_ready(value.model_dump(mode="json"))
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _json_ready(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (Decimal, date, datetime)):
        return str(value)
    if isinstance(value, Enum):
        return _json_ready(value.value)
    return value


__all__ = ["AdventureBasicClosureEvidence", "capture_adventure_basic_closure"]
