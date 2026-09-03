"""Owner-local quote, order, and deterministic clearing platform slice."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, OwnerAuthorizedFragment, ProjectionCheckpoint, StrictGameplayModel
from app.gameplay.settlement_plan import build_atomic_event_batch


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


class EconomyMarketPlatformError(ValueError):
    pass


class Quote(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    quote_ref: str = Field(min_length=1)
    issuer_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    side: Literal["buy", "sell"]
    unit_price_minor: int = Field(gt=0, strict=True)
    currency_ref: str = Field(pattern=r"^currency:")
    quantity_limit: int = Field(gt=0, strict=True)
    valid_from_tick: int = Field(ge=0, strict=True)
    valid_until_tick: int = Field(ge=0, strict=True)
    policy_revision: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    version: int = Field(ge=1, strict=True)
    status: Literal["active", "cancelled"] = "active"

    @model_validator(mode="after")
    def validate_window(self) -> "Quote":
        if self.valid_until_tick < self.valid_from_tick:
            raise ValueError("economy_market_quote_window_invalid")
        return self


class Order(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order_ref: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    quote_ref: str = Field(min_length=1)
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0, strict=True)
    limit_price_minor: int = Field(gt=0, strict=True)
    currency_ref: str = Field(pattern=r"^currency:")
    region_ref: str = Field(min_length=1)
    created_tick: int = Field(ge=0, strict=True)
    valid_from_tick: int = Field(ge=0, strict=True)
    valid_until_tick: int = Field(ge=0, strict=True)
    policy_revision: str = Field(min_length=1)
    status: Literal["active", "cancelled"] = "active"

    @model_validator(mode="after")
    def validate_window(self) -> "Order":
        if self.valid_until_tick < self.valid_from_tick:
            raise ValueError("economy_market_order_window_invalid")
        return self


class ClearingPolicy(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_ref: str = Field(pattern=r"^policy:")
    ordering_key: Literal["created_tick_order_ref"]
    partial_fill: bool
    max_matches: int = Field(gt=0, strict=True)


class MarketMatch(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    quote_ref: str = Field(min_length=1)
    order_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0, strict=True)
    unit_price_minor: int = Field(gt=0, strict=True)


class MarketClearing(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    clearing_ref: str = Field(min_length=1)
    policy_ref: str = Field(pattern=r"^policy:")
    region_ref: str = Field(min_length=1)
    tick: int = Field(ge=0, strict=True)
    quote_refs: tuple[str, ...] = Field(min_length=1)
    matches: tuple[MarketMatch, ...] = ()
    revision_vector: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_revision_vector(self) -> "MarketClearing":
        if any(not stream_id or isinstance(revision, bool) or revision < 0 for stream_id, revision in self.revision_vector.items()):
            raise ValueError("economy_market_revision_vector_invalid")
        return self


class MarketWriteResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    committed: bool
    zero_write: bool
    error_code: str | None = None
    append_result: AppendBatchResult | None = None
    clearing: MarketClearing | None = None
    revision_vector: dict[str, int] = Field(default_factory=dict)


@dataclass(frozen=True)
class EconomyMarketProjection:
    quotes: Mapping[str, Quote]
    orders: Mapping[str, Order]
    clearings: Mapping[str, MarketClearing]
    source_revision_vector: Mapping[str, int]
    last_global_sequence: int = 0
    applied_event_ids: tuple[str, ...] = ()

    def to_state(self) -> dict[str, object]:
        return {
            "quotes": {key: value.model_dump(mode="json") for key, value in self.quotes.items()},
            "orders": {key: value.model_dump(mode="json") for key, value in self.orders.items()},
            "clearings": {key: value.model_dump(mode="json") for key, value in self.clearings.items()},
            "source_revision_vector": dict(self.source_revision_vector),
            "last_global_sequence": self.last_global_sequence,
            "applied_event_ids": list(self.applied_event_ids),
        }


class EconomyMarketProjector:
    projector_id = "economy-market-platform"
    projector_version = "1"
    projection_schema_version = 1

    def rebuild(
        self,
        events: Sequence[object],
        *,
        checkpoint: ProjectionCheckpoint | EconomyMarketProjection | None = None,
    ) -> EconomyMarketProjection:
        projection = self._checkpoint_projection(checkpoint)
        quotes = dict(projection.quotes)
        orders = dict(projection.orders)
        clearings = dict(projection.clearings)
        revisions = dict(projection.source_revision_vector)
        applied_event_ids = list(projection.applied_event_ids)
        last_global_sequence = projection.last_global_sequence

        for event in sorted((event for event in events if getattr(event, "event_id", None)), key=lambda item: (item.global_sequence, item.event_id)):
            if event.event_id in applied_event_ids:
                continue
            if not event.stream_id.startswith("gameplay:economy:market:"):
                continue
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
            last_global_sequence = max(last_global_sequence, event.global_sequence)
            payload = dict(event.payload)
            if event.event_type == "gameplay.economy.market_quote_recorded@1":
                quote = Quote.model_validate(payload["quote"])
                prior = quotes.get(quote.quote_ref)
                if prior is not None and quote.version <= prior.version:
                    raise EconomyMarketPlatformError("economy_market_quote_replay_invalid")
                quotes[quote.quote_ref] = quote
            elif event.event_type == "gameplay.economy.market_order_recorded@1":
                order = Order.model_validate(payload["order"])
                orders[order.order_ref] = order
            elif event.event_type == "gameplay.economy.market_clearing_recorded@1":
                clearing = MarketClearing.model_validate(payload["clearing"])
                clearings[clearing.clearing_ref] = clearing
            applied_event_ids.append(event.event_id)

        return EconomyMarketProjection(
            quotes=MappingProxyType(dict(sorted(quotes.items()))),
            orders=MappingProxyType(dict(sorted(orders.items()))),
            clearings=MappingProxyType(dict(sorted(clearings.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
            last_global_sequence=last_global_sequence,
            applied_event_ids=tuple(applied_event_ids),
        )

    def create_checkpoint(self, events: Sequence[object]) -> ProjectionCheckpoint:
        projection = self.rebuild(events)
        state = projection.to_state()
        return ProjectionCheckpoint(
            checkpoint_id=f"checkpoint:{self.projector_id}:{projection.last_global_sequence}",
            projector_id=self.projector_id,
            projector_version=self.projector_version,
            projection_schema_version=self.projection_schema_version,
            source_revision_vector=dict(projection.source_revision_vector),
            last_global_sequence=projection.last_global_sequence,
            state=state,
            applied_event_ids=list(projection.applied_event_ids),
            projection_hash=_digest(
                {
                    "state": state,
                    "source_revision_vector": dict(projection.source_revision_vector),
                    "last_global_sequence": projection.last_global_sequence,
                    "applied_event_ids": list(projection.applied_event_ids),
                }
            ),
        )

    @staticmethod
    def _checkpoint_projection(checkpoint: ProjectionCheckpoint | EconomyMarketProjection | None) -> EconomyMarketProjection:
        if checkpoint is None:
            return EconomyMarketProjection(
                quotes=MappingProxyType({}),
                orders=MappingProxyType({}),
                clearings=MappingProxyType({}),
                source_revision_vector=MappingProxyType({}),
            )
        if isinstance(checkpoint, EconomyMarketProjection):
            return checkpoint
        state = checkpoint.state
        quotes = {
            key: Quote.model_validate(value)
            for key, value in dict(state.get("quotes", {})).items()
        }
        orders = {
            key: Order.model_validate(value)
            for key, value in dict(state.get("orders", {})).items()
        }
        clearings = {
            key: MarketClearing.model_validate(value)
            for key, value in dict(state.get("clearings", {})).items()
        }
        revisions = {
            str(key): int(value)
            for key, value in dict(state.get("source_revision_vector", {})).items()
        }
        return EconomyMarketProjection(
            quotes=MappingProxyType(dict(sorted(quotes.items()))),
            orders=MappingProxyType(dict(sorted(orders.items()))),
            clearings=MappingProxyType(dict(sorted(clearings.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
            last_global_sequence=checkpoint.last_global_sequence,
            applied_event_ids=tuple(checkpoint.applied_event_ids),
        )


class EconomyMarketAuthority:
    _PRINCIPAL = "actor_gameplay.economy_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store
        self._projector = EconomyMarketProjector()

    def record_quote(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        quote: Quote,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> MarketWriteResult:
        stream_id = self._quote_stream(quote.quote_ref)
        batch = self._build_batch(
            command_id=command_id,
            idempotency_key=idempotency_key,
            stream_id=stream_id,
            expected_revision=expected_revision,
            event_type="gameplay.economy.market_quote_recorded@1",
            payload={"quote": quote.model_dump(mode="json")},
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        return self._from_append(self._store.append_batch(batch))

    def record_order(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        order: Order,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> MarketWriteResult:
        stream_id = self._order_stream(order.order_ref)
        batch = self._build_batch(
            command_id=command_id,
            idempotency_key=idempotency_key,
            stream_id=stream_id,
            expected_revision=expected_revision,
            event_type="gameplay.economy.market_order_recorded@1",
            payload={"order": order.model_dump(mode="json")},
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        return self._from_append(self._store.append_batch(batch))

    def record_clearing(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        clearing_ref: str,
        quote_refs: tuple[str, ...],
        policy: ClearingPolicy,
        tick: int,
        region_ref: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        required_revision_vector: Mapping[str, int] | None = None,
    ) -> MarketWriteResult:
        projection = self._projector.rebuild(self._store.read_events())
        normalized_quote_refs = tuple(sorted(set(quote_refs)))
        if not normalized_quote_refs:
            return self._rejected("quote_refs_required")

        try:
            clearing, revision_vector = self._build_clearing(
                projection=projection,
                clearing_ref=clearing_ref,
                quote_refs=normalized_quote_refs,
                policy=policy,
                tick=tick,
                region_ref=region_ref,
            )
        except EconomyMarketPlatformError as exc:
            return self._rejected(str(exc))

        if required_revision_vector is not None:
            normalized_required = {str(key): int(value) for key, value in required_revision_vector.items()}
            if normalized_required != revision_vector:
                return self._rejected("revision_vector_mismatch")

        stream_id = self._clearing_stream(clearing_ref)
        batch = self._build_batch(
            command_id=command_id,
            idempotency_key=idempotency_key,
            stream_id=stream_id,
            expected_revision=expected_revision,
            event_type="gameplay.economy.market_clearing_recorded@1",
            payload={"clearing": clearing.model_dump(mode="json")},
            causation_id=causation_id,
            correlation_id=correlation_id,
            read_stream_revisions=revision_vector,
            pinned_revisions=revision_vector,
        )
        return self._from_append(self._store.append_batch(batch), clearing=clearing)

    def _build_clearing(
        self,
        *,
        projection: EconomyMarketProjection,
        clearing_ref: str,
        quote_refs: tuple[str, ...],
        policy: ClearingPolicy,
        tick: int,
        region_ref: str,
    ) -> tuple[MarketClearing, dict[str, int]]:
        matches: list[MarketMatch] = []
        revision_vector: dict[str, int] = {}
        active_quotes = []
        for quote_ref in quote_refs:
            quote = projection.quotes.get(quote_ref)
            if quote is None:
                raise EconomyMarketPlatformError("quote_missing")
            if quote.region_ref != region_ref:
                raise EconomyMarketPlatformError("quote_region_mismatch")
            if not self._is_active(quote, tick):
                continue
            active_quotes.append(quote)
            quote_stream = self._quote_stream(quote.quote_ref)
            if quote_stream not in projection.source_revision_vector:
                raise EconomyMarketPlatformError("quote_revision_missing")
            revision_vector[quote_stream] = projection.source_revision_vector[quote_stream]

        orders_by_quote: dict[str, list[Order]] = {quote.quote_ref: [] for quote in active_quotes}
        for order in projection.orders.values():
            if order.quote_ref not in orders_by_quote:
                continue
            if order.region_ref != region_ref or not self._is_active(order, tick):
                continue
            quote = projection.quotes[order.quote_ref]
            if not self._compatible(quote, order):
                continue
            orders_by_quote[order.quote_ref].append(order)
            order_stream = self._order_stream(order.order_ref)
            if order_stream not in projection.source_revision_vector:
                raise EconomyMarketPlatformError("order_revision_missing")
            revision_vector[order_stream] = projection.source_revision_vector[order_stream]

        for quote in sorted(active_quotes, key=lambda item: (item.unit_price_minor, item.quote_ref)):
            remaining = quote.quantity_limit
            orders = sorted(orders_by_quote[quote.quote_ref], key=lambda item: (item.created_tick, item.order_ref))
            for order in orders:
                if len(matches) >= policy.max_matches or remaining == 0:
                    break
                quantity = order.quantity if not policy.partial_fill else min(order.quantity, remaining)
                if not policy.partial_fill and order.quantity > remaining:
                    continue
                if quantity <= 0:
                    continue
                matches.append(
                    MarketMatch(
                        quote_ref=quote.quote_ref,
                        order_ref=order.order_ref,
                        quantity=quantity,
                        unit_price_minor=quote.unit_price_minor,
                    )
                )
                remaining -= quantity
            if len(matches) >= policy.max_matches:
                break

        if not matches:
            raise EconomyMarketPlatformError("clearing_empty")

        clearing = MarketClearing(
            clearing_ref=clearing_ref,
            policy_ref=policy.policy_ref,
            region_ref=region_ref,
            tick=tick,
            quote_refs=quote_refs,
            matches=tuple(matches),
            revision_vector=dict(sorted(revision_vector.items())),
        )
        return clearing, dict(sorted(revision_vector.items()))

    def _build_batch(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        stream_id: str,
        expected_revision: int,
        event_type: str,
        payload: Mapping[str, object],
        causation_id: str,
        correlation_id: str,
        read_stream_revisions: Mapping[str, int] | None = None,
        pinned_revisions: Mapping[str, int] | None = None,
    ):
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=expected_revision,
            event_specs=((event_type, dict(payload)),),
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            read_stream_revisions=read_stream_revisions,
            pinned_revisions=pinned_revisions,
        )
        return batch.model_copy(
            update={
                "owner_fragments": [
                    OwnerAuthorizedFragment(
                        fragment_id=f"fragment:economy-market:{command_id}",
                        owner_principal_ref=self._PRINCIPAL,
                        source_rule_ref="economy-market:owner-local@1",
                        expected_revisions={stream_id: expected_revision},
                        read_set_revisions=dict(read_stream_revisions or {}),
                        pinned_revisions=dict(pinned_revisions or {}),
                        event_specs={stream_id: ((event_type, dict(payload)),)},
                        event_visibility_policies={stream_id: ("project",)},
                    )
                ]
            },
            deep=True,
        )

    @staticmethod
    def _from_append(append_result: AppendBatchResult, *, clearing: MarketClearing | None = None) -> MarketWriteResult:
        zero_write = not append_result.committed or append_result.idempotency_status != "new_commit"
        return MarketWriteResult(
            committed=append_result.committed,
            zero_write=zero_write,
            error_code=append_result.failure.error_code if append_result.failure is not None else None,
            append_result=append_result,
            clearing=clearing,
            revision_vector=dict(append_result.resulting_stream_revisions),
        )

    @staticmethod
    def _rejected(error_code: str) -> MarketWriteResult:
        return MarketWriteResult(
            committed=False,
            zero_write=True,
            error_code=error_code,
        )

    @staticmethod
    def _is_active(value: Quote | Order, tick: int) -> bool:
        return value.status == "active" and value.valid_from_tick <= tick <= value.valid_until_tick

    @staticmethod
    def _compatible(quote: Quote, order: Order) -> bool:
        if quote.quote_ref != order.quote_ref:
            return False
        if quote.currency_ref != order.currency_ref or quote.region_ref != order.region_ref:
            return False
        if quote.policy_revision != order.policy_revision:
            return False
        if quote.side == "sell" and order.side == "buy":
            return order.limit_price_minor >= quote.unit_price_minor
        if quote.side == "buy" and order.side == "sell":
            return order.limit_price_minor <= quote.unit_price_minor
        return False

    @staticmethod
    def _quote_stream(quote_ref: str) -> str:
        return f"gameplay:economy:market:quote:{quote_ref}"

    @staticmethod
    def _order_stream(order_ref: str) -> str:
        return f"gameplay:economy:market:order:{order_ref}"

    @staticmethod
    def _clearing_stream(clearing_ref: str) -> str:
        return f"gameplay:economy:market:clearing:{clearing_ref}"


__all__ = [
    "ClearingPolicy",
    "EconomyMarketAuthority",
    "EconomyMarketPlatformError",
    "EconomyMarketProjection",
    "EconomyMarketProjector",
    "MarketClearing",
    "MarketMatch",
    "MarketWriteResult",
    "Order",
    "Quote",
]
