"""Rebuild cross-host impact_gate progress from durable Owner receipts."""
from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent
from app.gameplay.place_event_schema import PLACE_ASSESSMENT_CONFIRMED_EVENT
from app.gameplay.siege_physical_input_runtime import (
    FACILITY_GATE_PRINCIPAL,
    GateImpactReceiptV2,
    GATE_IMPACT_INPUT_EVENT_V2,
    PRESENCE_ASSESSMENT_INPUT_EVENT,
    PRESENCE_ASSESSMENT_INPUT_EVENT_V2,
    SIEGE_PHYSICAL_INPUT_PRINCIPAL,
)


PRESENCE_PRINCIPAL = "population.presence_authority"
PLACE_EVENT = "gameplay.presence.place_passability_changed"


@dataclass(frozen=True)
class ImpactGateObligation:
    obligation_id: str
    gate_ref: str
    status: str
    step_receipts: tuple[tuple[str, tuple[str, ...]], ...]
    pipeline_ref: str
    completed_steps: tuple[str, ...]
    pending_steps: tuple[str, ...]
    pending_reason: str | None
    owner_refs: tuple[str, ...]
    recovery_action: str | None
    deadline_world_tick: int | None
    input_revision_vector: tuple[tuple[str, int], ...]


def rebuild_impact_gate_obligations(
    store: GameplayEventStore,
) -> tuple[ImpactGateObligation, ...]:
    """Project open/settled obligations without writing a workflow ledger."""
    events = store.read_events()
    impacts = [
        event for event in events
        if event.event_type == GATE_IMPACT_INPUT_EVENT_V2
        and store.transaction_owns_event(
            transaction_id=event.transaction_id,
            event_id=event.event_id,
            principal_ref=SIEGE_PHYSICAL_INPUT_PRINCIPAL,
        )
    ]
    facility_by_impact: dict[str, list[GameplayEvent]] = {}
    input_by_source: dict[str, list[GameplayEvent]] = {}
    result_by_source: dict[str, list[GameplayEvent]] = {}
    for event in events:
        if (
            event.causation_id
            and event.event_type in {
                "gameplay.pool.adjusted",
                "gameplay.pool.threshold_crossed",
                "gameplay.machine.transitioned",
            }
            and store.transaction_owns_event(
                transaction_id=event.transaction_id,
                event_id=event.event_id,
                principal_ref=FACILITY_GATE_PRINCIPAL,
            )
        ):
            facility_by_impact.setdefault(event.causation_id, []).append(event)
        if event.event_type in {PRESENCE_ASSESSMENT_INPUT_EVENT, PRESENCE_ASSESSMENT_INPUT_EVENT_V2}:
            receipt = event.payload.get("receipt")
            if isinstance(receipt, dict) and store.transaction_owns_event(
                transaction_id=event.transaction_id,
                event_id=event.event_id,
                principal_ref=SIEGE_PHYSICAL_INPUT_PRINCIPAL,
            ):
                field = (
                    "impact_event_id" if event.event_type == PRESENCE_ASSESSMENT_INPUT_EVENT_V2
                    else "breach_event_id"
                )
                source_id = receipt.get(field)
                if isinstance(source_id, str):
                    input_by_source.setdefault(source_id, []).append(event)
        if (
            event.causation_id
            and event.event_type in {PLACE_EVENT, PLACE_ASSESSMENT_CONFIRMED_EVENT}
            and store.transaction_owns_event(
                transaction_id=event.transaction_id,
                event_id=event.event_id,
                principal_ref=PRESENCE_PRINCIPAL,
            )
        ):
            result_by_source.setdefault(event.causation_id, []).append(event)

    obligations = []
    for impact in impacts:
        facility_events = facility_by_impact.get(impact.event_id, [])
        source_ids = [impact.event_id, *(
            event.event_id for event in facility_events
            if event.event_type == "gameplay.pool.threshold_crossed"
            and event.payload.get("direction") == "enter"
            and event.payload.get("threshold_ref") == "breach"
        )]
        presence_inputs = sorted(
            (event for source in source_ids for event in input_by_source.get(source, ())),
            key=lambda event: event.global_sequence,
        )
        place_events = sorted(
            (event for source in source_ids for event in result_by_source.get(source, ())),
            key=lambda event: event.global_sequence,
        )
        receipts = (
            ("impact", (impact.event_id,)),
            ("facility", tuple(event.event_id for event in facility_events)),
            ("presence_input", tuple(event.event_id for event in presence_inputs)),
            ("passability", tuple(event.event_id for event in place_events)),
        )
        completed_steps = tuple(step for step, step_receipts in receipts if step_receipts)
        pending_steps = tuple(step for step, step_receipts in receipts if not step_receipts)
        pending_owner_by_step = {
            "facility": "Production",
            "presence_input": "Presence",
            "passability": "Presence",
        }
        pending_owners: list[str] = []
        for step in pending_steps:
            owner = pending_owner_by_step.get(step)
            if owner is not None and owner not in pending_owners:
                pending_owners.append(owner)
        owner_refs = tuple(pending_owners)
        settled = not pending_steps
        obligations.append(ImpactGateObligation(
            obligation_id=f"impact_gate:{impact.event_id}",
            gate_ref=str(impact.payload["gate_ref"]),
            status="settled" if settled else "open",
            step_receipts=receipts,
            pipeline_ref="impact_gate",
            completed_steps=completed_steps,
            pending_steps=pending_steps,
            pending_reason=None if settled else "unknown",
            owner_refs=owner_refs,
            recovery_action=None if settled else "reconcile",
            deadline_world_tick=None,
            input_revision_vector=_input_revision_vector(events, impact),
        ))
    return tuple(obligations)


def _input_revision_vector(
    events: list[GameplayEvent], impact: GameplayEvent,
) -> tuple[tuple[str, int], ...]:
    receipt = GateImpactReceiptV2.model_validate(impact.payload["receipt"])
    streams = {
        *receipt.expected_layer_revisions,
        f"place:{receipt.gate_ref}:passability",
    }
    revisions = {stream_id: 0 for stream_id in streams}
    for event in events:
        if event.global_sequence >= impact.global_sequence:
            continue
        if event.stream_id in revisions:
            revisions[event.stream_id] = event.stream_revision
    return tuple(sorted(revisions.items()))
