"""Population-time admission for the existing Economy obligation owners.

This is a stage-three caller designed and implemented for the already registered
scheduled-transfer and tax obligation policies. It does not create a second
clock or ledger; confirmed population time is the temporal admission boundary.
"""
from __future__ import annotations

from pathlib import Path

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.economy_due_calendar import EconomyDueCalendarRegistry, PopulationEconomyTaxCaller
from app.world_runtime.obligations import (
    ObligationLifecycleContractRegistry,
    ObligationLifecycleProjection,
    ObligationSettlementCoordinator,
)
from app.world_runtime.temporal_contracts import verify_temporal_authorization


class EconomyTemporalConsumer:
    _SUPPORTED = {
        "policy:economy_scheduled_account_transfer@1",
        "policy:economy_tax_due@1",
    }

    def __init__(self, *, store: GameplayEventStore, authority: EconomyAuthorityService | None = None,
                 due_calendar_registry: EconomyDueCalendarRegistry | None = None):
        self.store = store
        self.authority = authority or EconomyAuthorityService(store=store)
        self.coordinator = ObligationSettlementCoordinator.from_closed_registry(store=store)
        if due_calendar_registry is None:
            due_calendar_registry = EconomyDueCalendarRegistry.from_directory(
                Path(__file__).resolve().parents[3] / "assets" / "gameplay" / "economy_due_calendar"
            )
        self.tax_opener = PopulationEconomyTaxCaller(
            store=store, authority=self.authority, registry=due_calendar_registry,
            population_driver=None,
        )
        self.closed = False
        self.last_results: tuple[object, ...] = ()
        self.last_errors: tuple[tuple[str, str], ...] = ()

    def close(self) -> None:
        self.closed = True

    def advance(self, driver) -> None:
        if self.closed:
            raise RuntimeError("economy_consumer_closed")
        if driver.world_runtime.is_paused():
            return
        # Tax due dates become owner obligations only through an authored
        # calendar and a real Population-confirmed temporal admission.
        if getattr(driver, "require_temporal_authorization", False):
            self.tax_opener.population_driver = driver
            opened_sources = {
                event.payload.get("source_tax_due_event_id")
                for event in self.store.read_stream("gameplay:economy")
                if event.event_type == "gameplay.economy.tax_obligation_opened"
            }
            for source in self.store.read_stream("gameplay:economy"):
                if source.event_type != "gameplay.economy.tax_due_recorded" or source.event_id in opened_sources:
                    continue
                result = self.tax_opener.open(
                    tax_due_event_id=source.event_id,
                    command_id=f"command:economy-tax-open:{source.event_id}",
                    idempotency_key=f"economy-tax-open:{source.event_id}",
                    causation_id=source.event_id,
                    correlation_id=f"economy-tax:{source.event_id}",
                )
                if not result.committed:
                    errors = getattr(self, "_opening_errors", [])
                    errors.append((source.event_id, result.failure.error_code if result.failure else "economy_tax_open_rejected"))
                    self._opening_errors = errors
        if getattr(driver, "require_temporal_authorization", False):
            pins = getattr(getattr(driver, "publish_window", None), "confirmed_time_pins", None)
            if callable(pins):
                pins = pins()
            if not isinstance(pins, dict) or not verify_temporal_authorization(
                pins=pins, expected_participant="actor_gameplay.economy_domain",
                expected_cutoff=driver.current_tick,
                expected_timeline=driver.clock.timeline.timeline_id,
                grant_key="economy",
            ):
                self.last_results = ()
                self.last_errors = (("temporal", "economy_temporal_authorization_rejected"),)
                return
        projection = ObligationLifecycleProjection(
            tuple(registration for registration in ObligationLifecycleContractRegistry.closed_registrations()
                  if registration.policy_ref in self._SUPPORTED)
        ).rebuild(self.store.read_events())
        due = projection.at_tick(driver.current_tick, catch_up_limit=driver.catch_up_limit)
        scheduled = {item.obligation_id: item for item in due.to_scheduled_obligations()}
        results: list[object] = []
        errors: list[tuple[str, str]] = list(getattr(self, "_opening_errors", []))
        self._opening_errors = []
        for record in due.open.values():
            if record.status != "due":
                continue
            obligation = scheduled.get(record.obligation_id)
            if obligation is None:
                continue
            policy_ref = record.policy_ref
            if policy_ref not in self._SUPPORTED:
                continue
            obligation = obligation.model_copy(update={"status": "due"})
            try:
                if policy_ref == "policy:economy_scheduled_account_transfer@1":
                    fragment = self.authority.build_scheduled_account_transfer_settlement_fragment(
                        obligation=obligation
                    )
                else:
                    fragment = self.authority.build_tax_obligation_settlement_fragment(
                        obligation=obligation
                    )
                plan = self.coordinator.plan_settle(
                    obligation=obligation,
                    fragments=(fragment,),
                    principal_ref=EconomyAuthorityService._PRINCIPAL,
                )
                if not plan.ready or plan.owner_commit_batch is None:
                    raise ValueError(plan.error_code or "economy_temporal_plan_rejected")
                result = self.authority.commit_obligation_batch(plan.owner_commit_batch)
                results.append(result)
                if not result.committed:
                    errors.append((obligation.obligation_id, result.error_code or "economy_temporal_commit_rejected"))
            except Exception as exc:
                errors.append((obligation.obligation_id, f"{type(exc).__name__}:{exc}"))
        self.last_results = tuple(results)
        self.last_errors = tuple(errors)


__all__ = ["EconomyTemporalConsumer"]
