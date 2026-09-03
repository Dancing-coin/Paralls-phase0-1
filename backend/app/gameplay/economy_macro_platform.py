from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import (
    AppendBatchResult,
    GameplayEvent,
    GameplayFailure,
    OwnerAuthorizedFragment,
    StrictGameplayModel,
)
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch


class EconomyMacroPlatformError(ValueError):
    pass


class EconomyMacroContentModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RegionalMacroPolicy(EconomyMacroContentModel):
    policy_ref: str = Field(pattern=r"^policy:")
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    currency_ref: str = Field(pattern=r"^currency:")
    base_currency_ref: str = Field(pattern=r"^currency:")
    quote_currency_ref: str = Field(pattern=r"^currency:")
    price_index_basket_refs: tuple[str, ...] = Field(min_length=1)
    interest_rate_bps: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_fx_pair(self) -> "RegionalMacroPolicy":
        if self.base_currency_ref == self.quote_currency_ref:
            raise ValueError("economy_macro_fx_pair_invalid")
        return self


class PopulationAggregateSignal(EconomyMacroContentModel):
    signal_ref: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    source_stream_id: str = Field(min_length=1)
    source_stream_revision: int = Field(ge=1)
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    signal_kind: Literal["demand", "supply", "price_index"]
    quantity: int = Field(ge=0)
    unit_price_minor: int | None = Field(default=None, ge=0)
    baseline_unit_price_minor: int | None = Field(default=None, ge=0)
    public_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_price_index_fields(self) -> "PopulationAggregateSignal":
        is_price_index = self.signal_kind == "price_index"
        if is_price_index != (self.unit_price_minor is not None and self.baseline_unit_price_minor is not None):
            raise ValueError("economy_macro_price_index_fields_invalid")
        if self.baseline_unit_price_minor == 0:
            raise ValueError("economy_macro_price_index_baseline_invalid")
        return self


class RegionalMacroClose(EconomyMacroContentModel):
    close_ref: str = Field(min_length=1)
    policy_ref: str = Field(pattern=r"^policy:")
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    currency_ref: str = Field(pattern=r"^currency:")
    base_currency_ref: str = Field(pattern=r"^currency:")
    quote_currency_ref: str = Field(pattern=r"^currency:")
    signal_event_ids: tuple[str, ...] = Field(min_length=1)
    signal_refs: tuple[str, ...] = Field(min_length=1)
    cpi_basis_points: int = Field(ge=0)
    demand_quantity: int = Field(ge=0)
    supply_quantity: int = Field(ge=0)
    interest_rate_bps: int = Field(ge=0)
    money_supply_minor: int = Field(ge=0)
    fx_numerator: int = Field(gt=0)
    fx_denominator: int = Field(gt=0)
    summary_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class RegionalMacroCloseRecord:
    close_ref: str
    value: RegionalMacroClose
    source_event_id: str
    signal_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class EconomyMacroProjection:
    population_signals: Mapping[str, PopulationAggregateSignal]
    closes: Mapping[str, RegionalMacroCloseRecord]
    source_revision_vector: Mapping[str, int]


