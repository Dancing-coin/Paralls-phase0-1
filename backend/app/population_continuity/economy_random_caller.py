"""Population temporal caller for the stage-three Economy random owner.

The caller only admits a Population-confirmed window and forwards a frozen
registry source to Economy. It owns no random state, clock, or receipts.
"""
from __future__ import annotations

import hashlib
import json

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.economy_random_registry import EconomyRandomPolicyRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.random_business_admission import (
    RandomBusinessAdmission,
    RandomBusinessRequest,
)
from app.world_runtime.temporal_contracts import verify_temporal_authorization


class PopulationEconomyRandomCaller:
    """Designed and implemented stage-three Population -> Economy ingress."""

    def __init__(self, *, store: GameplayEventStore, registry: EconomyRandomPolicyRegistry,
                 authority: EconomyAuthorityService | None = None,
                 population_driver=None) -> None:
        self.store = store
        self.registry = registry
        self.authority = authority or EconomyAuthorityService(store=store)
        self.admission = RandomBusinessAdmission()
        self.population_driver = population_driver

    def _confirmed_cadence(self) -> tuple[str, dict[str, object]] | None:
        driver = self.population_driver
        if driver is None or driver.world_runtime.is_paused():
            return None
        publisher = driver.publish_window
        getter = getattr(publisher, "confirmed_time_pins", None)
        pins = getter() if callable(getter) else getter
        latest = getattr(driver.world_runtime, "latest_confirmation", None)
        cadence_id = getattr(latest, "cadence_id", None)
        if not isinstance(pins, dict) or not isinstance(cadence_id, str) or not cadence_id:
            return None
        # The publisher is the only source of confirmed cadence pins.  A
        # caller-provided copy is accepted only as an equality check below.
        return cadence_id, dict(pins)

    def _durable_cadence_read_set(self, *, world_ref: str, cadence_id: str, pins: dict[str, object],
                                  world_tick: int) -> dict[str, int] | None:
        result = self.store.get_by_idempotency(
            "world_runtime.cadence", f"population-runtime:{cadence_id}"
        )
        # Published cadence ids are stable in the existing driver.  Refuse a
        # guessed record instead of treating a re-digested pin as authority.
        if result is None or not result.committed or not result.committed_event_ids:
            return None
        transaction = self.store.get_transaction(result.transaction_id)
        if (transaction is None or transaction.idempotency_record.principal_ref != "world_runtime.cadence"
                or transaction.command_id != result.command_id
                or transaction.idempotency_record.idempotency_key != f"population-runtime:{cadence_id}"
                or tuple(event.event_id for event in transaction.events) != tuple(result.committed_event_ids)):
            return None
        event = self.store.get_event(result.committed_event_ids[0])
        if (event.event_type != "population.cadence.admitted"
                or event.stream_id != f"population-cadence:{world_ref}"
                or event.transaction_id != result.transaction_id
                or event.command_id != result.command_id
                or event.visibility_policy != "project"):
            return None
        record = event.payload
        cadence = record.get("cadence")
        if (not isinstance(cadence, dict) or cadence.get("world_ref") != world_ref
                or cadence.get("window_end") != world_tick
                or cadence.get("cadence_id") != cadence_id):
            return None
        persisted = record.get("time_pins")
        if not isinstance(persisted, dict) or persisted != pins:
            return None
        digest = record.get("record_digest")
        if not isinstance(digest, str):
            return None
        expected = "sha256:" + hashlib.sha256(
            json.dumps({key: value for key, value in record.items() if key != "record_digest"},
                       sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if digest != expected:
            return None
        revocation_stream = f"population-cadence-revocation:{world_ref}"
        # Capture the revocation head before inspecting its contents. The
        # Economy append pins this revision, so a revoke racing any checks
        # below invalidates the final write through the store's CAS.
        revocation_revision = self.store.get_stream_head(revocation_stream)
        for revocation in self.store.read_stream(revocation_stream):
            if (revocation.event_type == "population.cadence.revoked"
                    and revocation.payload.get("cadence_id") == cadence["cadence_id"]):
                revocation_tx = self.store.get_transaction(revocation.transaction_id)
                if (revocation.visibility_policy != "project" or revocation_tx is None
                        or revocation_tx.idempotency_record.principal_ref != "world_admin"
                        or revocation_tx.command_id != revocation.command_id):
                    return None
                return None
        return {
            event.stream_id: event.stream_revision,
            revocation_stream: revocation_revision,
        }

    def submit(
        self, *, policy_ref: str, operation_ref: str, effect_ref: str,
        target_ref: str, actor_ref: str, world_ref: str, timeline_ref: str,
        draw_index: int, world_tick: int, idempotency_key: str, command_id: str,
        pins: dict[str, object] | None, causation_id: str = "population:economy-random",
        correlation_id: str = "population:economy-random",
    ):
        if target_ref != actor_ref:
            return self.authority._rejected_append(command_id, "economy_random_target_identity_conflict")
        confirmed_record = self._confirmed_cadence()
        if confirmed_record is None:
            return self.authority._rejected_append(command_id, "economy_random_cadence_unconfirmed")
        cadence_id, confirmed = confirmed_record
        if pins is not None and pins != confirmed:
            return self.authority._rejected_append(command_id, "economy_random_cadence_unconfirmed")
        pins = confirmed
        driver = self.population_driver
        expected_world = driver.world_runtime.mode.world_ref
        if (world_ref != expected_world or driver.current_tick != world_tick
                or pins.get("timeline_id") != timeline_ref
                or pins.get("input_cutoff") != world_tick
                or pins.get("confirmation_boundary") != world_tick):
            return self.authority._rejected_append(command_id, "economy_random_cadence_boundary_conflict")
        read_stream_revisions = self._durable_cadence_read_set(
            world_ref=world_ref, cadence_id=cadence_id, pins=pins, world_tick=world_tick
        )
        if read_stream_revisions is None:
            return self.authority._rejected_append(command_id, "economy_random_cadence_receipt_invalid")
        if not verify_temporal_authorization(
            pins=pins, expected_participant="actor_gameplay.economy_domain",
            expected_cutoff=world_tick, expected_timeline=timeline_ref, grant_key="economy",
        ):
            return self.authority._rejected_append(command_id, "economy_random_temporal_authorization_rejected")
        try:
            policy = self.registry.policy(policy_ref)
            source = self.registry.source(policy_ref)
            request = RandomBusinessRequest(
                operation_ref=operation_ref, effect_ref=effect_ref, target_ref=actor_ref,
                draw_index=draw_index, source_digest=source.source_digest,
            )
            frozen = self.admission.admit(
                source, request, actor_ref=actor_ref, world_ref=world_ref,
                timeline_ref=timeline_ref, now_world_tick=world_tick,
                caller_principal=EconomyAuthorityService._PRINCIPAL,
            )
            current_registry = self.registry.reload()
            current_source = current_registry.source(policy_ref)
            self.admission.revalidate(frozen, current_source, now_world_tick=world_tick)
            policy_changed = current_registry.policy(policy_ref) != policy
        except (OSError, KeyError, TypeError, ValueError):
            return self.authority._rejected_append(command_id, "economy_random_source_revalidation_failed")
        if policy_changed:
            return self.authority._rejected_append(command_id, "economy_random_policy_changed")
        return self.authority.settle_random_business(
            operation_ref=operation_ref, kind=policy.kind, target_ref=target_ref,
            world_ref=world_ref, timeline_ref=timeline_ref, source=source, policy=policy,
            world_tick=world_tick, idempotency_key=idempotency_key, command_id=command_id,
            causation_id=causation_id, correlation_id=correlation_id,
            effect_ref=effect_ref, draw_index=draw_index, window_ref=cadence_id,
            read_stream_revisions=read_stream_revisions,
        )


__all__ = ["PopulationEconomyRandomCaller"]
