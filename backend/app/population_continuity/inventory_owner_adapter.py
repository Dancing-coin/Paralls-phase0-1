from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any

from app.gameplay.closed_generic_gameplay_families import ProductionOutputCustodyIntent
from app.population_continuity.models import BatchIntentCandidate
from app.population_continuity.siming_contracts import PopulationOwnerReceipt, PopulationReadSet
from app.world_runtime.temporal_contracts import verify_temporal_authorization
from app.world_runtime.temporal_contracts import SettlementWindow, SimulationTime


class InventoryOutputCustodyOwnerExecutor:
    """Route one population candidate through Inventory's existing custody Owner."""

    OWNER_REF = "actor_gameplay.inventory_domain"
    EVENT_FAMILY = "gameplay.inventory.production_output_received@1"
    CAPABILITY_ID = "population:inventory-output-custody:v1"
    CONTRACT_REF = "inf:inventory-production-output-custody@1"
    _FORBIDDEN_OVERRIDES = frozenset(
        {"holder_ref", "container_id", "quantity", "item_ref", "stream_ref", "event_family", "owner_ref"}
    )

    def __init__(self, *, authority: Any) -> None:
        self._authority = authority

    def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt:
        rejected = lambda: PopulationOwnerReceipt(
            receipt_ref=f"rejected:{intent.intent_ref}",
            owner_ref=self.OWNER_REF,
            event_family=self.EVENT_FAMILY,
            committed=False,
            revision_vector={},
            zero_write=True,
        )
        if (
            intent.intent_kind != "inventory_output_custody"
            or intent.package_revision != self.CAPABILITY_ID
            or intent.privacy_scope not in {"organization:summary", "public"}
        ):
            return rejected()
        projection = next((item for item in read_set.projections if item.ref == intent.source_ref), None)
        if projection is None or projection.scope != intent.privacy_scope or dict(projection.revision_vector) != dict(intent.expected_revisions):
            return rejected()
        store = getattr(self._authority, "_store", None)
        if store is None:
            return rejected()
        try:
            temporal_read_set = self._cadence_read_set(read_set)
        except (KeyError, TypeError, ValueError, AttributeError):
            return rejected()
        if not self._authorized_settlement_window(read_set):
            return rejected()
        payload = projection.payload
        if self._FORBIDDEN_OVERRIDES.intersection(payload) or any(
            key in intent.payload for key in self._FORBIDDEN_OVERRIDES
        ):
            return rejected()
        try:
            certification_event_id = str(payload["source_certification_event_id"])
            certification_revision = int(payload["source_certification_revision"])
            source_stream_ref = str(payload["source_stream_ref"])
            if not certification_event_id or certification_revision < 1 or not source_stream_ref:
                return rejected()
            if intent.expected_revisions.get(source_stream_ref) != certification_revision:
                return rejected()
            frozen = self._authority.freeze_production_output_custody_read(
                certification_event_id=certification_event_id,
                command_id=intent.intent_ref,
                correlation_id=intent.correlation_id,
            )
            if (
                frozen.source_certification_revision != certification_revision
                or frozen.source_stream_ref != source_stream_ref
                or intent.expected_revisions.get(source_stream_ref) != frozen.source_certification_revision
            ):
                return rejected()
            inventory_revision = frozen.inventory_stream_revision
            binding_pins = frozen.bindings[0].revision_pins()
            typed_intent = ProductionOutputCustodyIntent(
                certification_event_id=certification_event_id,
                expected_certification_revision=certification_revision,
                expected_inventory_stream_revision=inventory_revision,
                command_id=intent.intent_ref,
                correlation_id=intent.correlation_id,
                submitted_at=str(payload.get("submitted_at") or f"population:{read_set.cadence.cadence_id}"),
                **binding_pins,
            )
            result = self._authority.settle_production_output_custody(
                intent=typed_intent, temporal_read_set=temporal_read_set
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            return rejected()
        committed = bool(getattr(result, "committed", False))
        status = str(getattr(result, "idempotency_status", "rejected"))
        revisions = dict(getattr(result, "resulting_stream_revisions", {}) or {})
        event_ids = tuple(str(item) for item in (getattr(result, "committed_event_ids", ()) or ()))
        return PopulationOwnerReceipt(
            receipt_ref=event_ids[0] if event_ids else f"receipt:{intent.intent_ref}",
            owner_ref=self.OWNER_REF,
            event_family=self.EVENT_FAMILY,
            committed=committed,
            revision_vector=revisions,
            zero_write=not committed or status == "duplicate_replayed",
            idempotency_status=status,
        )

    def settlement_window(self, read_set: PopulationReadSet) -> SettlementWindow:
        """Build the caller's frozen window from the admitted cadence/read set.

        The object is derived only from durable cadence pins and the current
        read set.  It is deliberately reconstructed at submission time so a
        changed source revision or cadence cannot be hidden in a cached window.
        """
        pins = read_set.temporal_pins
        timeline_id = str(pins.get("timeline_id", ""))
        if not timeline_id:
            raise ValueError("settlement_window_timeline_missing")
        start = int(read_set.cadence.window_start)
        end = int(read_set.cadence.window_end)
        source_refs = tuple(
            str(item.payload["source_certification_event_id"])
            for item in read_set.projections
            if isinstance(item.payload.get("source_certification_event_id"), str)
        )
        evidence_refs = tuple(sorted(set(source_refs + (read_set.cadence.cadence_id,))))
        revisions = tuple(sorted(
            (str(key), int(value))
            for item in read_set.projections
            for key, value in item.revision_vector.items()
        ))
        return SettlementWindow(
            window_ref=read_set.cadence.cadence_id,
            timeline_id=timeline_id,
            from_time=SimulationTime(timeline_id, start, Fraction(start)),
            to_time=SimulationTime(timeline_id, end, Fraction(end)),
            participant_scope=(self.OWNER_REF,),
            phase_ref="population-cadence",
            input_cutoff=SimulationTime(timeline_id, int(pins["input_cutoff"]), Fraction(int(pins["input_cutoff"]))),
            late_input_policy_ref=str(pins["late_input_policy_ref"]),
            confirmation_boundary=SimulationTime(
                timeline_id, int(pins["confirmation_boundary"]), Fraction(int(pins["confirmation_boundary"]))
            ),
            frozen_read_set=revisions,
            evidence_refs=evidence_refs,
            ordering_policy_ref=str(pins["ordering_policy_ref"]),
            expected_authority_revisions=revisions,
            settlement_idempotency_key=f"inventory:{read_set.cadence.cadence_id}:{read_set.read_set_digest}",
        )

    def _authorized_settlement_window(self, read_set: PopulationReadSet) -> bool:
        """Require the cadence authority record; caller supplied pins are not authority."""
        pins = read_set.temporal_pins
        required = {
            "timeline_id", "profile_revision", "mapping_id", "mapping_revision", "source_clock_ref",
            "source_revision", "sampled_at", "received_at", "window_ticks", "canonical_unit_ref",
            "step_duration", "settlement_participant_scope", "input_cutoff", "late_input_policy_ref",
            "confirmation_boundary", "ordering_policy_ref", "temporal_authorization_ref",
            "temporal_authorization_revision", "temporal_authorization_issuer_ref",
            "temporal_authorization_valid_until", "temporal_authorization_digest",
        }
        if not required.issubset(pins):
            return False
        # ``bool`` is an ``int`` subclass.  Equality alone would therefore let
        # True stand in for tick 1 in the operational timestamp fields, even
        # though these pins are frozen alongside the world-time window.
        if any(
            type(pins.get(key)) is not int
            for key in (
                "sampled_at", "received_at", "freshness", "window_ticks", "input_cutoff",
                "confirmation_boundary", "temporal_authorization_valid_until",
            )
        ):
            return False
        if pins.get("settlement_participant_scope") != self.OWNER_REF:
            return False
        if pins.get("sampled_at") != read_set.cadence.window_end or pins.get("received_at") != read_set.cadence.window_end:
            return False
        if pins.get("input_cutoff") != read_set.cadence.window_end or pins.get("confirmation_boundary") != read_set.cadence.window_end:
            return False
        if pins.get("late_input_policy_ref") != "reject_after_cutoff" or pins.get("ordering_policy_ref") != "source_revision_then_event_ref":
            return False
        if pins.get("window_ticks") != read_set.cadence.window_end - read_set.cadence.window_start:
            return False
        if not verify_temporal_authorization(
            pins=pins,
            expected_participant=self.OWNER_REF,
            expected_cutoff=read_set.cadence.window_end,
            expected_timeline=str(pins.get("timeline_id")),
        ):
            return False
        try:
            window = self.settlement_window(read_set)
            if (
                window.from_time.canonical_time_value != read_set.cadence.window_start
                or window.to_time.canonical_time_value != read_set.cadence.window_end
                or window.input_cutoff.canonical_time_value != read_set.cadence.window_end
                or window.confirmation_boundary.canonical_time_value != read_set.cadence.window_end
                or window.participant_scope != (self.OWNER_REF,)
                or window.late_input_policy_ref != "reject_after_cutoff"
                or window.ordering_policy_ref != "source_revision_then_event_ref"
            ):
                return False
        except (KeyError, TypeError, ValueError):
            return False
        store = getattr(self._authority, "_store", None)
        if store is None:
            return False
        try:
            revocation_stream = f"population-cadence-revocation:{read_set.cadence.world_ref}"
            for revocation in store.read_stream(revocation_stream):
                if (
                    revocation.event_type != "population.cadence.revoked"
                    or revocation.payload.get("cadence_id") != read_set.cadence.cadence_id
                    or revocation.payload.get("world_ref") != read_set.cadence.world_ref
                ):
                    continue
                if (
                    revocation.payload.get("issuer_ref") != "world_admin"
                    or revocation.payload.get("authority_contract_ref")
                    != "world-admin:population-cadence-revocation@1"
                    or revocation.command_id != revocation.payload.get("command_id")
                ):
                    return False
                transaction = store.get_transaction(revocation.transaction_id)
                if transaction is None or transaction.idempotency_record.principal_ref != "world_admin":
                    return False
                return False
            result = store.get_by_idempotency("world_runtime.cadence", f"population-runtime:{read_set.cadence.cadence_id}")
            if result is None or not result.committed or not result.committed_event_ids:
                return False
            if len(set(result.committed_event_ids)) != len(result.committed_event_ids):
                return False
            transaction = store.get_transaction(result.transaction_id)
            if (
                transaction is None
                or transaction.command_id != result.command_id
                or transaction.idempotency_record.principal_ref != "world_runtime.cadence"
                or tuple(event.event_id for event in transaction.events)
                != tuple(result.committed_event_ids)
            ):
                return False
            event = store.get_event(result.committed_event_ids[0])
            if (
                event.event_type != "population.cadence.admitted"
                or event.stream_id != f"population-cadence:{read_set.cadence.world_ref}"
                or event.transaction_id != result.transaction_id
                or event.command_id != result.command_id
                # Cadence admission is a project-visible authority event.  The
                # receipt contract must match the policy emitted by
                # ``build_atomic_event_batch`` rather than requiring the
                # authority-only policy used by private owner events.
                or event.visibility_policy != "project"
            ):
                return False
            record = event.payload
            if record.get("record_digest") != "sha256:" + hashlib.sha256(
                json.dumps({key: value for key, value in record.items() if key != "record_digest"}, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest():
                return False
            cadence = record.get("cadence")
            if not isinstance(cadence, dict) or cadence != read_set.cadence.model_dump(mode="json"):
                return False
            persisted = record.get("time_pins")
            if not isinstance(persisted, dict):
                return False
            return all(persisted.get(key) == value for key, value in pins.items())
        except (AttributeError, KeyError, TypeError, ValueError):
            return False

    def _cadence_read_set(self, read_set: PopulationReadSet) -> dict[str, int]:
        """Validate the original admission, then pin its revocation stream for CAS."""
        store = self._authority._store
        cadence = read_set.cadence
        stream = f"population-cadence:{cadence.world_ref}"
        revocations = f"population-cadence-revocation:{cadence.world_ref}"
        # Read BEFORE inspecting records: a later change must fail at owner append.
        revisions = {ref: store.get_stream_head(ref) for ref in (stream, revocations)}
        receipt = store.get_by_idempotency("world_runtime.cadence", f"population-runtime:{cadence.cadence_id}")
        if receipt is None or not receipt.committed or len(receipt.committed_event_ids) != 1:
            raise ValueError("inventory_cadence_admission_missing")
        event = store.get_event(receipt.committed_event_ids[0])
        record = event.payload
        digest = "sha256:" + hashlib.sha256(json.dumps(
            {key: value for key, value in record.items() if key != "record_digest"},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        if (
            event.event_type != "population.cadence.admitted"
            or event.stream_id != stream
            or event.visibility_policy != "project"
            or event.transaction_id != receipt.transaction_id
            or not store.transaction_owns_event(transaction_id=receipt.transaction_id,
                event_id=event.event_id, principal_ref="world_runtime.cadence")
            or record.get("schema_version") != 1
            or record.get("cadence") != cadence.model_dump(mode="json")
            or record.get("record_digest") != digest
        ):
            raise ValueError("inventory_cadence_admission_invalid")
        if any(event.event_type == "population.cadence.revoked"
               and event.payload.get("cadence_id") == cadence.cadence_id
               for event in store.read_stream(revocations)):
            raise ValueError("inventory_cadence_revoked")
        return revisions

    def _inventory_revision(self, certification_event_id: str, payload: dict[str, object]) -> int:
        """Read the current Owner stream; only test doubles use the projection pin."""
        store = getattr(self._authority, "_store", None)
        if store is None:
            value = payload.get("expected_inventory_stream_revision", 0)
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
        try:
            certification = store.get_event(certification_event_id)
            source_stream = certification.stream_id
            facility_ref = certification.payload.get("facility_ref")
            acquisitions = [
                event
                for event in store.read_stream(source_stream)
                if event.event_type == "gameplay.construction_production.facility_acquired"
                and event.payload.get("facility_ref") == facility_ref
            ]
            holder_ref = acquisitions[0].payload.get("owner_ref") if len(acquisitions) == 1 else None
            if isinstance(holder_ref, str) and holder_ref:
                return int(store.get_stream_head(f"gameplay:inventory:{holder_ref}"))
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
        return 0


__all__ = ["InventoryOutputCustodyOwnerExecutor"]
