"""Event-sourced bounded value pools with reservations and hysteresis."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent
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

    def __post_init__(self) -> None:
        if not self.fact_type or any(
            not value.is_finite() for value in (self.lower, self.upper, self.initial, self.rate_per_tick)
        ):
            raise PoolError("pool_definition_invalid")
        if self.lower > self.upper:
            raise PoolError("pool_bounds_invalid")
        if not self.lower <= self.initial <= self.upper:
            raise PoolError("pool_initial_out_of_bounds")
        refs = [threshold.threshold_ref for threshold in self.thresholds]
        if len(refs) != len(set(refs)):
            raise PoolError("pool_threshold_duplicate")


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
    _REASONS = frozenset({"damage", "heal", "integrate", "restore", "grant", "manual_authority"})
    _CONSUME_REASONS = frozenset({"action_cost", "recipe_input", "treatment", "decay", "spoilage"})

    def __init__(self, *, store: GameplayEventStore,
                 definitions: Iterable[PoolDefinition] = ()) -> None:
        self._store = store
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
               thresholds: tuple[PoolThreshold, ...] | None = None) -> AppendBatchResult:
        _finite_decimal(delta, "pool_delta_invalid")
        if reason_code not in self._REASONS:
            raise PoolError("pool_adjust_reason_invalid")
        if window_ref is not None and not window_ref:
            raise PoolError("pool_window_invalid")
        digest_payload = {"kind": "adjust", "fact_type": fact_type, "delta": _decimal_text(delta),
                          "reason_code": reason_code, "window_ref": window_ref,
                          "model_ref": model_ref}
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
            digest_payload=digest_payload,
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
                digest_payload: Mapping[str, object]) -> AppendBatchResult:
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
        } for index, (event_type, payload) in enumerate(event_specs)]
        result = self._store.append_batch(OwnerCommitBuilder.build(
            principal_ref=self._PRINCIPAL, command_id=command_id, transaction_id=transaction_id,
            idempotency_key=idempotency_key, payload_digest=digest, events=events,
            expected_stream_revisions={fact_type: expected_revision},
            pinned_revisions={"pool": expected_revision}, result_digest=digest,
        ))
        if not result.committed:
            failure = result.failure
            raise PoolError(failure.error_code if failure is not None else "pool_append_rejected")
        return result

    def _duplicate(self, idempotency_key: str,
                   digest_payload: Mapping[str, object]) -> AppendBatchResult | None:
        digest = "sha256:" + sha256(_canonical_json(digest_payload)).hexdigest()
        return replay_duplicate(
            self._store, principal=self._PRINCIPAL, idempotency_key=idempotency_key,
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
