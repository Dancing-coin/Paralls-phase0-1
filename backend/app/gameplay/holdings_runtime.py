"""Event-sourced Holdings primitives for conserved quantities."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, OwnerAuthorizedFragment
from app.gameplay.owner_runtime_base import OwnerCommitBuilder, replay_duplicate


class HoldingsError(ValueError):
    pass


@dataclass(frozen=True)
class HoldingsDefinition:
    fact_type: str
    capacity: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.fact_type, str) or not self.fact_type:
            raise HoldingsError("holdings_definition_invalid")
        if self.capacity is not None:
            _finite_decimal(self.capacity, "holdings_capacity_invalid")
            if self.capacity < 0:
                raise HoldingsError("holdings_capacity_invalid")


@dataclass(frozen=True)
class HoldingsItemDefinition:
    item_ref: str
    unit_ref: str
    specification_ref: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (
            self.item_ref, self.unit_ref, self.specification_ref,
        )):
            raise HoldingsError("holdings_item_definition_invalid")


@dataclass(frozen=True)
class HoldingsReservation:
    reservation_ref: str
    lot_ref: str
    amount: Decimal


@dataclass(frozen=True)
class HoldingsLot:
    lot_ref: str
    item_ref: str
    container_ref: str
    quantity: Decimal
    reservations: Mapping[str, HoldingsReservation]

    @property
    def reserved_quantity(self) -> Decimal:
        return sum((reservation.amount for reservation in self.reservations.values()), Decimal(0))

    @property
    def available_quantity(self) -> Decimal:
        return self.quantity


@dataclass(frozen=True)
class HoldingsSumEntry:
    item_ref: str
    unit_ref: str
    specification_ref: str
    available_quantity: Decimal
    reserved_quantity: Decimal

    @property
    def total_quantity(self) -> Decimal:
        return self.available_quantity + self.reserved_quantity


@dataclass(frozen=True)
class HoldingsProjection:
    fact_type: str
    lots: Mapping[str, HoldingsLot]
    source_revision: int
    closed_lot_refs: frozenset[str] = frozenset()
    sum_by_item: Mapping[str, HoldingsSumEntry] = field(
        default_factory=lambda: MappingProxyType({})
    )

    @property
    def total_quantity(self) -> Decimal:
        return sum((lot.quantity + lot.reserved_quantity for lot in self.lots.values()), Decimal(0))

    @property
    def reserved_quantity(self) -> Decimal:
        return sum((lot.reserved_quantity for lot in self.lots.values()), Decimal(0))

    @property
    def available_quantity(self) -> Decimal:
        return sum((lot.quantity for lot in self.lots.values()), Decimal(0))


class HoldingsProjector:
    _EVENT_TYPES = frozenset({
        "gameplay.holdings.lot_created",
        "gameplay.holdings.reserved",
        "gameplay.holdings.transferred",
        "gameplay.holdings.consumed",
        "gameplay.holdings.split",
        "gameplay.holdings.merged",
        "gameplay.holdings.lost",
        "gameplay.holdings.reservation_released",
        "gameplay.holdings.reservation_settled",
        "gameplay.holdings.reservation_transferred",
    })

    def rebuild(
        self,
        events: Sequence[GameplayEvent],
        *,
        definition: HoldingsDefinition,
        item_definitions: Mapping[str, HoldingsItemDefinition],
        checkpoint_at: int | None = None,
    ) -> HoldingsProjection:
        if checkpoint_at is not None:
            if isinstance(checkpoint_at, bool) or not isinstance(checkpoint_at, int) or checkpoint_at < 0:
                raise HoldingsError("holdings_checkpoint_invalid")
            prefix = [event for event in events if event.global_sequence <= checkpoint_at]
            suffix = [event for event in events if event.global_sequence > checkpoint_at]
            checkpoint = self.rebuild(
                prefix, definition=definition, item_definitions=item_definitions,
            )
            lots = {
                lot_ref: {
                    "item_ref": lot.item_ref,
                    "container_ref": lot.container_ref,
                    "quantity": lot.quantity,
                }
                for lot_ref, lot in checkpoint.lots.items()
            }
            reservations = {
                reservation_ref: reservation
                for lot in checkpoint.lots.values()
                for reservation_ref, reservation in lot.reservations.items()
            }
            return self._rebuild_events(
                suffix,
                definition=definition,
                item_definitions=item_definitions,
                lots=lots,
                reservations=reservations,
                closed_lots=set(checkpoint.closed_lot_refs),
                previous_revision=checkpoint.source_revision,
            )
        return self._rebuild_events(
            events,
            definition=definition,
            item_definitions=item_definitions,
            lots={},
            reservations={},
            closed_lots=set(),
            previous_revision=0,
        )

    def _rebuild_events(
        self,
        events: Sequence[GameplayEvent],
        *,
        definition: HoldingsDefinition,
        item_definitions: Mapping[str, HoldingsItemDefinition],
        lots: dict[str, dict[str, object]],
        reservations: dict[str, HoldingsReservation],
        closed_lots: set[str],
        previous_revision: int,
    ) -> HoldingsProjection:
        for event in events:
            if event.stream_id != definition.fact_type:
                raise HoldingsError("holdings_event_stream_mismatch")
            if event.event_type not in self._EVENT_TYPES or event.schema_version != 1:
                raise HoldingsError("holdings_event_type_invalid")
            if event.stream_revision != previous_revision + 1:
                raise HoldingsError("holdings_event_revision_gap")
            previous_revision = event.stream_revision
            payload = event.payload

            if event.event_type == "gameplay.holdings.lot_created":
                lot_ref = _text(payload, "lot_ref")
                item_ref = _text(payload, "item_ref")
                container_ref = _text(payload, "container_ref")
                quantity = _decimal(payload, "quantity")
                if lot_ref in lots or lot_ref in closed_lots:
                    raise HoldingsError("holdings_lot_duplicate")
                if item_ref not in item_definitions:
                    raise HoldingsError("holdings_item_definition_unknown")
                if quantity <= 0:
                    raise HoldingsError("holdings_lot_quantity_invalid")
                if "quality" in payload:
                    _decimal(payload, "quality")
                lots[lot_ref] = {
                    "item_ref": item_ref,
                    "container_ref": container_ref,
                    "quantity": quantity,
                }
            elif event.event_type == "gameplay.holdings.reserved":
                lot_ref = _text(payload, "lot_ref")
                reservation_ref = _text(payload, "reservation_ref")
                amount = _decimal(payload, "amount")
                lot = lots.get(lot_ref)
                if lot is None or lot_ref in closed_lots:
                    raise HoldingsError("holdings_lot_unknown")
                if amount <= 0 or reservation_ref in reservations:
                    raise HoldingsError("holdings_reservation_invalid")
                if amount > lot["quantity"]:
                    raise HoldingsError("holdings_insufficient_available")
                lot["quantity"] -= amount
                reservations[reservation_ref] = HoldingsReservation(reservation_ref, lot_ref, amount)
            elif event.event_type == "gameplay.holdings.reservation_released":
                reservation_ref = _text(payload, "reservation_ref")
                reservation = reservations.get(reservation_ref)
                if reservation is None:
                    raise HoldingsError("holdings_reservation_unknown")
                if _text(payload, "lot_ref") != reservation.lot_ref:
                    raise HoldingsError("holdings_reservation_lot_mismatch")
                if _decimal(payload, "amount") != reservation.amount:
                    raise HoldingsError("holdings_reservation_amount_mismatch")
                lots[reservation.lot_ref]["quantity"] += reservation.amount
                del reservations[reservation_ref]
            elif event.event_type == "gameplay.holdings.reservation_settled":
                reservation_ref = _text(payload, "reservation_ref")
                reservation = reservations.get(reservation_ref)
                if reservation is None:
                    raise HoldingsError("holdings_reservation_unknown")
                if _text(payload, "lot_ref") != reservation.lot_ref:
                    raise HoldingsError("holdings_reservation_lot_mismatch")
                if _decimal(payload, "reserved_amount") != reservation.amount:
                    raise HoldingsError("holdings_reservation_amount_mismatch")
                actual = _decimal(payload, "actual")
                if _text(payload, "reason_code") not in HoldingsAuthorityService._SETTLEMENT_REASONS:
                    raise HoldingsError("holdings_settlement_invalid")
                if actual < 0 or actual > reservation.amount:
                    raise HoldingsError("holdings_settlement_exceeds_reservation")
                lot = lots[reservation.lot_ref]
                lot["quantity"] += reservation.amount - actual
                del reservations[reservation_ref]
            elif event.event_type == "gameplay.holdings.transferred":
                source_ref = _text(payload, "src_lot_ref")
                destination_ref = _text(payload, "dst_lot_ref")
                amount = _decimal(payload, "amount")
                source = _active_lot(lots, closed_lots, source_ref)
                destination = _active_lot(lots, closed_lots, destination_ref)
                if source_ref == destination_ref:
                    raise HoldingsError("holdings_transfer_lot_invalid")
                if "step_ref" in payload:
                    _text(payload, "step_ref")
                if amount <= 0 or amount > source["quantity"]:
                    raise HoldingsError("holdings_transfer_amount_invalid")
                _require_compatible_items(source, destination, item_definitions)
                source["quantity"] -= amount
                destination["quantity"] += amount
            elif event.event_type == "gameplay.holdings.reservation_transferred":
                reservation_ref = _text(payload, "reservation_ref")
                source_ref = _text(payload, "src_lot_ref")
                destination_ref = _text(payload, "dst_lot_ref")
                amount = _decimal(payload, "amount")
                source = _active_lot(lots, closed_lots, source_ref)
                destination = _active_lot(lots, closed_lots, destination_ref)
                reservation = reservations.get(reservation_ref)
                if reservation is None or reservation.lot_ref != source_ref:
                    raise HoldingsError("holdings_reservation_unknown")
                if source_ref == destination_ref or amount != reservation.amount:
                    raise HoldingsError("holdings_transfer_amount_invalid")
                if "step_ref" in payload:
                    _text(payload, "step_ref")
                _require_compatible_items(source, destination, item_definitions)
                # Moving the reservation reference and held quantity is one event.
                reservations[reservation_ref] = HoldingsReservation(reservation_ref, destination_ref, amount)
            elif event.event_type in {"gameplay.holdings.consumed", "gameplay.holdings.lost"}:
                lot_ref = _text(payload, "lot_ref")
                lot = _active_lot(lots, closed_lots, lot_ref)
                amount = _decimal(payload, "amount")
                reason_key = "reason_code"
                _text(payload, reason_key)
                if amount <= 0 or amount > lot["quantity"]:
                    raise HoldingsError("holdings_quantity_reduction_invalid")
                lot["quantity"] -= amount
            elif event.event_type == "gameplay.holdings.split":
                source_ref = _text(payload, "source_lot_ref")
                source = _active_lot(lots, closed_lots, source_ref)
                result_refs = _text_list(payload, "result_lot_refs", maximum=32, minimum=1)
                amounts = _decimal_list(payload, "amounts", expected_length=len(result_refs))
                if any(reservation.lot_ref == source_ref for reservation in reservations.values()):
                    raise HoldingsError("holdings_reserved_lot_cannot_split")
                if len(set(result_refs)) != len(result_refs) or source_ref in result_refs:
                    raise HoldingsError("holdings_split_lots_invalid")
                if any(ref in lots or ref in closed_lots for ref in result_refs):
                    raise HoldingsError("holdings_lot_duplicate")
                if any(amount <= 0 for amount in amounts) or sum(amounts, Decimal(0)) != source["quantity"]:
                    raise HoldingsError("holdings_split_quantity_mismatch")
                for result_ref, amount in zip(result_refs, amounts, strict=True):
                    lots[result_ref] = {**source, "quantity": amount}
                source["quantity"] = Decimal(0)
                closed_lots.add(source_ref)
            elif event.event_type == "gameplay.holdings.merged":
                source_refs = _text_list(payload, "source_lot_refs", maximum=32, minimum=2)
                result_ref = _text(payload, "result_lot_ref")
                if len(set(source_refs)) != len(source_refs) or result_ref in lots or result_ref in closed_lots:
                    raise HoldingsError("holdings_merge_lots_invalid")
                sources = [_active_lot(lots, closed_lots, ref) for ref in source_refs]
                if any(any(reservation.lot_ref == ref for reservation in reservations.values()) for ref in source_refs):
                    raise HoldingsError("holdings_reserved_lot_cannot_merge")
                if any(source["container_ref"] != sources[0]["container_ref"] for source in sources):
                    raise HoldingsError("holdings_merge_container_mismatch")
                _require_compatible_items(sources[0], sources[1], item_definitions)
                for source in sources[2:]:
                    _require_compatible_items(sources[0], source, item_definitions)
                quantity = sum((source["quantity"] for source in sources), Decimal(0))
                lots[result_ref] = {**sources[0], "quantity": quantity}
                for ref, source in zip(source_refs, sources, strict=True):
                    source["quantity"] = Decimal(0)
                    closed_lots.add(ref)

            if definition.capacity is not None and sum(
                (lot["quantity"] for lot in lots.values()), Decimal(0)
            ) + sum((reservation.amount for reservation in reservations.values()), Decimal(0)) > definition.capacity:
                raise HoldingsError("holdings_capacity_exceeded")

        projected_lots = {
            lot_ref: HoldingsLot(
                lot_ref=lot_ref,
                item_ref=values["item_ref"],
                container_ref=values["container_ref"],
                quantity=values["quantity"],
                reservations=MappingProxyType({
                    reservation_ref: reservation
                    for reservation_ref, reservation in reservations.items()
                    if reservation.lot_ref == lot_ref
                }),
            )
            for lot_ref, values in lots.items()
        }
        distribution_totals: dict[str, dict[str, Decimal]] = {}
        for lot in projected_lots.values():
            item_totals = distribution_totals.setdefault(lot.item_ref, {
                "available_quantity": Decimal(0),
                "reserved_quantity": Decimal(0),
            })
            item_totals["available_quantity"] += lot.available_quantity
            item_totals["reserved_quantity"] += lot.reserved_quantity
        distribution = MappingProxyType({
            item_ref: HoldingsSumEntry(
                item_ref=item_ref,
                unit_ref=item_definitions[item_ref].unit_ref,
                specification_ref=item_definitions[item_ref].specification_ref,
                available_quantity=totals["available_quantity"],
                reserved_quantity=totals["reserved_quantity"],
            )
            for item_ref, totals in sorted(distribution_totals.items())
        })
        return HoldingsProjection(
            fact_type=definition.fact_type,
            lots=MappingProxyType(projected_lots),
            source_revision=previous_revision,
            closed_lot_refs=frozenset(closed_lots),
            sum_by_item=distribution,
        )


class HoldingsAuthorityService:
    _PRINCIPAL = "owner:holdings"
    _SOURCE_RULE_REF = "holdings-runtime:owner-command@1"
    _SETTLEMENT_REASONS = frozenset({"action_cost", "recipe_input", "treatment", "decay", "spoilage"})

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        definitions: Mapping[str, HoldingsDefinition],
        item_definitions: Mapping[str, HoldingsItemDefinition],
        owner_ref: str | None = None,
        principal_ref: str | None = None,
    ) -> None:
        if any(value is not None and (not isinstance(value, str) or not value)
               for value in (owner_ref, principal_ref)):
            raise HoldingsError("holdings_owner_ref_invalid")
        if any(key != definition.fact_type for key, definition in definitions.items()):
            raise HoldingsError("holdings_definition_registry_invalid")
        if any(key != definition.item_ref for key, definition in item_definitions.items()):
            raise HoldingsError("holdings_item_registry_invalid")
        self._store = store
        self._definitions = MappingProxyType(dict(definitions))
        self._item_definitions = MappingProxyType(dict(item_definitions))
        self._owner_ref = owner_ref or principal_ref or self._PRINCIPAL
        self._principal_ref = principal_ref or self._PRINCIPAL
        self._projector = HoldingsProjector()

    def create_lot(
        self,
        *,
        fact_type: str,
        lot_ref: str,
        item_ref: str,
        quantity: Decimal,
        container_ref: str,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        _finite_decimal(quantity, "holdings_lot_quantity_invalid")
        if quantity <= 0 or not lot_ref or not container_ref:
            raise HoldingsError("holdings_lot_identity_invalid")
        self._item_definition(item_ref)
        payload = {
            "lot_ref": lot_ref,
            "item_ref": item_ref,
            "quantity": _decimal_text(quantity),
            "container_ref": container_ref,
        }
        digest_payload = {"kind": "lot_created", "fact_type": fact_type, **payload}
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        if lot_ref in projection.lots:
            raise HoldingsError("holdings_lot_duplicate")
        self._require_capacity(fact_type, projection.total_quantity + quantity)
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.holdings.lot_created", payload),),
            expected_revision=expected_revision, digest_payload=digest_payload,
        )

    def reserve(
        self,
        *,
        fact_type: str,
        lot_ref: str,
        reservation_ref: str,
        amount: Decimal,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        _finite_decimal(amount, "holdings_reservation_invalid")
        if amount <= 0 or not lot_ref or not reservation_ref:
            raise HoldingsError("holdings_reservation_invalid")
        payload = {"lot_ref": lot_ref, "reservation_ref": reservation_ref, "amount": _decimal_text(amount)}
        digest_payload = {"kind": "reserve", "fact_type": fact_type, **payload}
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        lot = projection.lots.get(lot_ref)
        if lot is None:
            raise HoldingsError("holdings_lot_unknown")
        if any(reservation_ref in existing.reservations for existing in projection.lots.values()):
            raise HoldingsError("holdings_reservation_duplicate")
        if amount > lot.available_quantity:
            raise HoldingsError("holdings_insufficient_available")
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.holdings.reserved", payload),),
            expected_revision=expected_revision, digest_payload=digest_payload,
        )

    def release(
        self,
        *,
        fact_type: str,
        reservation_ref: str,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        digest_payload = {"kind": "release", "fact_type": fact_type, "reservation_ref": reservation_ref}
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        reservation = _find_reservation(projection, reservation_ref)
        payload = {
            "lot_ref": reservation.lot_ref,
            "reservation_ref": reservation_ref,
            "amount": _decimal_text(reservation.amount),
        }
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.holdings.reservation_released", payload),),
            expected_revision=expected_revision, digest_payload=digest_payload,
        )

    def settle_reservation(
        self,
        *,
        fact_type: str,
        reservation_ref: str,
        actual: Decimal,
        reason_code: str,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        _finite_decimal(actual, "holdings_settlement_invalid")
        if actual < 0 or reason_code not in self._SETTLEMENT_REASONS:
            raise HoldingsError("holdings_settlement_invalid")
        digest_payload = {
            "kind": "settle_reservation", "fact_type": fact_type,
            "reservation_ref": reservation_ref, "actual": _decimal_text(actual),
            "reason_code": reason_code,
        }
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        reservation = _find_reservation(projection, reservation_ref)
        if actual > reservation.amount:
            raise HoldingsError("holdings_settlement_exceeds_reservation")
        payload = {
            "lot_ref": reservation.lot_ref, "reservation_ref": reservation_ref,
            "reserved_amount": _decimal_text(reservation.amount),
            "actual": _decimal_text(actual), "reason_code": reason_code,
        }
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.holdings.reservation_settled", payload),),
            expected_revision=expected_revision, digest_payload=digest_payload,
        )

    def transfer(
        self,
        *,
        fact_type: str,
        source_lot_ref: str,
        destination_lot_ref: str,
        amount: Decimal,
        step_ref: str | None = None,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        _finite_decimal(amount, "holdings_transfer_amount_invalid")
        if amount <= 0 or not source_lot_ref or not destination_lot_ref or source_lot_ref == destination_lot_ref:
            raise HoldingsError("holdings_transfer_lot_invalid")
        if step_ref is not None and not step_ref:
            raise HoldingsError("holdings_transfer_step_invalid")
        payload = {
            "src_lot_ref": source_lot_ref,
            "dst_lot_ref": destination_lot_ref,
            "amount": _decimal_text(amount),
        }
        if step_ref is not None:
            payload["step_ref"] = step_ref
        digest_payload = {"kind": "transfer", "fact_type": fact_type, **payload}
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        source = _projection_lot(projection, source_lot_ref)
        destination = _projection_lot(projection, destination_lot_ref)
        _require_compatible_items(source, destination, self._item_definitions)
        if amount > source.quantity:
            raise HoldingsError("holdings_insufficient_available")
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.holdings.transferred", payload),),
            expected_revision=expected_revision, digest_payload=digest_payload,
        )

    def transfer_reservation(
        self,
        *,
        fact_type: str,
        reservation_ref: str,
        destination_lot_ref: str,
        step_ref: str | None = None,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if not reservation_ref or not destination_lot_ref:
            raise HoldingsError("holdings_transfer_lot_invalid")
        if step_ref is not None and not step_ref:
            raise HoldingsError("holdings_transfer_step_invalid")
        digest_payload = {
            "kind": "transfer_reservation", "fact_type": fact_type,
            "reservation_ref": reservation_ref, "destination_lot_ref": destination_lot_ref,
            "step_ref": step_ref,
        }
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        reservation = _find_reservation(projection, reservation_ref)
        if reservation.lot_ref == destination_lot_ref:
            raise HoldingsError("holdings_transfer_lot_invalid")
        source = _projection_lot(projection, reservation.lot_ref)
        destination = _projection_lot(projection, destination_lot_ref)
        _require_compatible_items(source, destination, self._item_definitions)
        payload = {
            "reservation_ref": reservation_ref,
            "src_lot_ref": reservation.lot_ref,
            "dst_lot_ref": destination_lot_ref,
            "amount": _decimal_text(reservation.amount),
        }
        if step_ref is not None:
            payload["step_ref"] = step_ref
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.holdings.reservation_transferred", payload),),
            expected_revision=expected_revision, digest_payload=digest_payload,
        )

    def consume(
        self,
        *,
        fact_type: str,
        lot_ref: str,
        amount: Decimal,
        reason_code: str,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        return self._reduce_quantity(
            event_type="gameplay.holdings.consumed", kind="consume",
            fact_type=fact_type, lot_ref=lot_ref, amount=amount, reason_code=reason_code,
            command_id=command_id, idempotency_key=idempotency_key,
            expected_revision=expected_revision, causation_id=causation_id,
            correlation_id=correlation_id,
        )

    def lose(
        self,
        *,
        fact_type: str,
        lot_ref: str,
        amount: Decimal,
        reason_code: str,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        return self._reduce_quantity(
            event_type="gameplay.holdings.lost", kind="lose",
            fact_type=fact_type, lot_ref=lot_ref, amount=amount, reason_code=reason_code,
            command_id=command_id, idempotency_key=idempotency_key,
            expected_revision=expected_revision, causation_id=causation_id,
            correlation_id=correlation_id,
        )

    def _reduce_quantity(
        self,
        *,
        event_type: str,
        kind: str,
        fact_type: str,
        lot_ref: str,
        amount: Decimal,
        reason_code: str,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        _finite_decimal(amount, "holdings_quantity_reduction_invalid")
        if amount <= 0 or not reason_code:
            raise HoldingsError("holdings_quantity_reduction_invalid")
        payload = {"lot_ref": lot_ref, "amount": _decimal_text(amount), "reason_code": reason_code}
        digest_payload = {"kind": kind, "fact_type": fact_type, **payload}
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        lot = _projection_lot(projection, lot_ref)
        if amount > lot.quantity:
            raise HoldingsError("holdings_insufficient_available")
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=((event_type, payload),), expected_revision=expected_revision,
            digest_payload=digest_payload,
        )

    def project(self, fact_type: str) -> HoldingsProjection:
        return self._read(fact_type)

    def _read(self, fact_type: str) -> HoldingsProjection:
        return self._projector.rebuild(
            self._store.read_stream(fact_type),
            definition=self._definition(fact_type),
            item_definitions=self._item_definitions,
        )

    def _definition(self, fact_type: str) -> HoldingsDefinition:
        try:
            return self._definitions[fact_type]
        except KeyError as exc:
            raise HoldingsError("holdings_definition_unavailable") from exc

    def _item_definition(self, item_ref: str) -> HoldingsItemDefinition:
        try:
            return self._item_definitions[item_ref]
        except KeyError as exc:
            raise HoldingsError("holdings_item_definition_unknown") from exc

    def _require_capacity(self, fact_type: str, next_total: Decimal) -> None:
        capacity = self._definition(fact_type).capacity
        if capacity is not None and next_total > capacity:
            raise HoldingsError("holdings_capacity_exceeded")

    def _duplicate(self, idempotency_key: str, payload: Mapping[str, object]) -> AppendBatchResult | None:
        digest = "sha256:" + sha256(_canonical_json(payload)).hexdigest()
        return replay_duplicate(
            self._store, principal=self._principal_ref, idempotency_key=idempotency_key,
            payload_digest=digest, error_factory=HoldingsError,
            missing_result_code="holdings_idempotency_missing_result",
        )

    def _append(
        self,
        *,
        fact_type: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        event_specs: Sequence[tuple[str, Mapping[str, object]]],
        expected_revision: int,
        digest_payload: Mapping[str, object],
    ) -> AppendBatchResult:
        if not command_id or not idempotency_key or not causation_id or not correlation_id:
            raise HoldingsError("holdings_command_identity_invalid")
        digest = "sha256:" + sha256(_canonical_json(digest_payload)).hexdigest()
        transaction_id = f"tx:{command_id}"
        events = [
            {
                "event_id": f"evt:{command_id}:holdings:{index}",
                "event_type": event_type,
                "schema_version": 1,
                "stream_id": fact_type,
                "stream_revision": 0,
                "global_sequence": 0,
                "transaction_id": transaction_id,
                "command_id": command_id,
                "causation_id": causation_id,
                "correlation_id": correlation_id,
                "visibility_policy": "authority_only",
                "payload": dict(payload),
            }
            for index, (event_type, payload) in enumerate(event_specs)
        ]
        fragment = OwnerAuthorizedFragment(
            fragment_id=f"fragment:holdings:{command_id}",
            owner_principal_ref=self._owner_ref,
            source_rule_ref=self._SOURCE_RULE_REF,
            expected_revisions={fact_type: expected_revision},
            read_set_revisions={fact_type: expected_revision},
            event_specs={fact_type: tuple((event_type, dict(payload)) for event_type, payload in event_specs)},
            event_visibility_policies={fact_type: tuple("authority_only" for _ in event_specs)},
            pinned_revisions={fact_type: expected_revision},
        )
        batch = OwnerCommitBuilder.build(
            principal_ref=self._principal_ref, command_id=command_id, transaction_id=transaction_id,
            idempotency_key=idempotency_key, payload_digest=digest, events=events,
            expected_stream_revisions={fact_type: expected_revision},
            pinned_revisions={fact_type: expected_revision},
            result_digest=digest, read_stream_revisions={fact_type: expected_revision},
        )
        batch["owner_fragments"] = [fragment.model_dump(mode="python")]
        result = self._store.append_batch(batch)
        if not result.committed:
            failure = result.failure
            raise HoldingsError(failure.error_code if failure is not None else "holdings_append_rejected")
        return result

    def split(
        self,
        *,
        fact_type: str,
        source_lot_ref: str,
        result_lot_refs: Sequence[str],
        amounts: Sequence[Decimal],
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        refs = tuple(result_lot_refs)
        quantities = tuple(amounts)
        if not source_lot_ref or not 1 <= len(refs) <= 32 or len(refs) != len(quantities):
            raise HoldingsError("holdings_split_lots_invalid")
        for amount in quantities:
            _finite_decimal(amount, "holdings_split_quantity_invalid")
        payload = {
            "source_lot_ref": source_lot_ref,
            "result_lot_refs": list(refs),
            "amounts": [_decimal_text(amount) for amount in quantities],
        }
        digest_payload = {"kind": "split", "fact_type": fact_type, **payload}
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        source = _projection_lot(projection, source_lot_ref)
        if source.reservations:
            raise HoldingsError("holdings_reserved_lot_cannot_split")
        if len(set(refs)) != len(refs) or source_lot_ref in refs:
            raise HoldingsError("holdings_split_lots_invalid")
        if any(ref in projection.lots for ref in refs):
            raise HoldingsError("holdings_lot_duplicate")
        if any(amount <= 0 for amount in quantities) or sum(quantities, Decimal(0)) != source.quantity:
            raise HoldingsError("holdings_split_quantity_mismatch")
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.holdings.split", payload),),
            expected_revision=expected_revision, digest_payload=digest_payload,
        )

    def merge(
        self,
        *,
        fact_type: str,
        source_lot_refs: Sequence[str],
        result_lot_ref: str,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        refs = tuple(source_lot_refs)
        if not 2 <= len(refs) <= 32 or not result_lot_ref:
            raise HoldingsError("holdings_merge_lots_invalid")
        payload = {"source_lot_refs": list(refs), "result_lot_ref": result_lot_ref}
        digest_payload = {"kind": "merge", "fact_type": fact_type, **payload}
        duplicate = self._duplicate(idempotency_key, digest_payload)
        if duplicate is not None:
            return duplicate
        projection = self._read(fact_type)
        _require_revision(expected_revision, projection.source_revision)
        if len(set(refs)) != len(refs) or result_lot_ref in refs or result_lot_ref in projection.lots:
            raise HoldingsError("holdings_merge_lots_invalid")
        sources = [_projection_lot(projection, ref) for ref in refs]
        if any(source.reservations for source in sources):
            raise HoldingsError("holdings_reserved_lot_cannot_merge")
        if any(source.container_ref != sources[0].container_ref for source in sources):
            raise HoldingsError("holdings_merge_container_mismatch")
        for source in sources[1:]:
            _require_compatible_items(
                {"item_ref": sources[0].item_ref},
                {"item_ref": source.item_ref}, self._item_definitions,
            )
        return self._append(
            fact_type=fact_type, command_id=command_id, idempotency_key=idempotency_key,
            causation_id=causation_id, correlation_id=correlation_id,
            event_specs=(("gameplay.holdings.merged", payload),),
            expected_revision=expected_revision, digest_payload=digest_payload,
        )


def _find_reservation(projection: HoldingsProjection, reservation_ref: str) -> HoldingsReservation:
    for lot in projection.lots.values():
        reservation = lot.reservations.get(reservation_ref)
        if reservation is not None:
            return reservation
    raise HoldingsError("holdings_reservation_unknown")


def _projection_lot(projection: HoldingsProjection, lot_ref: str) -> HoldingsLot:
    try:
        lot = projection.lots[lot_ref]
    except KeyError as exc:
        raise HoldingsError("holdings_lot_unknown") from exc
    if lot.quantity == 0 and not lot.reservations:
        raise HoldingsError("holdings_lot_unavailable")
    return lot


def _active_lot(
    lots: Mapping[str, dict[str, object]],
    closed_lots: set[str],
    lot_ref: str,
) -> dict[str, object]:
    if lot_ref in closed_lots:
        raise HoldingsError("holdings_lot_closed")
    try:
        return lots[lot_ref]
    except KeyError as exc:
        raise HoldingsError("holdings_lot_unknown") from exc


def _require_compatible_items(
    left_lot: Mapping[str, object] | HoldingsLot,
    right_lot: Mapping[str, object] | HoldingsLot,
    item_definitions: Mapping[str, HoldingsItemDefinition],
) -> None:
    left_item_ref = left_lot.item_ref if isinstance(left_lot, HoldingsLot) else left_lot["item_ref"]
    right_item_ref = right_lot.item_ref if isinstance(right_lot, HoldingsLot) else right_lot["item_ref"]
    left = item_definitions[left_item_ref]
    right = item_definitions[right_item_ref]
    if left.unit_ref != right.unit_ref or left.specification_ref != right.specification_ref:
        raise HoldingsError("holdings_item_incompatible")


def _require_revision(expected: int, actual: int) -> None:
    if type(expected) is not int or expected != actual:
        raise HoldingsError("revision_conflict")


def _finite_decimal(value: Decimal, error_code: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise HoldingsError(error_code)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _decimal(payload: Mapping[str, object], key: str) -> Decimal:
    value = payload.get(key)
    if type(value) is not str:
        raise HoldingsError("holdings_event_payload_invalid")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise HoldingsError("holdings_event_payload_invalid") from exc
    if not result.is_finite():
        raise HoldingsError("holdings_event_payload_invalid")
    return result


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise HoldingsError("holdings_event_payload_invalid")
    return value


def _text_list(
    payload: Mapping[str, object],
    key: str,
    *,
    maximum: int,
    minimum: int,
) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise HoldingsError("holdings_event_payload_invalid")
    if any(not isinstance(item, str) or not item for item in value):
        raise HoldingsError("holdings_event_payload_invalid")
    return tuple(value)


def _decimal_list(
    payload: Mapping[str, object],
    key: str,
    *,
    expected_length: int,
) -> tuple[Decimal, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or len(value) != expected_length:
        raise HoldingsError("holdings_event_payload_invalid")
    results: list[Decimal] = []
    for item in value:
        if not isinstance(item, str):
            raise HoldingsError("holdings_event_payload_invalid")
        try:
            amount = Decimal(item)
        except InvalidOperation as exc:
            raise HoldingsError("holdings_event_payload_invalid") from exc
        if not amount.is_finite():
            raise HoldingsError("holdings_event_payload_invalid")
        results.append(amount)
    return tuple(results)


def _canonical_json(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
