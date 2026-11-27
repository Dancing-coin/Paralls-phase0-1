"""Production/Facility-owned gate integrity facts on the shared Pool primitive."""
from __future__ import annotations

from decimal import Decimal
import re
from typing import Mapping

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult
from app.gameplay.pool_runtime import (
    PoolAuthorityService,
    PoolDefinition,
    PoolError,
    PoolProjector,
)
from app.gameplay.siege_physical_input_runtime import (
    GateImpactReceipt,
    SiegePhysicalInputAuthority,
)


_FACILITY_PRINCIPAL = "actor_gameplay.construction_production_domain"
_GATE_REF = re.compile(r"^gate-[a-z0-9-]+$")


class FacilityIntegrityAuthority:
    """Write gate integrity through Production/Facility's configured Pool facts."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        definitions: Mapping[str, PoolDefinition],
        impact_profiles: Mapping[str, Mapping[str, Decimal]] | None = None,
    ) -> None:
        if not definitions:
            raise ValueError("facility_integrity_definition_invalid")
        for gate_ref, definition in definitions.items():
            if (
                not isinstance(gate_ref, str)
                or _GATE_REF.fullmatch(gate_ref) is None
                or definition.fact_type != self.fact_type_for(gate_ref)
                or not any(item.threshold_ref == "breach" for item in definition.thresholds)
            ):
                raise ValueError("facility_integrity_definition_invalid")
        self._definitions = dict(definitions)
        self.store = store
        self._impact_profiles = {
            gate_ref: dict(profiles)
            for gate_ref, profiles in (impact_profiles or {}).items()
        }
        for gate_ref, profiles in self._impact_profiles.items():
            if gate_ref not in self._definitions or any(
                not isinstance(profile_ref, str)
                or not profile_ref
                or not isinstance(delta, Decimal)
                or not delta.is_finite()
                or delta >= 0
                for profile_ref, delta in profiles.items()
            ):
                raise ValueError("facility_impact_profile_invalid")
        self._pool = PoolAuthorityService(
            store=store,
            definitions=tuple(self._definitions.values()),
            owner_ref=_FACILITY_PRINCIPAL,
            principal_ref=_FACILITY_PRINCIPAL,
        )

    @staticmethod
    def fact_type_for(gate_ref: str) -> str:
        return f"fact:facility:{gate_ref}:integrity"

    def initialize(
        self,
        *,
        gate_ref: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        definition = self._definition(gate_ref)
        return self._pool.initialize(
            definition=definition,
            command_id=command_id,
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )

    def apply_delta(
        self,
        *,
        gate_ref: str,
        delta: Decimal,
        reason_code: str,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        read_stream_revisions: Mapping[str, int] | None = None,
        event_time: int | None = None,
    ) -> AppendBatchResult:
        definition = self._definition(gate_ref)
        if reason_code not in {"damage", "repair"}:
            raise PoolError("facility_integrity_reason_invalid")
        return self._pool.adjust(
            fact_type=definition.fact_type,
            delta=delta,
            reason_code="damage" if reason_code == "damage" else "heal",
            command_id=command_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            read_stream_revisions=read_stream_revisions,
            event_time=event_time,
        )

    def apply_signed_impact(
        self,
        *,
        input_authority: SiegePhysicalInputAuthority,
        authority_ref: str,
        receipt_id: str,
    ) -> AppendBatchResult:
        receipt_event = input_authority.gate_impact_event(
            authority_ref=authority_ref,
            receipt_id=receipt_id,
        )
        if receipt_event is None:
            return self._reject(receipt_id, "facility_impact_input_unknown")
        receipt = GateImpactReceipt.model_validate(receipt_event.payload["receipt"])
        definition = self._definition(receipt.gate_ref)
        delta = self._impact_profiles.get(receipt.gate_ref, {}).get(
            receipt.impact_kind_ref
        )
        if delta is None:
            return self._reject(receipt_id, "facility_impact_profile_unknown")
        if not isinstance(delta, Decimal) or delta >= 0:
            raise PoolError("facility_impact_profile_invalid")
        command_id = f"facility-impact:{receipt_event.event_id}"
        if self.store.get_by_idempotency(_FACILITY_PRINCIPAL, command_id) is None:
            projection = PoolProjector().rebuild(
                self.store.read_stream(definition.fact_type),
                definitions={definition.fact_type: definition},
            )
            if receipt.expected_integrity_revision != projection.source_revision:
                return self._reject(receipt_id, "facility_impact_revision_conflict")
        result = self.apply_delta(
            gate_ref=receipt.gate_ref,
            delta=delta,
            reason_code="damage",
            command_id=command_id,
            idempotency_key=command_id,
            expected_revision=receipt.expected_integrity_revision,
            causation_id=receipt_event.event_id,
            correlation_id=f"siege:{receipt.gate_ref}",
            read_stream_revisions={receipt_event.stream_id: receipt_event.stream_revision},
            event_time=receipt_event.event_time,
        )
        return result

    @staticmethod
    def _reject(command_id: str, code: str) -> AppendBatchResult:
        from app.gameplay.models import GameplayFailure

        return AppendBatchResult(
            committed=False,
            transaction_id=f"rejected:facility-impact:{command_id}",
            command_id=f"facility-impact:{command_id}",
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=code,
                message=code,
                failed_stage="facility_impact_input",
            ),
        )

    def _definition(self, gate_ref: str) -> PoolDefinition:
        try:
            return self._definitions[gate_ref]
        except KeyError as exc:
            raise PoolError("facility_integrity_gate_unknown") from exc
