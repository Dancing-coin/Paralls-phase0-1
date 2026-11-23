"""Production dispatch wiring for the M6-5 Morale and Presence commands."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Callable

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.l5_dispatch_runtime import (
    L5ReactionDispatcher,
    TriggeredGameplayCommand,
    TrustedGameplayCommandGateway,
)
from app.gameplay.models import AtomicEventBatch, GameplayEvent
from app.gameplay.morale_refold_runtime import MoraleRefoldAuthority
from app.gameplay.place_passability_runtime import (
    PlacePassabilityAssessment,
    PlacePassabilityAuthority,
)
from app.gameplay.pool_runtime import PoolDefinition
from app.gameplay.rule_pack_validator import load_pack


M6_5_PACK = Path(__file__).resolve().parents[3] / "packs" / "county_siege_morale_presence"
MORALE_OWNER_DOMAINS = {
    "Morale": "morale",
    "Presence": "presence",
}
DEFAULT_MORALE_DEFINITIONS = MappingProxyType({
    ("organization:garrison:east@1", "role:garrison-defender@1"): PoolDefinition(
        fact_type="fact:unit:garrison-east:morale",
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal("100"),
        aggregation_mode="distribution",
        refold_model_ref="morale_refold@1",
    ),
})
PlaceResolver = Callable[
    [str, GameplayEvent], PlacePassabilityAssessment | None
]


@dataclass(frozen=True)
class M6_5SiegeRuntime:
    morale: MoraleRefoldAuthority
    presence: PlacePassabilityAuthority
    dispatcher: L5ReactionDispatcher

    def after_transaction_dispatched(
        self, transaction: AtomicEventBatch
    ) -> tuple[object, ...]:
        return self.dispatcher.after_transaction_dispatched(transaction)


def build_m6_5_siege_runtime(
    *,
    store: GameplayEventStore,
    morale_definitions: Mapping[tuple[str, str], PoolDefinition],
    presence_resolver: PlaceResolver | None = None,
    evidence_event_principals: Mapping[str, str] | None = None,
) -> M6_5SiegeRuntime:
    morale = MoraleRefoldAuthority(store=store, definitions=morale_definitions)
    presence = PlacePassabilityAuthority(
        store=store,
        resolver=presence_resolver,
        evidence_event_principals=evidence_event_principals,
    )
    command_outputs = {
        "morale.refold": {definition.fact_type for definition in morale_definitions.values()},
        "presence.reevaluate": {presence.stream_id("gate-03")},
    }
    pack = load_pack(
        M6_5_PACK,
        handlers={},
        owner_domains=MORALE_OWNER_DOMAINS,
        command_fact_outputs=command_outputs,
    )
    gateway = TrustedGameplayCommandGateway(
        handlers={
            "morale.refold": lambda command: morale.refold_after_casualty(
                death_event_id=command.trigger_event.event_id,
            ),
            "presence.reevaluate": lambda command: presence.commit_assessment(
                gate_ref=str(command.target["scope"]),
                breach_event_id=command.trigger_event.event_id,
                expected_revision=store.get_stream_head(
                    presence.stream_id(str(command.target["scope"]))
                ),
            ),
        },
        command_fact_outputs=command_outputs,
    )
    dispatcher = L5ReactionDispatcher(
        reactions=tuple(pack.reactions.values()),
        gateway=gateway,
        fact_type_for=_fact_type_for,
        conditions={"facility_breach@1": _is_breach_entry},
    )
    return M6_5SiegeRuntime(morale=morale, presence=presence, dispatcher=dispatcher)


def _fact_type_for(event: GameplayEvent) -> str | None:
    fact_type = event.payload.get("fact_type")
    if isinstance(fact_type, str):
        return fact_type
    actor_ref = event.payload.get("actor_ref")
    if event.event_type == "gameplay.character.life_state_changed" and isinstance(actor_ref, str):
        return f"fact:character:{actor_ref}:lifestate"
    return None


def _is_breach_entry(event: GameplayEvent) -> bool:
    return (
        event.payload.get("threshold_ref") == "breach"
        and event.payload.get("direction") == "enter"
    )
