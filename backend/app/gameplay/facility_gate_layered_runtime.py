"""Atomic Production/Facility resolution for the layered M6-5 gate impact."""
from __future__ import annotations

from decimal import Decimal
import re
from typing import Mapping

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, OwnerAuthorizedFragment
from app.gameplay.pool_runtime import (
    PoolDefinition,
    PoolError,
    PoolProjector,
)
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch_from_fragments
from app.gameplay.siege_physical_input_runtime import (
    FACILITY_GATE_PRINCIPAL as FACILITY_PRINCIPAL,
    GATE_IMPACT_INPUT_EVENT_V2,
    GateImpactReceiptV2,
    SiegePhysicalInputAuthority,
    facility_impact_command_id,
)


GATE_LATCH_EVENT = "gameplay.machine.transitioned"
GATE_LATCH_STATES = ("secured", "damaged", "broken")
_GATE_REF = re.compile(r"^gate-[a-z0-9-]+$")
_LAYER_NAMES = ("durability", "latch-durability", "integrity")


class FacilityGateLayeredAuthority:
    """Commit Facility damage layers atomically from a signed v2 input."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        definitions: Mapping[str, Mapping[str, PoolDefinition]],
        impact_magnitudes: Mapping[str, Mapping[str, Decimal]],
    ) -> None:
        if not definitions:
            raise ValueError("facility_gate_layer_definitions_invalid")
        normalized_definitions: dict[str, dict[str, PoolDefinition]] = {}
        for gate_ref, pools in definitions.items():
            expected = {
                self.fact_type_for(gate_ref, layer)
                for layer in _LAYER_NAMES
            }
            if (
                not isinstance(gate_ref, str)
                or _GATE_REF.fullmatch(gate_ref) is None
                or set(pools) != expected
                or any(
                    definition.fact_type != fact_type
                    for fact_type, definition in pools.items()
                )
                or not any(
                    threshold.threshold_ref == "breach"
                    for threshold in pools[self.fact_type_for(gate_ref, "integrity")].thresholds
                )
            ):
                raise ValueError("facility_gate_layer_definitions_invalid")
            normalized_definitions[gate_ref] = dict(pools)

        normalized_profiles = {
            gate_ref: dict(profiles)
            for gate_ref, profiles in impact_magnitudes.items()
        }
        for gate_ref, profiles in normalized_profiles.items():
            if gate_ref not in normalized_definitions or not profiles or any(
                not isinstance(kind_ref, str)
                or not kind_ref
                or not isinstance(magnitude, Decimal)
                or not magnitude.is_finite()
                or magnitude <= 0
                for kind_ref, magnitude in profiles.items()
            ):
                raise ValueError("facility_gate_impact_profile_invalid")

        self.store = store
        self._definitions = normalized_definitions
        self._impact_magnitudes = normalized_profiles
        self._projector = PoolProjector()

    @staticmethod
    def fact_type_for(gate_ref: str, layer: str) -> str:
        if layer not in _LAYER_NAMES:
            raise ValueError("facility_gate_layer_unknown")
        return f"fact:facility:{gate_ref}:{layer}"

    @staticmethod
    def latch_fact_type_for(gate_ref: str) -> str:
        return f"fact:facility:{gate_ref}:latch"

    def initialize(
        self,
        *,
        gate_ref: str,
        command_prefix: str,
        causation_id: str,
        correlation_id: str,
    ) -> tuple[AppendBatchResult, ...]:
        pools = self._definitions.get(gate_ref)
        if pools is None:
            raise PoolError("facility_integrity_gate_unknown")
        from app.gameplay.pool_runtime import PoolAuthorityService

        authority = PoolAuthorityService(
            store=self.store,
            definitions=tuple(pools.values()),
            owner_ref=FACILITY_PRINCIPAL,
            principal_ref=FACILITY_PRINCIPAL,
        )
        results = []
        for layer in _LAYER_NAMES:
            definition = pools[self.fact_type_for(gate_ref, layer)]
            existing_events = self.store.read_stream(definition.fact_type)
            if existing_events:
                projection = self._projector.rebuild(
                    existing_events,
                    definitions={definition.fact_type: definition},
                )
                if (projection.lower, projection.upper) != (definition.lower, definition.upper):
                    raise PoolError("pool_definition_conflict")
                continue
            results.append(authority.initialize(
                definition=definition,
                command_id=f"{command_prefix}:{layer}",
                idempotency_key=f"{command_prefix}:{layer}",
                causation_id=causation_id,
                correlation_id=correlation_id,
            ))
        return tuple(results)

    def apply_signed_impact(
        self,
        *,
        input_authority: SiegePhysicalInputAuthority,
        authority_ref: str,
        receipt_id: str,
    ) -> AppendBatchResult:
        input_event = input_authority.gate_impact_event_v2(
            authority_ref=authority_ref,
            receipt_id=receipt_id,
        )
        if input_event is None:
            return self._reject(receipt_id, "facility_impact_input_unknown")

        receipt = GateImpactReceiptV2.model_validate(input_event.payload["receipt"])
        command_id = facility_impact_command_id(input_event.event_id)
        previous_result = self.store.get_by_idempotency(FACILITY_PRINCIPAL, command_id)
        if previous_result is not None:
            return previous_result.model_copy(
                update={"idempotency_status": "duplicate_replayed"},
                deep=True,
            )
        pools = self._definitions.get(receipt.gate_ref)
        magnitude = self._impact_magnitudes.get(receipt.gate_ref, {}).get(
            receipt.impact_kind_ref
        )
        if pools is None or magnitude is None:
            return self._reject(receipt_id, "facility_impact_profile_unknown")
        expected_revisions = receipt.expected_layer_revisions
        projections = {
            layer: self._projector.rebuild(
                self.store.read_stream(self.fact_type_for(receipt.gate_ref, layer)),
                definitions={
                    self.fact_type_for(receipt.gate_ref, layer):
                    pools[self.fact_type_for(receipt.gate_ref, layer)]
                },
            )
            for layer in _LAYER_NAMES
        }
        layer_revisions = {
            self.fact_type_for(receipt.gate_ref, layer): projections[layer].source_revision
            for layer in _LAYER_NAMES
        }
        if layer_revisions != expected_revisions:
            return self._reject(receipt_id, "facility_impact_revision_conflict")

        remaining = magnitude
        event_specs: dict[str, list[tuple[str, dict[str, object]]]] = {}
        updated_latch_value = projections["latch-durability"].value
        for layer in _LAYER_NAMES:
            projection = projections[layer]
            capacity = projection.value - projection.lower
            applied = min(capacity, remaining)
            if applied <= 0:
                continue
            next_value = projection.value - applied
            fact_type = self.fact_type_for(receipt.gate_ref, layer)
            specs = [("gameplay.pool.adjusted", {
                "fact_type": fact_type,
                "previous": format(projection.value, "f"),
                "delta": format(-applied, "f"),
                "next": format(next_value, "f"),
                "reason_code": "damage",
            })]
            specs.extend(self._threshold_events(projection, next_value, pools[fact_type]))
            event_specs[fact_type] = specs
            remaining -= applied
            if layer == "latch-durability":
                updated_latch_value = next_value
            if remaining <= 0:
                break

        if not event_specs:
            return self._reject(receipt_id, "facility_gate_layers_depleted")

        latch_fact_type = self.latch_fact_type_for(receipt.gate_ref)
        latch_definition = pools[self.fact_type_for(receipt.gate_ref, "latch-durability")]
        latch_state, latch_revision = self._latch_state(
            latch_fact_type,
            latch_definition,
        )
        layer_revisions[latch_fact_type] = latch_revision
        latch_target = (
            self._latch_state_for(
                updated_latch_value,
                latch_definition.upper,
                latch_state,
            )
            if updated_latch_value != projections["latch-durability"].value
            else None
        )
        if latch_target is not None:
            event_specs[latch_fact_type] = [(GATE_LATCH_EVENT, {
                "fact_type": latch_fact_type,
                "from": latch_state,
                "to": latch_target,
                "condition_ref": "facility_latch_durability@1",
                "condition_revision": projections["latch-durability"].source_revision + 1,
            })]

        read_revisions = {
            **layer_revisions,
            input_event.stream_id: input_event.stream_revision,
        }
        expected_writes = {
            stream_id: layer_revisions[stream_id]
            for stream_id in event_specs
        }
        visibility = {
            stream_id: tuple("authority_only" for _ in specs)
            for stream_id, specs in event_specs.items()
        }
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:{command_id}",
            owner_principal_ref=FACILITY_PRINCIPAL,
            source_rule_ref="facility:impact-gate-layered@1",
            expected_revisions=expected_writes,
            read_set_revisions=read_revisions,
            event_specs={
                stream_id: tuple(specs)
                for stream_id, specs in event_specs.items()
            },
            event_visibility_policies=visibility,
            pinned_revisions=read_revisions,
        )
        batch = build_multi_stream_atomic_event_batch_from_fragments(
            command_id=command_id,
            idempotency_principal_ref=FACILITY_PRINCIPAL,
            idempotency_key=command_id,
            causation_id=input_event.event_id,
            correlation_id=f"siege:{receipt.gate_ref}",
            fragments=(fragment,),
        )
        return self.store.append_batch(batch)

    def _latch_state(
        self,
        fact_type: str,
        latch_definition: PoolDefinition,
    ) -> tuple[str, int]:
        events = self.store.read_stream(fact_type)
        if not events:
            return "secured", 0
        previous_revision = 0
        state = "secured"
        for event in events:
            payload = event.payload
            if (
                event.event_type != GATE_LATCH_EVENT
                or event.schema_version != 1
                or event.stream_revision != previous_revision + 1
                or payload.get("fact_type") != fact_type
                or payload.get("from") != state
                or payload.get("to") not in GATE_LATCH_STATES
                or (state, payload.get("to")) not in {
                    ("secured", "damaged"),
                    ("secured", "broken"),
                    ("damaged", "broken"),
                }
                or payload.get("condition_ref") != "facility_latch_durability@1"
                or type(payload.get("condition_revision")) is not int
                or payload["condition_revision"] < 1
                or not self.store.transaction_owns_event(
                    transaction_id=event.transaction_id,
                    event_id=event.event_id,
                    principal_ref=FACILITY_PRINCIPAL,
                )
            ):
                raise PoolError("facility_gate_latch_history_invalid")
            transaction = self.store.get_transaction(event.transaction_id)
            condition_events = [
                item for item in transaction.events
                if item.stream_id == latch_definition.fact_type
                and item.event_type == "gameplay.pool.adjusted"
                and item.stream_revision == payload["condition_revision"]
            ] if transaction is not None else []
            if len(condition_events) != 1:
                raise PoolError("facility_gate_latch_history_invalid")
            try:
                condition_value = Decimal(condition_events[0].payload["next"])
            except (KeyError, TypeError, ValueError) as error:
                raise PoolError("facility_gate_latch_history_invalid") from error
            if (
                not condition_value.is_finite()
                or self._latch_state_for(condition_value, latch_definition.upper, state)
                != payload["to"]
            ):
                raise PoolError("facility_gate_latch_history_invalid")
            state = payload["to"]
            previous_revision = event.stream_revision
        return state, previous_revision

    @staticmethod
    def _latch_state_for(value: Decimal, upper: Decimal, current: str) -> str | None:
        if current == "broken":
            return None
        if value <= 0:
            return "broken"
        if current == "secured" and value < upper:
            return "damaged"
        return None

    @staticmethod
    def _threshold_events(projection, next_value, definition):
        events = []
        for threshold in definition.thresholds:
            active = threshold.threshold_ref in projection.active_thresholds
            direction = None
            if not active and next_value < threshold.enter_below:
                direction = "enter"
            elif active and next_value > threshold.exit_above:
                direction = "exit"
            if direction is not None:
                events.append(("gameplay.pool.threshold_crossed", {
                    "fact_type": projection.fact_type,
                    "threshold_ref": threshold.threshold_ref,
                    "direction": direction,
                    "value": format(next_value, "f"),
                }))
        return events

    @staticmethod
    def _reject(command_id: str, code: str) -> AppendBatchResult:
        from app.gameplay.models import GameplayFailure

        return AppendBatchResult(
            committed=False,
            transaction_id=f"rejected:facility-gate-impact:{command_id}",
            command_id=f"facility-gate-impact:{command_id}",
            idempotency_status="rejected",
            failure=GameplayFailure(
                error_code=code,
                message=code,
                failed_stage="facility_gate_impact",
            ),
        )
