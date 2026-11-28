"""Commit Ownership Bond expiry after a Population-confirmed world boundary."""
from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.ownership_runtime import OwnershipAuthorityService, OwnershipProjector
from app.world_runtime.temporal_contracts import verify_temporal_authorization


class OwnershipBondExpiryConsumer:
    def __init__(self, *, store: GameplayEventStore) -> None:
        self.store = store
        self.authority = OwnershipAuthorityService(store=store)
        self.projector = OwnershipProjector()
        self.last_results: tuple[object, ...] = ()
        self.last_errors: tuple[tuple[str, str], ...] = ()

    def advance(self, driver) -> None:
        if driver.world_runtime.is_paused():
            return

        pins = getattr(getattr(driver, "publish_window", None), "confirmed_time_pins", None)
        if callable(pins):
            pins = pins()
        if not isinstance(pins, dict) or not verify_temporal_authorization(
            pins=pins,
            expected_participant="actor_gameplay.ownership_domain",
            expected_cutoff=driver.current_tick,
            expected_timeline=driver.clock.timeline.timeline_id,
            grant_key="ownership",
        ):
            self.last_results = ()
            self.last_errors = (("temporal", "ownership_temporal_authorization_rejected"),)
            return

        world_ref = driver.world_runtime.mode.world_ref
        cadence_id = f"cadence:{world_ref}:{driver.current_tick - driver.window_size}"
        results: list[object] = []
        errors: list[tuple[str, str]] = []
        projection = self.projector.rebuild(self.store.read_events())
        due_bonds = sorted(
            (bond.bond_ref, bond.term_expires_at)
            for bond in projection.bonds.values()
            if bond.status == "active"
            and bond.term_expires_at is not None
            and bond.term_expires_at <= driver.current_tick
        )
        for bond_ref, term_expires_at in due_bonds:
            projection = self.projector.rebuild(self.store.read_events())
            bond = projection.bonds.get(bond_ref)
            if bond is None or bond.status != "active":
                continue
            command_id = f"ownership-expire:{bond_ref}:{term_expires_at}"
            try:
                result = self.authority.expire_bond(
                    command_id=command_id,
                    bond_ref=bond_ref,
                    world_tick=driver.current_tick,
                    expected_ownership_revision=projection.source_revision_vector.get("gameplay:ownership", 0),
                    idempotency_key=command_id,
                    causation_id=cadence_id,
                    correlation_id=cadence_id,
                )
                results.append(result)
                if not result.committed:
                    errors.append((bond_ref, result.failure.error_code if result.failure else "ownership_expiry_rejected"))
            except ValueError as exc:
                errors.append((bond_ref, str(exc)))

        self.last_results = tuple(results)
        self.last_errors = tuple(errors)
