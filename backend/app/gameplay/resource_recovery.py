"""Confirmed Population world-time recovery for materialized resources."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector, ResourceDefinitionRegistry
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.world_runtime.temporal_contracts import verify_temporal_authorization


RECOVERY_PRINCIPAL = "resource_recovery_authority"


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _stream(actor_ref: str) -> str:
    return f"gameplay:resources:{actor_ref.removeprefix('character:')}"


class ResourceRecoveryAuthorityService:
    """Owner that derives recovery from committed materialization/recovery events."""

    def __init__(self, *, store: GameplayEventStore, definitions: ResourceDefinitionRegistry | None = None) -> None:
        self.store = store
        self.definitions = definitions

    def _validate_cadence(self, event: GameplayEvent, *, world_ref: str, timeline_ref: str) -> int:
        record = event.payload
        cadence = record.get("cadence")
        if event.event_type != "population.cadence.admitted" or not isinstance(cadence, dict):
            raise ValueError("resource_recovery_population_boundary_missing")
        if record.get("record_digest") != _digest({key: value for key, value in record.items() if key != "record_digest"}):
            raise ValueError("resource_recovery_population_record_tampered")
        if cadence.get("world_ref") != world_ref:
            raise ValueError("resource_recovery_population_scope_invalid")
        tick = cadence.get("window_end")
        pins = record.get("time_pins")
        if type(tick) is not int or not isinstance(pins, dict) or pins.get("timeline_id") != timeline_ref:
            raise ValueError("resource_recovery_temporal_pins_invalid")
        if not verify_temporal_authorization(pins=pins, expected_participant="actor_gameplay.inventory_domain",
                expected_cutoff=tick, expected_timeline=timeline_ref):
            raise ValueError("resource_recovery_temporal_authorization_rejected")
        if pins.get("temporal_authorization_issuer_ref") != f"world_runtime.population_cadence:{world_ref}" or not verify_temporal_authorization(
                pins=pins, expected_participant="actor_gameplay.resource_domain", expected_cutoff=tick,
                expected_timeline=timeline_ref, grant_key="resource"):
            raise ValueError("resource_recovery_temporal_authorization_rejected")
        receipt = self.store.get_by_idempotency("world_runtime.cadence", f"population-runtime:{cadence.get('cadence_id')}")
        if receipt is None or not receipt.committed or receipt.committed_event_ids != [event.event_id]:
            raise ValueError("resource_recovery_population_receipt_invalid")
        delivered = self.store.list_outbox(topic="population_cadence_event", transaction_id=event.transaction_id)
        if len(delivered) != 1 or delivered[0].event_id != event.event_id or delivered[0].delivery_state != "delivered":
            raise ValueError("resource_recovery_population_not_confirmed")
        revocations = self.store.read_stream(f"population-cadence-revocation:{world_ref}")
        if any(item.payload.get("source_cadence_event_id") == event.event_id for item in revocations):
            raise ValueError("resource_recovery_population_revoked")
        return tick

    def recover(
        self, *, actor_ref: str, world_ref: str, timeline_ref: str, confirmed_world_tick: int,
        idempotency_key: str, expected_revision: int,
        read_stream_revisions: dict[str, int] | None = None,
    ) -> AppendBatchResult:
        if type(confirmed_world_tick) is not int or confirmed_world_tick < 0:
            raise ValueError("resource_recovery_tick_invalid")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("resource_recovery_revision_invalid")
        if not all(isinstance(value, str) and value for value in (actor_ref, world_ref, timeline_ref, idempotency_key)):
            raise ValueError("resource_recovery_identity_invalid")
        actor = actor_ref.removeprefix("character:")
        stream = _stream(actor)
        cadence_stream = f"population-cadence:{world_ref}"
        revocation_stream = f"population-cadence-revocation:{world_ref}"
        prior = self.store.get_by_idempotency(RECOVERY_PRINCIPAL, idempotency_key)
        cadence_head = self.store.get_stream_head(cadence_stream)
        revocation_head = self.store.get_stream_head(revocation_stream)
        latest = self.store.read_stream(cadence_stream)[-1] if cadence_head else None
        if latest is None or latest.event_type != "population.cadence.admitted":
            raise ValueError("resource_recovery_population_boundary_missing")
        confirmed = self._validate_cadence(latest, world_ref=world_ref, timeline_ref=timeline_ref)
        if confirmed < confirmed_world_tick:
            raise ValueError("resource_recovery_tick_not_confirmed")
        if prior is None and confirmed != confirmed_world_tick:
            raise ValueError("resource_recovery_tick_not_latest_confirmed")
        pins = latest.payload.get("time_pins")
        required_pin_keys = ("sampled_at", "received_at", "input_cutoff", "confirmation_boundary", "temporal_authorization_digest")
        if not isinstance(pins, dict) or any(key not in pins for key in required_pin_keys):
            raise ValueError("resource_recovery_temporal_pins_missing")
        if any(type(pins.get(key)) is not int for key in required_pin_keys[:4]) or not isinstance(pins.get(required_pin_keys[4]), str):
            raise ValueError("resource_recovery_temporal_pins_invalid")
        if any(pins[key] != confirmed for key in required_pin_keys[:4]):
            raise ValueError("resource_recovery_temporal_boundary_mismatch")
        if pins.get("timeline_id") != timeline_ref:
            raise ValueError("resource_recovery_timeline_scope_invalid")
        if not verify_temporal_authorization(
            pins=pins, expected_participant="actor_gameplay.resource_domain",
            expected_cutoff=confirmed, expected_timeline=timeline_ref, grant_key="resource",
        ):
            raise ValueError("resource_recovery_temporal_authorization_rejected")
        read_set = dict(read_stream_revisions or {})
        if any(type(value) is not int or value < 0 for value in read_set.values()):
            raise ValueError("resource_recovery_read_set_invalid")
        if prior is not None:
            prior_tx = self.store.get_transaction(prior.transaction_id)
            if prior_tx is None:
                # Preserve changed-duplicate semantics even when the transaction
                # record itself is gone, while failing closed for same-argument
                # retries whose receipt can no longer be verified.
                original_revision = None
                for event_id in prior.committed_event_ids:
                    event = self.store.get_event(event_id)
                    if event is None:
                        continue
                    candidate = event.payload.get("expected_resource_revision")
                    if type(candidate) is int:
                        original_revision = candidate
                        break
                if original_revision is not None and original_revision != expected_revision:
                    raise ValueError("idempotency_key_reused")
                raise ValueError("resource_recovery_receipt_incomplete")
            if prior_tx.expected_stream_revisions != {stream: expected_revision}:
                raise ValueError("idempotency_key_reused")
            prior_events = self._verified_receipt_events(prior, actor=actor, key=idempotency_key,
                                                        expected_revision=expected_revision)
            original = next((event.payload for event in prior_events if event.event_type == "gameplay.resource.recovered"), None)
            if original is None or original.get("actor_ref") != actor or original.get("world_ref") != world_ref or original.get("timeline_ref") != timeline_ref or original.get("confirmed_world_tick") != confirmed_world_tick:
                raise ValueError("idempotency_key_reused")
            if original.get("caller_read_stream_revisions") != (read_stream_revisions or {}):
                raise ValueError("idempotency_key_reused")
            if original.get("expected_resource_revision") != expected_revision:
                raise ValueError("idempotency_key_reused")
            original_cadence = self.store.get_event(original["cadence_event_id"])
            if self._validate_cadence(original_cadence, world_ref=world_ref, timeline_ref=timeline_ref) != confirmed_world_tick:
                raise ValueError("resource_recovery_original_cadence_invalid")
            resource_events = self.store.read_stream(stream)
            original_boundaries = original.get("modifier_effective_boundaries")
            if not isinstance(original_boundaries, list):
                raise ValueError("resource_recovery_modifier_boundary_receipt_invalid")
            original_transaction_cut = min((event.global_sequence for event in prior_events), default=None)
            if original_transaction_cut is None:
                raise ValueError("resource_recovery_modifier_boundary_receipt_invalid")
            recovered_resource_id = original.get("resource_id")
            expected_boundaries = []
            for resource_event in resource_events:
                if (resource_event.event_type not in {"gameplay.resource.modifier_attached", "gameplay.resource.modifier_detached"}
                        or resource_event.payload.get("resource_id") != recovered_resource_id
                        or resource_event.global_sequence >= original_transaction_cut):
                    continue
                modifier = resource_event.payload.get("modifier")
                if not isinstance(modifier, dict) or modifier.get("operation") != "recovery_delta" or modifier.get("effective_world_tick") is not None:
                    continue
                _, boundary = self._equipment_modifier_effective_tick(
                    resource_event, actor_ref=actor, world_ref=world_ref, timeline_ref=timeline_ref,
                    cadence_stream=cadence_stream,
                )
                expected_boundaries.append(boundary)
            if sorted(original_boundaries, key=lambda item: item.get("resource_event_id", "")) != sorted(expected_boundaries, key=lambda item: item["resource_event_id"]):
                raise ValueError("resource_recovery_modifier_boundary_receipt_invalid")
            return prior.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
        if read_set.get(cadence_stream, cadence_head) != cadence_head:
            raise ValueError("resource_recovery_cadence_revision_conflict")
        if read_set.get(revocation_stream, revocation_head) != revocation_head:
            raise ValueError("resource_recovery_revocation_revision_conflict")
        read_set[cadence_stream] = cadence_head
        read_set[revocation_stream] = revocation_head
        request = {"actor_ref": actor, "world_ref": world_ref, "timeline_ref": timeline_ref,
                   "confirmed_world_tick": confirmed_world_tick, "cadence_event_id": latest.event_id,
                   "cadence_revision": cadence_head, "read_stream_revisions": read_set}
        request_digest = _digest(request)
        events = self.store.read_stream(stream)
        materialized = [event for event in events if event.event_type == "gameplay.resource.materialized"]
        if not materialized:
            raise ValueError("resource_recovery_before_materialization")
        if self.store.get_stream_head(stream) != expected_revision:
            raise ValueError("resource_recovery_revision_conflict")
        projection = ResourceBodyRuntimeProjector(resource_definitions=self.definitions).rebuild_resources(actor, events)
        specs: list[tuple[str, dict[str, Any]]] = []
        for event in materialized:
            payload = event.payload
            resource_id = payload.get("resource_id")
            if payload.get("world_ref") != world_ref or payload.get("timeline_ref") != timeline_ref:
                raise ValueError("resource_recovery_materialization_scope_invalid")
            period = payload.get("recovery_period_world_ticks")
            amount = payload.get("recovery_amount")
            if type(period) is not int or period <= 0 or type(amount) is not int or amount < 0:
                raise ValueError("resource_recovery_policy_invalid")
            last_tick = payload.get("materialized_world_tick")
            applied = [e for e in events if e.event_type == "gameplay.resource.recovered"
                       and e.payload.get("resource_id") == resource_id]
            for recovered in applied:
                record = recovered.payload
                through = record.get("applied_through_world_tick")
                recovery_boundary = record.get("confirmed_world_tick")
                if (type(through) is not int or through < 0 or type(recovery_boundary) is not int
                        or recovery_boundary < through or recovery_boundary > confirmed_world_tick
                        or record.get("actor_ref") != actor or record.get("world_ref") != world_ref
                        or record.get("timeline_ref") != timeline_ref):
                    raise ValueError("resource_recovery_history_invalid")
            if applied:
                last_tick = max(last_tick, max(e.payload["applied_through_world_tick"] for e in applied))
            if type(last_tick) is not int or last_tick < 0 or last_tick > confirmed_world_tick:
                raise ValueError("resource_recovery_materialization_invalid")
            history = [e for e in events if e.payload.get("resource_id") == resource_id
                       and e.event_type in {"gameplay.resource.modifier_attached", "gameplay.resource.modifier_detached"}]
            active: dict[str, dict[str, Any]] = {}
            changes: list[tuple[int, int, str, dict[str, Any]]] = []
            lifecycle_ticks: dict[str, tuple[int, bool]] = {}
            effective_boundaries: list[dict[str, Any]] = []
            for modifier_event in history:
                modifier = modifier_event.payload.get("modifier")
                if not isinstance(modifier, dict) or modifier.get("operation") != "recovery_delta":
                    continue
                effective = modifier.get("effective_world_tick")
                if modifier_event.event_type == "gameplay.resource.modifier_attached" and effective is None:
                    effective, boundary = self._equipment_modifier_effective_tick(
                        modifier_event, actor_ref=actor, world_ref=world_ref, timeline_ref=timeline_ref,
                        cadence_stream=cadence_stream,
                    )
                    effective_boundaries.append(boundary)
                elif modifier_event.event_type == "gameplay.resource.modifier_detached":
                    # Detach timing belongs to the lifecycle event. A legacy or
                    # hand-authored detach without a pinned time is invalid;
                    # bridge events may derive it from their Equipment source.
                    detach_tick = modifier_event.payload.get("effective_world_tick")
                    if detach_tick is None:
                        # Bridge provenance is carried on the resource event;
                        # the nested modifier is only the semantic mapping.
                        if not modifier_event.payload.get("source_transaction_id"):
                            raise ValueError("resource_recovery_modifier_temporal_contract_required")
                        detach_tick, boundary = self._equipment_modifier_effective_tick(
                            modifier_event, actor_ref=actor, world_ref=world_ref, timeline_ref=timeline_ref,
                            cadence_stream=cadence_stream,
                        )
                        effective_boundaries.append(boundary)
                    effective = detach_tick
                if type(effective) is not int or effective < 0:
                    raise ValueError("resource_recovery_modifier_temporal_contract_required")
                if modifier_event.event_type == "gameplay.resource.modifier_attached":
                    state = lifecycle_ticks.get(str(modifier["modifier_ref"]))
                    if state is not None and (state[1] or effective < state[0]):
                        raise ValueError("resource_recovery_modifier_history_invalid")
                    lifecycle_ticks[str(modifier["modifier_ref"])] = (effective, True)
                    changes.append((effective, modifier_event.global_sequence, "attach", modifier))
                else:
                    detach_tick = effective
                    if type(detach_tick) is not int or detach_tick < 0:
                        raise ValueError("resource_recovery_modifier_temporal_contract_required")
                    state = lifecycle_ticks.get(str(modifier["modifier_ref"]))
                    if state is None or not state[1] or detach_tick < state[0]:
                        raise ValueError("resource_recovery_modifier_history_invalid")
                    lifecycle_ticks[str(modifier["modifier_ref"])] = (detach_tick, False)
                    changes.append((detach_tick, modifier_event.global_sequence, "detach", modifier))
            changes.sort(key=lambda item: (item[0], item[1]))
            for tick, _, operation, modifier in changes:
                if tick <= last_tick:
                    if operation == "attach":
                        active[str(modifier["modifier_ref"])] = modifier
                    else:
                        active.pop(str(modifier["modifier_ref"]), None)
            periods = (confirmed_world_tick - last_tick) // period
            if periods <= 0:
                continue
            current = projection.entries[resource_id].current
            entry = projection.entries[resource_id]
            maximum = min(entry.capacity, entry.maximum) if entry.capacity is not None else entry.maximum
            if type(current) is not int or type(maximum) is not int:
                raise ValueError("resource_recovery_materialization_invalid")
            gain = 0
            cursor = 1
            effective_changes: dict[int, list[tuple[str, dict[str, Any]]]] = {}
            for tick, _, operation, modifier in changes:
                if tick <= last_tick:
                    continue
                index = max(1, (tick - last_tick + period - 1) // period)
                if index <= periods:
                    effective_changes.setdefault(index, []).append((operation, modifier))
            for index, operations in sorted(effective_changes.items()):
                if index > cursor:
                    gain += (index - cursor) * max(0, amount + sum(int(item["amount"]) for item in active.values()))
                for operation, modifier in operations:
                    if operation == "attach":
                        active[str(modifier["modifier_ref"])] = modifier
                    else:
                        active.pop(str(modifier["modifier_ref"]), None)
                cursor = index
            if cursor <= periods:
                gain += (periods - cursor + 1) * max(0, amount + sum(int(item["amount"]) for item in active.values()))
            delta = min(gain, max(0, maximum - current))
            through = last_tick + periods * period
            specs.append(("gameplay.resource.recovered", {"actor_ref": actor, "resource_id": resource_id,
                "delta": delta, "periods": periods, "recovery_amount": amount,
                "recovery_period_world_ticks": period, "applied_through_world_tick": through,
                "confirmed_world_tick": confirmed_world_tick, "world_ref": world_ref,
                "timeline_ref": timeline_ref, "cadence_event_id": latest.event_id,
                "resource_schema": "resource.v2" if entry.capacity is not None else "legacy-v0",
                "capacity": maximum,
                "debt": entry.debt,
                "modifier_effective_boundaries": sorted(effective_boundaries, key=lambda item: item["resource_event_id"]),
                "caller_read_stream_revisions": dict(read_stream_revisions or {}),
                "expected_resource_revision": expected_revision,
                "request_digest": request_digest}))
        if not specs:
            # Preserve a receipt without inventing a zero-value domain event.
            raise ValueError("resource_recovery_no_complete_period")
        command_id = f"resource-recover:{actor}:{idempotency_key}"
        batch = build_multi_stream_atomic_event_batch(
            command_id=command_id, principal_ref=RECOVERY_PRINCIPAL,
            expected_revisions={stream: expected_revision}, event_specs={stream: specs},
            idempotency_key=idempotency_key, causation_id=f"cause:{command_id}",
            correlation_id=f"correlation:{command_id}", read_stream_revisions=read_set,
            event_visibility_policies={stream: ["authority_only"] * len(specs)},
        )
        return self.store.append_batch(batch)

    def _verified_receipt_events(self, receipt: AppendBatchResult, *, actor: str,
                                 key: str, expected_revision: int) -> list[GameplayEvent]:
        """Verify every resource in an owner batch before returning a duplicate."""
        invalid = "resource_recovery_receipt_incomplete"
        tx = self.store.get_transaction(receipt.transaction_id)
        command = f"resource-recover:{actor}:{key}"
        stream = _stream(actor)
        if (not receipt.committed or receipt.failure is not None or tx is None
                or tx.command_id != command or receipt.command_id != command
                or tx.idempotency_record.principal_ref != RECOVERY_PRINCIPAL
                or tx.idempotency_record.idempotency_key != key
                or tx.expected_stream_revisions != {stream: expected_revision}
                or receipt.committed_event_ids != [event.event_id for event in tx.events]):
            raise ValueError(invalid)
        events = tx.events
        try:
            if any(event != self.store.get_event(event.event_id)
                   or event.event_type != "gameplay.resource.recovered" or event.schema_version != 1
                   or event.stream_id != stream or event.transaction_id != tx.transaction_id
                   or event.command_id != command or event.causation_id != f"cause:{command}"
                   or event.correlation_id != f"correlation:{command}"
                   or event.visibility_policy != "authority_only"
                   or event.stream_revision != expected_revision + index + 1
                   or event.global_sequence != events[0].global_sequence + index
                   or event.payload.get("actor_ref") != actor
                   for index, event in enumerate(events)):
                raise ValueError(invalid)
        except KeyError as exc:
            raise ValueError(invalid) from exc
        canonical = build_multi_stream_atomic_event_batch(
            command_id=command, principal_ref=RECOVERY_PRINCIPAL,
            expected_revisions=tx.expected_stream_revisions,
            event_specs={stream: [(event.event_type, event.payload) for event in events]},
            idempotency_key=key, causation_id=f"cause:{command}", correlation_id=f"correlation:{command}",
            read_stream_revisions=tx.read_stream_revisions, pinned_revisions=tx.pinned_revisions,
            event_visibility_policies={stream: ["authority_only"] * len(events)},
        )
        if (tx.result_digest != canonical.result_digest
                or tx.idempotency_record != canonical.idempotency_record
                or receipt.resulting_stream_revisions != {stream: events[-1].stream_revision}
                or receipt.global_sequence_range != (events[0].global_sequence, events[-1].global_sequence)
                or [event.event_id for event in events] != [event.event_id for event in canonical.events]):
            raise ValueError(invalid)
        return events

    def _equipment_modifier_effective_tick(
        self, resource_event: GameplayEvent, *, actor_ref: str, world_ref: str, timeline_ref: str,
        cadence_stream: str,
    ) -> tuple[int, dict[str, Any]]:
        """An equipment source starts at the first confirmed Population boundary after its commit."""
        payload = resource_event.payload
        source_transaction_id = payload.get("source_transaction_id")
        source_event_id = payload.get("source_event_id")
        modifier = payload.get("modifier")
        if not isinstance(source_transaction_id, str) or not isinstance(source_event_id, str) or not isinstance(modifier, dict):
            raise ValueError("resource_recovery_modifier_temporal_contract_required")
        source = self.store.get_transaction(source_transaction_id)
        if source is None or source.idempotency_record.principal_ref != "actor_gameplay.equipment_domain":
            raise ValueError("resource_recovery_modifier_source_authority_invalid")
        receipt = self.store.get_by_idempotency(source.idempotency_record.principal_ref, source.idempotency_record.idempotency_key)
        if (receipt is None or not receipt.committed or receipt.transaction_id != source_transaction_id
                or receipt.committed_event_ids != [item.event_id for item in source.events]):
            raise ValueError("resource_recovery_modifier_source_receipt_invalid")
        source_event = next((item for item in source.events if item.event_id == source_event_id), None)
        expected_type = "gameplay.modifier.source_activated" if resource_event.event_type == "gameplay.resource.modifier_attached" else "gameplay.modifier.source_deactivated"
        if (source_event is None or source_event.event_type != expected_type
                or source_event.stream_id != f"gameplay:modifiers:{actor_ref}"
                or source_event.payload.get("actor_ref") != actor_ref
                or source_event.payload.get("modifier_instance_id") != modifier.get("modifier_ref")):
            raise ValueError("resource_recovery_modifier_source_event_invalid")
        if source_event.event_type == "gameplay.modifier.source_activated" and source_event.payload.get("template_id") != modifier.get("template_id"):
            raise ValueError("resource_recovery_modifier_template_drift")
        source_end = max((item.global_sequence for item in source.events), default=-1)
        boundaries = self.store.read_stream(cadence_stream)
        candidate = next((item for item in boundaries if item.global_sequence > source_end), None)
        if candidate is None:
            raise ValueError("resource_recovery_modifier_boundary_missing")
        tick = self._validate_cadence(candidate, world_ref=world_ref, timeline_ref=timeline_ref)
        revocation_stream = f"population-cadence-revocation:{world_ref}"
        if any(item.payload.get("source_cadence_event_id") == candidate.event_id for item in self.store.read_stream(revocation_stream)):
            raise ValueError("resource_recovery_modifier_boundary_revoked")
        return tick, {
            "resource_event_id": resource_event.event_id,
            "source_event_id": source_event_id,
            "source_transaction_id": source_transaction_id,
            "source_transaction_last_global_sequence": source_end,
            "cadence_event_id": candidate.event_id,
            "cadence_transaction_id": candidate.transaction_id,
            "cadence_global_sequence": candidate.global_sequence,
            "effective_world_tick": tick,
        }


class PopulationResourceRecoveryCaller:
    """Read-only caller: takes the confirmed boundary from Population cadence."""

    def __init__(self, *, authority: ResourceRecoveryAuthorityService) -> None:
        self.authority = authority

    def recover(self, **kwargs: Any) -> AppendBatchResult:
        return self.authority.recover(**kwargs)


__all__ = ["PopulationResourceRecoveryCaller", "ResourceRecoveryAuthorityService"]