def _sha(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _failure(command_id: str, error_code: str, failed_stage: str, *, stream_id: str | None = None) -> AppendBatchResult:
    return AppendBatchResult(
        committed=False,
        transaction_id=f"transaction:{command_id}",
        command_id=command_id,
        idempotency_status="rejected",
        failure=GameplayFailure(
            error_code=error_code,
            message=error_code,
            failed_stage=failed_stage,
            stream_id=stream_id,
        ),
    )


class EconomyMacroProjector:
    def rebuild(
        self,
        events: Sequence[GameplayEvent],
        *,
        checkpoint: EconomyMacroProjection | None = None,
    ) -> EconomyMacroProjection:
        signals = dict(checkpoint.population_signals) if checkpoint else {}
        closes = dict(checkpoint.closes) if checkpoint else {}
        revisions = dict(checkpoint.source_revision_vector) if checkpoint else {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            payload = event.payload
            if event.event_type == "gameplay.economy.population_aggregate_signal_recorded@1":
                signal = PopulationAggregateSignal.model_validate(payload)
                if signal.signal_ref in signals:
                    raise EconomyMacroPlatformError("economy_macro_signal_duplicate")
                signals[signal.signal_ref] = signal
                revisions[event.stream_id] = event.stream_revision
                continue
            if event.event_type == "gameplay.economy.regional_macro_period_closed@1":
                close = RegionalMacroClose.model_validate(payload)
                if close.close_ref in closes:
                    raise EconomyMacroPlatformError("economy_macro_close_duplicate")
                closes[close.close_ref] = RegionalMacroCloseRecord(
                    close_ref=close.close_ref,
                    value=close,
                    source_event_id=event.event_id,
                    signal_event_ids=close.signal_event_ids,
                )
                revisions[event.stream_id] = event.stream_revision
                continue
        return EconomyMacroProjection(
            population_signals=MappingProxyType(dict(sorted(signals.items()))),
            closes=MappingProxyType(dict(sorted(closes.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
        )


class EconomyMacroPlatformAuthority:
    _PRINCIPAL = "actor_gameplay.economy_domain"
    _SOURCE_PRINCIPAL = "actor_gameplay.population_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store
        self._projector = EconomyMacroProjector()

    def append_population_aggregate_signal(
        self,
        *,
        source_event_id: str,
        expected_source_revision: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if expected_source_revision <= 0:
            raise EconomyMacroPlatformError("economy_macro_source_revision_invalid")
        source = self._load_population_source(
            source_event_id=source_event_id,
            expected_source_revision=expected_source_revision,
            command_id=command_id,
        )
        if isinstance(source, AppendBatchResult):
            return source

        payload = self._signal_payload_from_source(source)
        projection = self.projection()
        signal_ref = payload["signal_ref"]
        if signal_ref in projection.population_signals:
            return _failure(command_id, "economy_macro_signal_duplicate", "admission")
        stream_id = self._stream_id(payload["region_ref"])
        expected_revision = self._store.get_stream_head(stream_id)
        batch = self._batch(
            command_id=command_id,
            idempotency_key=idempotency_key,
            stream_id=stream_id,
            expected_revision=expected_revision,
            event_type="gameplay.economy.population_aggregate_signal_recorded@1",
            payload=payload,
            visibility_policy="public",
            causation_id=causation_id,
            correlation_id=correlation_id,
            digest_payload={
                "type": "population_aggregate_signal",
                "source_event_id": source_event_id,
                "expected_source_revision": expected_source_revision,
                "signal": payload,
            },
        )
        return self._store.append_batch(batch)

    def close_regional_macro_period(
        self,
        *,
        policy: RegionalMacroPolicy,
        close_ref: str,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        stream_id = self._stream_id(policy.region_ref)
        projection = self.projection()
        signal_events = [
            event
            for event in self._relevant_events()
            if event.event_type == "gameplay.economy.population_aggregate_signal_recorded@1"
            and event.payload.get("region_ref") == policy.region_ref
            and event.payload.get("period_ref") == policy.period_ref
        ]
        relevant_signals = [PopulationAggregateSignal.model_validate(event.payload) for event in signal_events]
        if not signal_events:
            return _failure(command_id, "economy_macro_signals_missing", "admission")
        close = self._build_close(
            close_ref=close_ref,
            policy=policy,
            relevant_signals=relevant_signals,
            signal_event_ids=tuple(
                event.event_id
                for event in sorted(signal_events, key=lambda item: (item.global_sequence, item.event_id))
            ),
        )
        duplicate = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if duplicate is not None:
            digest = _sha(
                {
                    "type": "regional_macro_close",
                    "close_ref": close_ref,
                    "policy": policy.model_dump(mode="json"),
                    "close": close.model_dump(mode="json"),
                }
            )
            record = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
            if record is not None and record.payload_digest == digest:
                return duplicate.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return _failure(command_id, "idempotency_key_reused", "idempotency")
        if close_ref in projection.closes:
            return _failure(command_id, "economy_macro_close_duplicate", "admission")
        batch = self._batch(
            command_id=command_id,
            idempotency_key=idempotency_key,
            stream_id=stream_id,
            expected_revision=expected_revision,
            event_type="gameplay.economy.regional_macro_period_closed@1",
            payload=close.model_dump(mode="json"),
            visibility_policy="authority_only",
            causation_id=causation_id,
            correlation_id=correlation_id,
            digest_payload={
                "type": "regional_macro_close",
                "close_ref": close_ref,
                "policy": policy.model_dump(mode="json"),
                "close": close.model_dump(mode="json"),
            },
        )
        return self._store.append_batch(batch)

    def projection(self, *, checkpoint_at: int | None = None) -> EconomyMacroProjection:
        events = self._relevant_events()
        if checkpoint_at is not None and (isinstance(checkpoint_at, bool) or checkpoint_at < 0):
            raise EconomyMacroPlatformError("economy_macro_checkpoint_invalid")
        if checkpoint_at is None:
            return self._projector.rebuild(events)
        prefix = [event for event in events if event.global_sequence <= checkpoint_at]
        tail = [event for event in events if event.global_sequence > checkpoint_at]
        checkpoint = self._projector.rebuild(prefix)
        return self._projector.rebuild(tail, checkpoint=checkpoint)

    def replay(self, *, checkpoint_at: int | None = None):
        events = self._relevant_events()
        replay = GameplayProjectionReplay(projector_id="economy-macro-platform", projector_version="1")
        if checkpoint_at is None:
            return replay.full_replay(events)
        checkpoint = replay.create_checkpoint([event for event in events if event.global_sequence <= checkpoint_at])
        return replay.checkpoint_plus_tail_replay(checkpoint, [event for event in events if event.global_sequence > checkpoint_at])

    def _relevant_events(self) -> list[GameplayEvent]:
        return [
            event
            for event in self._store.read_events()
            if event.event_type
            in {
                "gameplay.economy.population_aggregate_signal_recorded@1",
                "gameplay.economy.regional_macro_period_closed@1",
            }
        ]

    def _load_population_source(
        self,
        *,
        source_event_id: str,
        expected_source_revision: int,
        command_id: str,
    ) -> GameplayEvent | AppendBatchResult:
        try:
            source = self._store.get_event(source_event_id)
        except KeyError:
            return _failure(command_id, "economy_population_signal_source_missing", "source_lookup")
        if source.event_type != "gameplay.population.aggregate_published@1":
            return _failure(command_id, "economy_population_signal_source_invalid", "source_lookup")
        if source.visibility_policy != "public":
            return _failure(command_id, "economy_population_signal_private_source", "source_lookup")
        if self._store.get_stream_head(source.stream_id) != expected_source_revision:
            return _failure(command_id, "economy_population_signal_stale_source", "source_lookup", stream_id=source.stream_id)
        if source.stream_revision != expected_source_revision:
            return _failure(command_id, "economy_population_signal_revision_mismatch", "source_lookup", stream_id=source.stream_id)
        return source

    def _signal_payload_from_source(self, source: GameplayEvent) -> dict[str, object]:
        payload = dict(source.payload)
        quantity = payload.get("quantity")
        signal_kind = payload.get("signal_kind")
        region_ref = payload.get("region_ref")
        period_ref = payload.get("period_ref")
        item_ref = payload.get("item_ref")
        aggregate_ref = payload.get("aggregate_ref")
        if (
            not isinstance(quantity, int)
            or isinstance(quantity, bool)
            or quantity < 0
            or signal_kind not in {"demand", "supply", "price_index"}
            or not isinstance(region_ref, str)
            or not region_ref
            or not isinstance(period_ref, str)
            or not period_ref
            or not isinstance(item_ref, str)
            or not item_ref
            or not isinstance(aggregate_ref, str)
            or not aggregate_ref
        ):
            raise EconomyMacroPlatformError("economy_population_signal_source_invalid")
        signal_payload: dict[str, object] = {
            "signal_ref": f"signal:{aggregate_ref}",
            "source_event_id": source.event_id,
            "source_stream_id": source.stream_id,
            "source_stream_revision": source.stream_revision,
            "region_ref": region_ref,
            "period_ref": period_ref,
            "item_ref": item_ref,
            "signal_kind": signal_kind,
            "quantity": quantity,
        }
        if signal_kind == "price_index":
            unit_price_minor = payload.get("unit_price_minor")
            baseline_unit_price_minor = payload.get("baseline_unit_price_minor")
            if (
                not isinstance(unit_price_minor, int)
                or isinstance(unit_price_minor, bool)
                or unit_price_minor < 0
                or not isinstance(baseline_unit_price_minor, int)
                or isinstance(baseline_unit_price_minor, bool)
                or baseline_unit_price_minor <= 0
            ):
                raise EconomyMacroPlatformError("economy_population_signal_source_invalid")
            signal_payload["unit_price_minor"] = unit_price_minor
            signal_payload["baseline_unit_price_minor"] = baseline_unit_price_minor
        signal_payload["public_digest"] = _sha(signal_payload)
        PopulationAggregateSignal.model_validate(signal_payload)
        return signal_payload

    def _build_close(
        self,
        *,
        close_ref: str,
        policy: RegionalMacroPolicy,
        relevant_signals: Sequence[PopulationAggregateSignal],
        signal_event_ids: tuple[str, ...],
    ) -> RegionalMacroClose:
        basket = set(policy.price_index_basket_refs)
        price_signals = [
            signal
            for signal in relevant_signals
            if signal.signal_kind == "price_index" and signal.item_ref in basket
        ]
        if not price_signals:
            raise EconomyMacroPlatformError("economy_macro_price_index_missing")
        numerator = sum((signal.unit_price_minor or 0) * signal.quantity for signal in price_signals)
        denominator = sum((signal.baseline_unit_price_minor or 0) * signal.quantity for signal in price_signals)
        if denominator <= 0:
            raise EconomyMacroPlatformError("economy_macro_price_index_missing")
        demand_quantity = sum(signal.quantity for signal in relevant_signals if signal.signal_kind == "demand")
        supply_quantity = sum(signal.quantity for signal in relevant_signals if signal.signal_kind == "supply")
        money_supply_minor = self._money_supply(policy.currency_ref)
        fx_numerator, fx_denominator = self._latest_fx_fixing(
            base_currency_ref=policy.base_currency_ref,
            quote_currency_ref=policy.quote_currency_ref,
        )
        signal_refs = tuple(sorted(signal.signal_ref for signal in relevant_signals))
        close_payload = {
            "close_ref": close_ref,
            "policy_ref": policy.policy_ref,
            "region_ref": policy.region_ref,
            "period_ref": policy.period_ref,
            "currency_ref": policy.currency_ref,
            "base_currency_ref": policy.base_currency_ref,
            "quote_currency_ref": policy.quote_currency_ref,
            "signal_event_ids": signal_event_ids,
            "signal_refs": signal_refs,
            "cpi_basis_points": (numerator * 10000) // denominator,
            "demand_quantity": demand_quantity,
            "supply_quantity": supply_quantity,
            "interest_rate_bps": policy.interest_rate_bps,
            "money_supply_minor": money_supply_minor,
            "fx_numerator": fx_numerator,
            "fx_denominator": fx_denominator,
        }
        close_payload["summary_digest"] = _sha(close_payload)
        return RegionalMacroClose.model_validate(close_payload)

    def _money_supply(self, currency_ref: str) -> int:
        total = 0
        for event in self._store.read_events():
            if event.event_type != "gameplay.economy.currency_issuance_recorded@1":
                continue
            if event.payload.get("currency_ref") != currency_ref:
                continue
            amount = event.payload.get("amount_minor")
            if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                raise EconomyMacroPlatformError("economy_macro_money_supply_invalid")
            total += amount
        return total

    def _latest_fx_fixing(self, *, base_currency_ref: str, quote_currency_ref: str) -> tuple[int, int]:
        fixings = [
            event
            for event in self._store.read_events()
            if event.event_type == "gameplay.economy.fx_fixing_recorded@1"
            and event.payload.get("base_currency_ref") == base_currency_ref
            and event.payload.get("quote_currency_ref") == quote_currency_ref
        ]
        if not fixings:
            raise EconomyMacroPlatformError("economy_macro_fx_fixing_missing")
        latest = max(fixings, key=lambda event: (event.global_sequence, event.event_id))
        numerator = latest.payload.get("numerator")
        denominator = latest.payload.get("denominator")
        if (
            not isinstance(numerator, int)
            or isinstance(numerator, bool)
            or numerator <= 0
            or not isinstance(denominator, int)
            or isinstance(denominator, bool)
            or denominator <= 0
        ):
            raise EconomyMacroPlatformError("economy_macro_fx_fixing_invalid")
        return numerator, denominator

    def _batch(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        stream_id: str,
        expected_revision: int,
        event_type: str,
        payload: Mapping[str, object],
        visibility_policy: str,
        causation_id: str,
        correlation_id: str,
        digest_payload: Mapping[str, object],
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
            read_stream_revisions={stream_id: expected_revision},
            pinned_revisions={stream_id: expected_revision},
        )
        batch = batch.model_copy(
            update={
                "events": [
                    event.model_copy(update={"visibility_policy": visibility_policy}, deep=True)
                    for event in batch.events
                ],
                "owner_fragments": [
                    OwnerAuthorizedFragment(
                        fragment_id=f"fragment:economy-macro:{command_id}",
                        owner_principal_ref=self._PRINCIPAL,
                        source_rule_ref="economy-macro:explicit-owner-operation@1",
                        expected_revisions={stream_id: expected_revision},
                        read_set_revisions={stream_id: expected_revision},
                        pinned_revisions={stream_id: expected_revision},
                        event_specs={stream_id: ((event_type, dict(payload)),)},
                        event_visibility_policies={stream_id: (visibility_policy,)},
                    )
                ],
                "idempotency_record": batch.idempotency_record.model_copy(
                    update={"payload_digest": _sha(dict(digest_payload))},
                    deep=True,
                ),
                "result_digest": _sha(dict(digest_payload)),
            },
            deep=True,
        )
        return batch

    @staticmethod
    def _stream_id(region_ref: object) -> str:
        if not isinstance(region_ref, str) or not region_ref:
            raise EconomyMacroPlatformError("economy_macro_region_invalid")
        return f"gameplay:economy:macro:{region_ref}"


__all__ = [
    "EconomyMacroPlatformAuthority",
    "EconomyMacroPlatformError",
    "EconomyMacroProjection",
    "EconomyMacroProjector",
    "PopulationAggregateSignal",
    "RegionalMacroClose",
    "RegionalMacroPolicy",
]
