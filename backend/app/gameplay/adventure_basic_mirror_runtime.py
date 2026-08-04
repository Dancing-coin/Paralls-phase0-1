"""Outbox-backed runtime delivery for the five governed adventure-basic scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.gameplay.adventure_basic_mirror_source import AdventureBasicMirrorSource, Scenario
from app.gameplay.adventure_basic_reference import (
    AdventureBasicScenario1,
    AdventureBasicScenario2,
    AdventureBasicScenario3,
    AdventureBasicScenario4,
    AdventureBasicScenario5,
)
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.godot_mirror_delivery import GameplayGodotProjectionPublisher
from app.gameplay.models import AtomicEventBatch, GameplayOutboxEntry, ProjectionRefreshHint
from app.services.authority_event_bus import AuthorityEventBusPort


class AdventureBasicMirrorRuntimeError(ValueError):
    """Raised when a server-owned adventure scenario cannot use the mirror route."""


class AdventureBasicMirrorEventStore(GameplayEventStore):
    """Adds an explicit post-commit mirror refresh to existing authority batches."""

    def __init__(self, *, scenario_id: str, actor_ref: str) -> None:
        super().__init__()
        self._scenario_id = scenario_id
        self._actor_ref = actor_ref

    def append_batch(self, batch):  # type: ignore[no-untyped-def]
        normalized = AtomicEventBatch.model_validate(batch)
        enriched = normalized.model_copy(
            update={
                "outbox_entries": [*normalized.outbox_entries, self._mirror_outbox(normalized)],
                "projection_refresh_hints": [
                    *normalized.projection_refresh_hints,
                    ProjectionRefreshHint(
                        projection_id="godot_mirror",
                        stream_id=normalized.events[0].stream_id,
                        reason="adventure_basic_committed",
                        actor_refs=(self._actor_ref,),
                    ),
                ],
            }
        )
        return super().append_batch(enriched)

    def _mirror_outbox(self, batch: AtomicEventBatch) -> GameplayOutboxEntry:
        event = batch.events[0]
        return GameplayOutboxEntry(
            outbox_id=f"outbox:adventure-basic-mirror:{batch.transaction_id}",
            transaction_id=batch.transaction_id,
            event_id=event.event_id,
            global_sequence=0,
            topic="gameplay.committed",
            audience="godot_room",
            payload_projection={
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "source": {"layer": "gameplay", "system": "adventure_basic_mirror"},
                "routing": {
                    "audience_mode": "room",
                    "routing_mode": "event_type",
                    "target_ids": ["godot_mirror"],
                },
                "priority": "p1",
                "durability": "replayable",
                "payload": {
                    "actor_ref": self._actor_ref,
                    "scenario_id": self._scenario_id,
                },
            },
        )


@dataclass(frozen=True)
class AdventureBasicMirrorRuntimeResult:
    committed: bool
    scenario_id: str
    transaction_ids: tuple[str, ...]


@dataclass
class AdventureBasicMirrorRuntime:
    """One server-selected scenario with a read-only Godot mirror source."""

    scenario_id: str
    scenario: Scenario
    store: AdventureBasicMirrorEventStore
    dispatcher: GameplayOutboxDispatcher

    @property
    def actor_ref(self) -> str:
        return self.scenario.player_ref

    @classmethod
    def create(
        cls,
        *,
        scenario_id: str,
        publisher: GameplayGodotProjectionPublisher,
        authority_bus: AuthorityEventBusPort,
        after_transaction_dispatched: Callable[[AtomicEventBatch], None],
    ) -> "AdventureBasicMirrorRuntime":
        actor_ref = AdventureBasicScenario1.player_ref
        if publisher.has_actor_source(actor_ref=actor_ref):
            raise AdventureBasicMirrorRuntimeError("adventure_basic_mirror_actor_source_conflict")
        store = AdventureBasicMirrorEventStore(scenario_id=scenario_id, actor_ref=actor_ref)
        scenario = _create_scenario(scenario_id=scenario_id, store=store)
        runtime = cls(
            scenario_id=scenario_id,
            scenario=scenario,
            store=store,
            dispatcher=GameplayOutboxDispatcher(
                store=store,
                bus=authority_bus,
                after_transaction_dispatched=after_transaction_dispatched,
            ),
        )
        publisher.register_actor_source(
            actor_ref=runtime.actor_ref,
            source=lambda: AdventureBasicMirrorSource(
                scenario_id=runtime.scenario_id,
                scenario=runtime.scenario,
            ).godot_view(),
        )
        runtime.dispatcher.dispatch_pending()
        publisher.refresh_actor(actor_ref=runtime.actor_ref)
        return runtime

    def execute_canonical_success(self) -> AdventureBasicMirrorRuntimeResult:
        transaction_count_before = len(self.store.read_transactions())
        for operation in _canonical_operations(self.scenario_id, self.scenario):
            result = operation()
            if not _is_committed_authority_result(result):
                raise AdventureBasicMirrorRuntimeError("adventure_basic_canonical_command_not_committed")
            # Refresh only after this authority batch has committed and its outbox is delivered.
            self.dispatcher.dispatch_pending()
        transactions = self.store.read_transactions()[transaction_count_before:]
        return AdventureBasicMirrorRuntimeResult(
            committed=True,
            scenario_id=self.scenario_id,
            transaction_ids=tuple(transaction.transaction_id for transaction in transactions),
        )


def _create_scenario(*, scenario_id: str, store: GameplayEventStore) -> Scenario:
    if scenario_id == "scenario-1":
        return AdventureBasicScenario1.create(store=store)
    if scenario_id == "scenario-2":
        return AdventureBasicScenario2.create(store=store)
    if scenario_id == "scenario-3":
        return AdventureBasicScenario3.create(store=store)
    if scenario_id == "scenario-4":
        return AdventureBasicScenario4.create(store=store)
    if scenario_id == "scenario-5":
        return AdventureBasicScenario5.create(store=store)
    raise AdventureBasicMirrorRuntimeError("adventure_basic_mirror_scenario_unknown")


def _is_committed_authority_result(result: object) -> bool:
    if bool(getattr(result, "committed", False)):
        return True
    append_result = getattr(result, "append_result", None)
    return bool(getattr(result, "accepted", False)) and bool(getattr(append_result, "committed", False))


def _canonical_operations(scenario_id: str, scenario: Scenario) -> tuple[Callable[[], object], ...]:
    if scenario_id == "scenario-1":
        assert isinstance(scenario, AdventureBasicScenario1)
        return (scenario.purchase_sword, scenario.equip_sword)
    if scenario_id == "scenario-2":
        assert isinstance(scenario, AdventureBasicScenario2)
        return (scenario.purchase_sword, scenario.equip_sword, scenario.swing_sword)
    if scenario_id == "scenario-3":
        assert isinstance(scenario, AdventureBasicScenario3)
        return (scenario.equip_storage_ring, lambda: scenario.move_to_storage_ring(scenario.cargo_item_id))
    if scenario_id == "scenario-4":
        assert isinstance(scenario, AdventureBasicScenario4)
        return (scenario.purchase_land, scenario.issue_deed_credential, scenario.transfer_land_right)
    if scenario_id == "scenario-5":
        assert isinstance(scenario, AdventureBasicScenario5)
        return (
            scenario.gift_archive_relic,
            scenario.issue_archive_debt,
            lambda: scenario.repay_archive_debt(scenario.debt_principal),
            scenario.create_service_contract,
            scenario.discard_contract_document,
            scenario.complete_service_contract,
        )
    raise AdventureBasicMirrorRuntimeError("adventure_basic_mirror_scenario_unknown")


__all__ = [
    "AdventureBasicMirrorEventStore",
    "AdventureBasicMirrorRuntime",
    "AdventureBasicMirrorRuntimeError",
    "AdventureBasicMirrorRuntimeResult",
]
