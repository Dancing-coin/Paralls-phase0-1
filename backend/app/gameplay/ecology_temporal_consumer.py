"""Population-time admission for the existing Ecology obligation owner.

Designed and implemented in stage three. Reuses the existing population
driver, event store, obligation registry and Ecology authority.
"""
from __future__ import annotations

from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.event_store import GameplayEventStore
from app.world_runtime.obligations import (
    ObligationLifecycleContractRegistry,
    ObligationLifecycleProjection,
    ObligationSettlementCoordinator,
)
from app.world_runtime.temporal_contracts import verify_temporal_authorization


class EcologyTemporalConsumer:
    _SUPPORTED = {
        "policy:ecology_frost_crop_state_expiry@1",
        "policy:ecology_drought_state_expiry@1",
    }

    def __init__(self, *, store: GameplayEventStore, authority: EcologyHazardAuthority | None = None):
        self.store = store
        self.authority = authority or EcologyHazardAuthority(store=store)
        self.coordinator = ObligationSettlementCoordinator.from_closed_registry(store=store)
        self.closed = False
        self.last_results: tuple[object, ...] = ()
        self.last_errors: tuple[tuple[str, str], ...] = ()

    def close(self) -> None:
        self.closed = True

    def advance(self, driver) -> None:
        if self.closed:
            raise RuntimeError("ecology_consumer_closed")
        if driver.world_runtime.is_paused():
            return
        if getattr(driver, "require_temporal_authorization", False):
            pins = getattr(getattr(driver, "publish_window", None), "confirmed_time_pins", None)
            if callable(pins):
                pins = pins()
            if not isinstance(pins, dict) or not verify_temporal_authorization(
                pins=pins, expected_participant="actor_gameplay.ecology_domain",
                expected_cutoff=driver.current_tick,
                expected_timeline=driver.clock.timeline.timeline_id,
                grant_key="ecology",
            ):
                self.last_results = ()
                self.last_errors = (("temporal", "ecology_temporal_authorization_rejected"),)
                return
        view = ObligationLifecycleProjection(
            tuple(registration for registration in ObligationLifecycleContractRegistry.closed_registrations()
                  if registration.policy_ref in self._SUPPORTED)
        ).rebuild(self.store.read_events())
        results: list[object] = []
        errors: list[tuple[str, str]] = []
        due_view = view.at_tick(driver.current_tick, catch_up_limit=driver.catch_up_limit)
        scheduled = {item.obligation_id: item for item in due_view.to_scheduled_obligations()}
        for record in due_view.open.values():
            if record.status != "due":
                continue
            obligation = scheduled[record.obligation_id].model_copy(update={"status": "due"})
            try:
                region_ref = next((ref for ref in obligation.source_refs if ref.startswith("region:")), "")
                if not region_ref:
                    raise ValueError("ecology_temporal_region_missing")
                region = region_ref
                stream = EcologyHazardAuthority.ecology_stream_id(region_ref=region)
                expected_revision = self.store.get_stream_head(stream)
                if record.policy_ref == "policy:ecology_frost_crop_state_expiry@1":
                    crop_ref = next((ref for ref in obligation.source_refs if ref.startswith("crop:")), "")
                    hazard_ref = next((ref for ref in obligation.source_refs if ref.startswith("hazard:")), "")
                    if not crop_ref or not hazard_ref:
                        raise ValueError("ecology_temporal_frost_source_missing")
                    fragment = self.authority.build_frost_crop_state_fragment(
                        obligation=obligation, region_ref=region,
                        hazard_ref=hazard_ref.removeprefix("hazard:"),
                        crop_ref=crop_ref.removeprefix("crop:"), expected_revision=expected_revision,
                    )
                elif record.policy_ref == "policy:ecology_drought_state_expiry@1":
                    fragment = self.authority.build_drought_state_fragment(
                        obligation=obligation, region_ref=region, expected_revision=expected_revision,
                    )
                else:
                    continue
                plan = self.coordinator.plan_settle(
                    obligation=obligation, fragments=(fragment,),
                    principal_ref="world_runtime.ecology_temporal_consumer",
                )
                if not plan.ready or plan.owner_commit_batch is None:
                    raise ValueError(plan.error_code or "ecology_temporal_plan_rejected")
                result = self.authority.commit_obligation_batch(plan.owner_commit_batch)
                results.append(result)
                if not result.committed:
                    errors.append((obligation.obligation_id, result.error_code or "ecology_temporal_commit_rejected"))
            except Exception as exc:
                errors.append((obligation.obligation_id, f"{type(exc).__name__}:{exc}"))
        self.last_results = tuple(results)
        self.last_errors = tuple(errors)
