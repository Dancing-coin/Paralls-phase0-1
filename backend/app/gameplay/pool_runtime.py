"""Event-sourced bounded value pools with reservations and hysteresis."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Callable, Iterable, Literal, Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, OwnerAuthorizedFragment
from app.gameplay.owner_runtime_base import OwnerCommitBuilder, replay_duplicate


class PoolError(ValueError):
    pass


@dataclass(frozen=True)
class PoolThreshold:
    threshold_ref: str
    enter_below: Decimal
    exit_above: Decimal

    def __post_init__(self) -> None:
        if (not self.threshold_ref or not self.enter_below.is_finite()
                or not self.exit_above.is_finite() or self.exit_above <= self.enter_below):
            raise PoolError("pool_threshold_invalid")


@dataclass(frozen=True)
class PoolDefinition:
    fact_type: str
    lower: Decimal
    upper: Decimal
    initial: Decimal
    rate_per_tick: Decimal = Decimal(0)
    thresholds: tuple[PoolThreshold, ...] = ()
    aggregation_mode: Literal["none", "sum", "distribution", "ordered"] = "none"
    refold_model_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.fact_type or any(
            not value.is_finite() for value in (self.lower, self.upper, self.initial, self.rate_per_tick)
        ):
            raise PoolError("pool_definition_invalid")
        if self.lower > self.upper:
            raise PoolError("pool_bounds_invalid")
        if not self.lower <= self.initial <= self.upper:
            raise PoolError("pool_initial_out_of_bounds")
        if (not isinstance(self.aggregation_mode, str)
                or self.aggregation_mode not in {"none", "sum", "distribution", "ordered"}):
            raise PoolError("pool_aggregation_mode_invalid")
        if self.aggregation_mode == "distribution":
            if not isinstance(self.refold_model_ref, str) or not self.refold_model_ref:
                raise PoolError("pool_refold_model_required")
        elif self.refold_model_ref is not None:
            raise PoolError("pool_refold_model_unexpected")
        refs = [threshold.threshold_ref for threshold in self.thresholds]
        if len(refs) != len(set(refs)):
            raise PoolError("pool_threshold_duplicate")


PoolRefoldResolver = Callable[
    [str, tuple[tuple[str, Decimal], ...], str, Mapping[str, int]], Decimal
]


def aggregate_pool_values(
    values: Sequence[tuple[str, Decimal]],
    *,
    definition: PoolDefinition,
    refold: PoolRefoldResolver | None = None,
    trigger: str | None = None,
    input_revision_vector: Mapping[str, int] | None = None,
) -> Decimal | Mapping[str, Decimal] | tuple[tuple[str, Decimal], ...]:
    members = tuple(values)
    fact_types = [fact_type for fact_type, _ in members]
    if len(set(fact_types)) != len(fact_types):
        raise PoolError("pool_aggregate_member_duplicate")
    for fact_type, value in members:
        if not isinstance(fact_type, str) or not fact_type:
            raise PoolError("pool_aggregate_member_invalid")
        _finite_decimal(value, "pool_aggregate_value_invalid")
        _require_in_bounds(value, definition.lower, definition.upper)

    if definition.aggregation_mode in {"none", "ordered"}:
        if definition.aggregation_mode == "none":
            return MappingProxyType(dict(members))
        return members
    if definition.aggregation_mode == "sum":
        total = sum((value for _, value in members), Decimal(0))
        _finite_decimal(total, "pool_aggregate_value_invalid")
        return total

    if refold is None:
        raise PoolError("pool_refold_resolver_required")
    if trigger not in {"split", "merge", "fidelity_change", "scope_change", "casualty"}:
        raise PoolError("pool_refold_trigger_invalid")
    if (not isinstance(input_revision_vector, Mapping)
            or not set(fact_types).issubset(input_revision_vector)):
        raise PoolError("pool_refold_revision_vector_invalid")
    if any(type(revision) is not int or revision < 0 for revision in input_revision_vector.values()):
        raise PoolError("pool_refold_revision_vector_invalid")

    result = refold(
        definition.refold_model_ref,
        members,
        trigger,
        MappingProxyType(dict(sorted(input_revision_vector.items()))),
    )
    _finite_decimal(result, "pool_refold_result_invalid")
    _require_in_bounds(result, definition.lower, definition.upper)
    return result


@dataclass(frozen=True)
class PoolReservation:
    reservation_ref: str
    amount: Decimal
    holder_ref: str
    purpose_code: str


@dataclass(frozen=True)
class PoolProjection:
    fact_type: str
    lower: Decimal
    upper: Decimal
    value: Decimal
    reservations: Mapping[str, PoolReservation]
    integrated_windows: frozenset[str]
    active_thresholds: frozenset[str]
    source_revision: int

    @property
    def reserved(self) -> Decimal:
        return sum((item.amount for item in self.reservations.values()), Decimal(0))

    @property
    def available(self) -> Decimal:
        return self.value - self.reserved


class PoolProjector:
    _EVENT_TYPES = frozenset({
        "gameplay.pool.initialized", "gameplay.pool.adjusted", "gameplay.pool.reserved",
        "gameplay.pool.released", "gameplay.pool.consumed", "gameplay.pool.bound_changed",
        "gameplay.pool.threshold_crossed",
    })

    def rebuild(self, events: Sequence[GameplayEvent], *,
                definitions: Mapping[str, PoolDefinition] | None = None) -> PoolProjection:
        fact_type: str | None = None
        lower: Decimal | None = None
        upper: Decimal | None = None
        value: Decimal | None = None
        reservations: dict[str, PoolReservation] = {}
        integrated_windows: set[str] = set()
        active_thresholds: set[str] = set()
        previous_adjusted_value: Decimal | None = None
        previous_revision = 0
        for event in events:
            if event.event_type not in self._EVENT_TYPES or event.schema_version != 1:
                raise PoolError("pool_event_type_invalid")
            if event.stream_id != event.payload.get("fact_type"):
                raise PoolError("pool_event_stream_mismatch")
            if event.stream_revision != previous_revision + 1:
                raise PoolError("pool_event_revision_gap")
            payload = event.payload
            allowed_fields = {
                "gameplay.pool.initialized": {"fact_type", "initial", "bound_lower", "bound_upper"},
                "gameplay.pool.adjusted": {
                    "fact_type", "previous", "delta", "next", "window_ref", "model_ref", "reason_code",
                },
                "gameplay.pool.reserved": {
                    "fact_type", "reservation_ref", "amount", "holder_ref", "purpose_code",
                },
                "gameplay.pool.released": {"fact_type", "reservation_ref", "amount", "reason_code"},
                "gameplay.pool.consumed": {
                    "fact_type", "reservation_ref", "amount", "actual", "reason_code",
                },
                "gameplay.pool.bound_changed": {
                    "fact_type", "previous_lower", "previous_upper", "next_lower", "next_upper",
                    "authority_ref",
                },
                "gameplay.pool.threshold_crossed": {
                    "fact_type", "threshold_ref", "direction", "value",
                },
            }[event.event_type]
            required_fields = allowed_fields
            if event.event_type == "gameplay.pool.adjusted":
                required_fields = allowed_fields - {"window_ref", "model_ref"}
            elif event.event_type == "gameplay.pool.released":
                required_fields = allowed_fields - {"reason_code"}
            if set(payload) - allowed_fields or not required_fields.issubset(payload):
                raise PoolError("pool_event_payload_invalid")
            if event.event_type == "gameplay.pool.adjusted" and (
                "window_ref" in payload and not payload["window_ref"]
            ):
                raise PoolError("pool_event_payload_invalid")
            current_fact_type = _required_text(payload, "fact_type")
            if fact_type is None:
                fact_type = current_fact_type
            elif fact_type != current_fact_type:
                raise PoolError("pool_fact_type_mismatch")

            if event.event_type == "gameplay.pool.initialized":
                if value is not None or previous_revision != 0:
                    raise PoolError("pool_already_initialized")
                lower = _decimal(payload, "bound_lower")
                upper = _decimal(payload, "bound_upper")
                value = _decimal(payload, "initial")
                if lower > upper or not lower <= value <= upper:
                    raise PoolError("pool_initial_out_of_bounds")
            else:
                if value is None or lower is None or upper is None:
                    raise PoolError("pool_not_initialized")
                if event.event_type == "gameplay.pool.adjusted":
                    previous = _decimal(payload, "previous")
                    delta = _decimal(payload, "delta")
                    next_value = _decimal(payload, "next")
                    if previous != value or previous + delta != next_value:
                        raise PoolError("pool_adjustment_invalid")
                    if payload["reason_code"] not in PoolAuthorityService._REASONS:
                        raise PoolError("pool_adjust_reason_invalid")
                    previous_adjusted_value = value
                    value = next_value
                    window_ref = payload.get("window_ref")
                    if window_ref is not None:
                        window_ref = _required_text(payload, "window_ref")
                        if window_ref in integrated_windows:
                            raise PoolError("pool_window_already_integrated")
                        integrated_windows.add(window_ref)
                    _require_in_bounds(value, lower, upper)
                    if value < sum((item.amount for item in reservations.values()), Decimal(0)):
                        raise PoolError("pool_insufficient_available")
                elif event.event_type == "gameplay.pool.reserved":
                    reservation_ref = _required_text(payload, "reservation_ref")
                    amount = _decimal(payload, "amount")
                    holder_ref = _required_text(payload, "holder_ref")
                    purpose_code = _required_text(payload, "purpose_code")
                    if amount <= 0 or reservation_ref in reservations:
                        raise PoolError("pool_reservation_invalid")
                    if sum((item.amount for item in reservations.values()), Decimal(0)) + amount > value:
                        raise PoolError("pool_insufficient_available")
                    reservations[reservation_ref] = PoolReservation(
                        reservation_ref, amount, holder_ref, purpose_code
                    )
                elif event.event_type == "gameplay.pool.released":
                    reservation_ref = _required_text(payload, "reservation_ref")
                    reservation = reservations.pop(reservation_ref, None)
                    if reservation is None or _decimal(payload, "amount") != reservation.amount:
                        raise PoolError("pool_reservation_invalid")
                elif event.event_type == "gameplay.pool.consumed":
                    reservation_ref = _required_text(payload, "reservation_ref")
                    reservation = reservations.pop(reservation_ref, None)
                    amount = _decimal(payload, "amount")
                    actual = _decimal(payload, "actual")
                    if reservation is None or reservation.amount != amount or actual < 0 or actual > amount:
                        raise PoolError("pool_consumption_invalid")
                    if payload["reason_code"] not in PoolAuthorityService._CONSUME_REASONS:
                        raise PoolError("pool_consume_reason_invalid")
                    previous_adjusted_value = value
                    value -= actual
                    _require_in_bounds(value, lower, upper)
                    if value < sum((item.amount for item in reservations.values()), Decimal(0)):
                        raise PoolError("pool_insufficient_available")
                elif event.event_type == "gameplay.pool.bound_changed":
                    if (_decimal(payload, "previous_lower") != lower
                            or _decimal(payload, "previous_upper") != upper):
                        raise PoolError("pool_bound_change_invalid")
                    lower = _decimal(payload, "next_lower")
                    upper = _decimal(payload, "next_upper")
                    if lower > upper or not lower <= value <= upper:
                        raise PoolError("pool_bound_change_invalid")
                    _required_text(payload, "authority_ref")
                elif event.event_type == "gameplay.pool.threshold_crossed":
                    threshold_ref = _required_text(payload, "threshold_ref")
                    direction = payload.get("direction")
                    threshold_value = _decimal(payload, "value")
                    definition = None if definitions is None else definitions.get(fact_type)
                    if definition is not None:
                        threshold = next((
                            item for item in definition.thresholds
                            if item.threshold_ref == threshold_ref
                        ), None)
                        if threshold is None or previous_adjusted_value is None:
                            raise PoolError("pool_threshold_transition_invalid")
                        crossed_enter = (
                            threshold_ref not in active_thresholds
                            and previous_adjusted_value >= threshold.enter_below
                            and value < threshold.enter_below
                        )
                        crossed_exit = (
                            threshold_ref in active_thresholds
                            and previous_adjusted_value <= threshold.exit_above
                            and value > threshold.exit_above
                        )
                        if not ((direction == "enter" and crossed_enter)
                                or (direction == "exit" and crossed_exit)):
                            raise PoolError("pool_threshold_transition_invalid")
                    if direction == "enter" and threshold_ref not in active_thresholds:
                        active_thresholds.add(threshold_ref)
                    elif direction == "exit" and threshold_ref in active_thresholds:
                        active_thresholds.remove(threshold_ref)
                    else:
                        raise PoolError("pool_threshold_transition_invalid")
                    if threshold_value != value:
                        raise PoolError("pool_threshold_value_mismatch")
            previous_revision = event.stream_revision

        if fact_type is None or value is None or lower is None or upper is None:
            raise PoolError("pool_not_initialized")
        return PoolProjection(
            fact_type=fact_type,
            lower=lower,
            upper=upper,
            value=value,
            reservations=MappingProxyType(dict(reservations)),
            integrated_windows=frozenset(integrated_windows),
            active_thresholds=frozenset(active_thresholds),
            source_revision=previous_revision,
        )


class PoolAuthorityService:
    _PRINCIPAL = "owner:pool"
    _SOURCE_RULE_REF = "pool-runtime:owner-command@1"
    _REASONS = frozenset({"damage", "heal", "integrate", "restore", "grant", "manual_authority"})
    _CONSUME_REASONS = frozenset({"action_cost", "recipe_input", "treatment", "decay", "spoilage"})

    def __init__(self, *, store: GameplayEventStore,
                 definitions: Iterable[PoolDefinition] = (), owner_ref: str | None = None,
                 principal_ref: str | None = None) -> None:
        if any(value is not None and (not isinstance(value, str) or not value)
               for value in (owner_ref, principal_ref)):
            raise PoolError("pool_owner_ref_invalid")
        self._store = store
        self._owner_ref = owner_ref or principal_ref or self._PRINCIPAL
        self._principal_ref = principal_ref or self._PRINCIPAL
        self._projector = PoolProjector()
        self._definitions = {definition.fact_type: definition for definition in definitions}

    def initialize(self, *, definition: PoolDefinition, command_id: str, idempotency_key: str,
                   causation_id: str, correlation_id: str) -> AppendBatchResult:
        existing_definition = self._definitions.get(definition.fact_type)
        if existing_definition is not None and existing_definition != definition:
            raise PoolError("pool_definition_conflict")
        payload = {
            "fact_type": definition.fact_type,
            "initial": _decimal_text(definition.initial),
            "bound_lower": _decimal_text(definition.lower),
            "bound_upper": _decimal_text(definition.upper),
        }
        result = self._append(
            fact_type=definition.fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.pool.initialized", payload),), expected_revision=0,
            digest_payload={"kind": "initialize", **payload},
        )
        self._definitions[definition.fact_type] = definition
        return result

    def adjust(self, *, fact_type: str, delta: Decimal, reason_code: str, command_id: str,
               idempotency_key: str, expected_revision: int, causation_id: str,
               correlation_id: str, window_ref: str | None = None, model_ref: str | None = None,
               thresholds: tuple[PoolThreshold, ...] | None = None,
               input_revision_vector: Mapping[str, int] | None = None,
               read_stream_revisions: Mapping[str, int] | None = None,
               event_time: int | None = None) -> AppendBatchResult:
        _finite_decimal(delta, "pool_delta_invalid")
        if event_time is not None and (type(event_time) is not int or event_time < 0):
            raise PoolError("pool_event_time_invalid")
        if reason_code not in self._REASONS:
            raise PoolError("pool_adjust_reason_invalid")
        if window_ref is not None and not window_ref:
            raise PoolError("pool_window_invalid")
        if model_ref is not None and (not isinstance(model_ref, str) or not model_ref):
            raise PoolError("pool_model_ref_invalid")
        if model_ref is not None and input_revision_vector is None:
            raise PoolError("pool_model_revision_vector_invalid")
        if input_revision_vector is not None and (
            not isinstance(input_revision_vector, Mapping) or not input_revision_vector
            or any(
                not isinstance(stream_id, str) or not stream_id
                or type(revision) is not int or revision < 0
                for stream_id, revision in input_revision_vector.items()
            )
        ):
            raise PoolError("pool_model_revision_vector_invalid")
        if read_stream_revisions is not None and (
            not isinstance(read_stream_revisions, Mapping)
            or any(
                not isinstance(stream_id, str) or not stream_id
                or type(revision) is not int or revision < 0
                for stream_id, revision in read_stream_revisions.items()
            )
        ):
            raise PoolError("pool_model_read_revision_vector_invalid")
        digest_payload = {"kind": "adjust", "fact_type": fact_type, "delta": _decimal_text(delta),
                          "reason_code": reason_code, "window_ref": window_ref,
                          "model_ref": model_ref}
        if event_time is not None:
            digest_payload["event_time"] = event_time
        if input_revision_vector is not None:
            digest_payload["input_revision_vector"] = dict(input_revision_vector)
        if read_stream_revisions is not None:
            digest_payload["read_stream_revisions"] = dict(read_stream_revisions)
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        if window_ref is not None and window_ref in projection.integrated_windows:
            raise PoolError("pool_window_already_integrated")
        next_value = projection.value + delta
        _require_in_bounds(next_value, projection.lower, projection.upper)
        if next_value < projection.reserved:
            raise PoolError("pool_insufficient_available")
        event_specs: list[tuple[str, dict[str, object]]] = [("gameplay.pool.adjusted", {
            "fact_type": fact_type,
            "previous": _decimal_text(projection.value),
            "delta": _decimal_text(delta),
            "next": _decimal_text(next_value),
            **({"window_ref": window_ref} if window_ref is not None else {}),
            **({"model_ref": model_ref} if model_ref is not None else {}),
            "reason_code": reason_code,
        })]
        configured_thresholds = self._definition(fact_type).thresholds if thresholds is None else thresholds
        event_specs.extend(self._threshold_events(projection, next_value, configured_thresholds))
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=tuple(event_specs), expected_revision=expected_revision,
            digest_payload=digest_payload, input_revision_vector=input_revision_vector,
            read_stream_revisions=read_stream_revisions,
            event_time=event_time,
        )

    def integrate(self, *, fact_type: str, ticks: int, window_ref: str, command_id: str,
                  idempotency_key: str, expected_revision: int, causation_id: str,
                  correlation_id: str) -> AppendBatchResult:
        if type(ticks) is not int or ticks <= 0 or not window_ref:
            raise PoolError("pool_integration_invalid")
        delta = self._definition(fact_type).rate_per_tick * ticks
        return self.adjust(
            fact_type=fact_type, delta=delta, reason_code="integrate", window_ref=window_ref,
            command_id=command_id, idempotency_key=idempotency_key,
            expected_revision=expected_revision, causation_id=causation_id,
            correlation_id=correlation_id,
        )

    def reserve(self, *, fact_type: str, reservation_ref: str, amount: Decimal, holder_ref: str,
                purpose_code: str, command_id: str, idempotency_key: str,
                expected_revision: int, causation_id: str, correlation_id: str) -> AppendBatchResult:
        _finite_decimal(amount, "pool_reserve_amount_invalid")
        if amount <= 0 or not reservation_ref or not holder_ref or not purpose_code:
            raise PoolError("pool_reservation_invalid")
        payload = {"fact_type": fact_type, "reservation_ref": reservation_ref,
                   "amount": _decimal_text(amount), "holder_ref": holder_ref,
                   "purpose_code": purpose_code}
        digest_payload = {"kind": "reserve", **payload}
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        if reservation_ref in projection.reservations:
            raise PoolError("pool_reservation_duplicate")
        if amount > projection.available:
            raise PoolError("pool_insufficient_available")
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.pool.reserved", payload),), expected_revision=expected_revision,
            digest_payload=digest_payload,
        )

    def release(self, *, fact_type: str, reservation_ref: str, command_id: str,
                idempotency_key: str, expected_revision: int, causation_id: str,
                correlation_id: str, reason_code: str | None = None) -> AppendBatchResult:
        digest_payload: dict[str, object] = {
            "kind": "release", "fact_type": fact_type, "reservation_ref": reservation_ref,
        }
        if reason_code is not None:
            digest_payload["reason_code"] = reason_code
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        reservation = projection.reservations.get(reservation_ref)
        if reservation is None:
            raise PoolError("pool_reservation_unknown")
        payload: dict[str, object] = {"fact_type": fact_type, "reservation_ref": reservation_ref,
                                      "amount": _decimal_text(reservation.amount)}
        if reason_code is not None:
            payload["reason_code"] = reason_code
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.pool.released", payload),), expected_revision=expected_revision,
            digest_payload=digest_payload,
        )

    def consume(self, *, fact_type: str, reservation_ref: str, actual: Decimal,
                reason_code: str, command_id: str, idempotency_key: str,
                expected_revision: int, causation_id: str, correlation_id: str,
                thresholds: tuple[PoolThreshold, ...] | None = None) -> AppendBatchResult:
        _finite_decimal(actual, "pool_consumption_invalid")
        if reason_code not in self._CONSUME_REASONS:
            raise PoolError("pool_consume_reason_invalid")
        digest_payload = {"kind": "consume", "fact_type": fact_type,
                          "reservation_ref": reservation_ref, "actual": _decimal_text(actual),
                          "reason_code": reason_code}
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        reservation = projection.reservations.get(reservation_ref)
        if reservation is None:
            raise PoolError("pool_consume_without_reservation")
        if actual < 0 or actual > reservation.amount:
            raise PoolError("pool_consume_exceeds_reservation")
        next_value = projection.value - actual
        _require_in_bounds(next_value, projection.lower, projection.upper)
        specs: list[tuple[str, dict[str, object]]] = [("gameplay.pool.consumed", {
            "fact_type": fact_type, "reservation_ref": reservation_ref,
            "amount": _decimal_text(reservation.amount), "actual": _decimal_text(actual),
            "reason_code": reason_code,
        })]
        configured_thresholds = self._definition(fact_type).thresholds if thresholds is None else thresholds
        specs.extend(self._threshold_events(projection, next_value, configured_thresholds))
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=tuple(specs), expected_revision=expected_revision,
            digest_payload=digest_payload,
        )

    def set_bound(self, *, fact_type: str, new_lower: Decimal, new_upper: Decimal,
                  authority_ref: str, command_id: str, idempotency_key: str,
                  expected_revision: int, causation_id: str,
                  correlation_id: str) -> AppendBatchResult:
        _finite_decimal(new_lower, "pool_bounds_invalid")
        _finite_decimal(new_upper, "pool_bounds_invalid")
        if new_lower > new_upper or not authority_ref:
            raise PoolError("pool_bounds_invalid")
        digest_payload = {"kind": "set_bound", "fact_type": fact_type,
                          "next_lower": _decimal_text(new_lower),
                          "next_upper": _decimal_text(new_upper), "authority_ref": authority_ref}
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        if not new_lower <= projection.value <= new_upper:
            raise PoolError("pool_bound_change_invalid")
        payload = {"fact_type": fact_type, "previous_lower": _decimal_text(projection.lower),
                   "previous_upper": _decimal_text(projection.upper),
                   "next_lower": _decimal_text(new_lower), "next_upper": _decimal_text(new_upper),
                   "authority_ref": authority_ref}
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.pool.bound_changed", payload),), expected_revision=expected_revision,
            digest_payload=digest_payload,
        )

    def _threshold_events(self, projection: PoolProjection, next_value: Decimal,
                          thresholds: tuple[PoolThreshold, ...]) -> list[tuple[str, dict[str, object]]]:
        specs = []
        for threshold in thresholds:
            active = threshold.threshold_ref in projection.active_thresholds
            direction = None
            if not active and next_value < threshold.enter_below:
                direction = "enter"
            elif active and next_value > threshold.exit_above:
                direction = "exit"
            if direction is not None:
                specs.append(("gameplay.pool.threshold_crossed", {
                    "fact_type": projection.fact_type,
                    "threshold_ref": threshold.threshold_ref,
                    "direction": direction,
                    "value": _decimal_text(next_value),
                }))
        return specs

    def _read(self, fact_type: str) -> PoolProjection:
        return self._projector.rebuild(
            self._store.read_stream(fact_type), definitions=self._definitions
        )

    def _definition(self, fact_type: str) -> PoolDefinition:
        definition = self._definitions.get(fact_type)
        if definition is None:
            raise PoolError("pool_definition_unavailable")
        return definition

    def _append(self, *, fact_type: str, command_id: str, idempotency_key: str,
                causation_id: str, correlation_id: str,
                event_specs: Sequence[tuple[str, Mapping[str, object]]], expected_revision: int,
                digest_payload: Mapping[str, object],
                input_revision_vector: Mapping[str, int] | None = None,
                read_stream_revisions: Mapping[str, int] | None = None,
                event_time: int | None = None) -> AppendBatchResult:
        if not command_id or not idempotency_key or not causation_id or not correlation_id:
            raise PoolError("pool_command_identity_invalid")
        digest = "sha256:" + sha256(_canonical_json(digest_payload)).hexdigest()
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        transaction_id = f"tx:{command_id}"
        events = [{
            "event_id": f"evt:{command_id}:pool:{index}", "event_type": event_type,
            "schema_version": 1, "stream_id": fact_type, "stream_revision": 0,
            "global_sequence": 0, "transaction_id": transaction_id, "command_id": command_id,
            "causation_id": causation_id, "correlation_id": correlation_id,
            "visibility_policy": "authority_only", "payload": dict(payload),
            **({"event_time": event_time} if event_time is not None else {}),
        } for index, (event_type, payload) in enumerate(event_specs)]
        read_revisions = {fact_type: expected_revision}
        revision_vector = (
            input_revision_vector
            if read_stream_revisions is None
            else read_stream_revisions
        )
        if revision_vector is not None:
            for stream_id, revision in revision_vector.items():
                if stream_id in read_revisions and read_revisions[stream_id] != revision:
                    raise PoolError("pool_model_revision_vector_invalid")
                read_revisions[stream_id] = revision
        pinned_revisions = dict(read_revisions)
        if input_revision_vector is not None and read_stream_revisions is not None:
            pinned_revisions.update({
                f"input:{stream_id}": revision
                for stream_id, revision in input_revision_vector.items()
            })
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:pool:{command_id}",
            owner_principal_ref=self._owner_ref,
            source_rule_ref=self._SOURCE_RULE_REF,
            expected_revisions={fact_type: expected_revision},
            read_set_revisions=read_revisions,
            event_specs={fact_type: tuple(
                (event_type, dict(payload)) for event_type, payload in event_specs
            )},
            event_visibility_policies={fact_type: tuple(
                "authority_only" for _ in event_specs
            )},
            pinned_revisions=pinned_revisions,
        )
        batch = OwnerCommitBuilder.build(
            principal_ref=self._principal_ref, command_id=command_id, transaction_id=transaction_id,
            idempotency_key=idempotency_key, payload_digest=digest, events=events,
            expected_stream_revisions={fact_type: expected_revision},
            pinned_revisions=pinned_revisions, result_digest=digest,
            read_stream_revisions=read_revisions,
        )
        batch["owner_fragments"] = [fragment.model_dump(mode="python")]
        result = self._store.append_batch(batch)
        if not result.committed:
            failure = result.failure
            raise PoolError(failure.error_code if failure is not None else "pool_append_rejected")
        return result

    def _duplicate(self, idempotency_key: str,
                   digest_payload: Mapping[str, object]) -> AppendBatchResult | None:
        digest = "sha256:" + sha256(_canonical_json(digest_payload)).hexdigest()
        return replay_duplicate(
            self._store, principal=self._principal_ref, idempotency_key=idempotency_key,
            payload_digest=digest, error_factory=PoolError,
            missing_result_code="pool_idempotency_missing_result",
        )


def _require_revision(expected: int, actual: int) -> None:
    if type(expected) is not int or expected != actual:
        raise PoolError("revision_conflict")


def _finite_decimal(value: Decimal, error_code: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise PoolError(error_code)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _decimal(payload: Mapping[str, object], key: str) -> Decimal:
    value = payload.get(key)
    if type(value) is not str:
        raise PoolError("pool_event_payload_invalid")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise PoolError("pool_event_payload_invalid") from exc
    if not result.is_finite():
        raise PoolError("pool_event_payload_invalid")
    return result


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if type(value) is not str or not value:
        raise PoolError("pool_event_payload_invalid")
    return value


def _require_in_bounds(value: Decimal, lower: Decimal, upper: Decimal) -> None:
    if value < lower:
        raise PoolError("pool_lower_bound_exceeded")
    if value > upper:
        raise PoolError("pool_upper_bound_exceeded")


def _canonical_json(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
