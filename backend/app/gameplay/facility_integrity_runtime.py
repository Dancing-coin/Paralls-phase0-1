"""Production/Facility-owned gate integrity facts on the shared Pool primitive."""
from __future__ import annotations

from decimal import Decimal
import re
from typing import Mapping

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult
from app.gameplay.pool_runtime import PoolAuthorityService, PoolDefinition, PoolError


_FACILITY_PRINCIPAL = "actor_gameplay.construction_production_domain"
_GATE_REF = re.compile(r"^gate-[a-z0-9-]+$")


class FacilityIntegrityAuthority:
    """Write gate integrity through Production/Facility's configured Pool facts."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        definitions: Mapping[str, PoolDefinition],
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
        )

    def _definition(self, gate_ref: str) -> PoolDefinition:
        try:
            return self._definitions[gate_ref]
        except KeyError as exc:
            raise PoolError("facility_integrity_gate_unknown") from exc
