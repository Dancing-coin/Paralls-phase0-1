"""Rebuild cross-host impact_gate progress from durable Owner receipts."""
from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent


FACILITY_PRINCIPAL = "actor_gameplay.construction_production_domain"
PRESENCE_PRINCIPAL = "population.presence_authority"
IMPACT_EVENT = "gameplay.facility.gate_impact_input_received@2"
PRESENCE_INPUT_EVENT = "gameplay.presence.assessment_input_received"
PLACE_EVENT = "gameplay.presence.place_passability_changed"


@dataclass(frozen=True)
class ImpactGateObligation:
    obligation_id: str
    gate_ref: str
    status: str
    step_receipts: tuple[tuple[str, tuple[str, ...]], ...]


def rebuild_impact_gate_obligations(
    store: GameplayEventStore,
) -> tuple[ImpactGateObligation, ...]:
    """Project open/settled obligations without writing a workflow ledger."""
    events = store.read_events()
    impacts = [
        event for event in events
        if event.event_type == IMPACT_EVENT
        and store.transaction_owns_event(
            transaction_id=event.transaction_id,
            event_id=event.event_id,
            principal_ref="authority:siege:physical-input",
        )
    ]
    facility_by_impact: dict[str, list[GameplayEvent]] = {}
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
                principal_ref=FACILITY_PRINCIPAL,
            )
        ):
            facility_by_impact.setdefault(event.causation_id, []).append(event)

    obligations = []
    for impact in impacts:
        facility_events = facility_by_impact.get(impact.event_id, [])
        breach_ids = {
            event.event_id for event in facility_events
            if event.event_type == "gameplay.pool.threshold_crossed"
            and event.payload.get("direction") == "enter"
            and event.payload.get("threshold_ref") == "breach"
        }
        presence_inputs = [
            event for event in events
            if event.event_type == PRESENCE_INPUT_EVENT
            and isinstance(event.payload.get("receipt"), dict)
            and event.payload["receipt"].get("breach_event_id") in breach_ids
            and store.transaction_owns_event(
                transaction_id=event.transaction_id,
                event_id=event.event_id,
                principal_ref="authority:siege:physical-input",
            )
        ]
        place_events = [
            event for event in events
            if event.event_type == PLACE_EVENT
            and event.causation_id in breach_ids
            and store.transaction_owns_event(
                transaction_id=event.transaction_id,
                event_id=event.event_id,
                principal_ref=PRESENCE_PRINCIPAL,
            )
        ]
        receipts = (
            ("impact", (impact.event_id,)),
            ("facility", tuple(event.event_id for event in facility_events)),
            ("presence_input", tuple(event.event_id for event in presence_inputs)),
            ("passability", tuple(event.event_id for event in place_events)),
        )
        obligations.append(ImpactGateObligation(
            obligation_id=f"impact_gate:{impact.event_id}",
            gate_ref=str(impact.payload["gate_ref"]),
            status="settled" if place_events else "open",
            step_receipts=receipts,
        ))
    return tuple(obligations)
