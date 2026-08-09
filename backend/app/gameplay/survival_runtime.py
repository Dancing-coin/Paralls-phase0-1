"""Explicit Survival profile proposals; no inventory, account, or body ownership."""

from __future__ import annotations

from enum import StrEnum
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, StrictGameplayModel
from app.gameplay.settlement_plan import build_atomic_event_batch


class SurvivalMode(StrEnum):
    DISABLED = "disabled"
    NARRATIVE = "narrative"
    LIGHTWEIGHT = "lightweight"
    SIMULATION = "simulation"


class NeedDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    need_ref: str = Field(min_length=1)
    category: str = Field(min_length=1)
    decay_per_tick: float = Field(ge=0, le=1)


class NeedState(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    need_ref: str = Field(min_length=1)
    value: float = Field(ge=0, le=1)
    last_tick: int = Field(ge=0)


class ConsumptionPlan(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    need_ref: str = Field(min_length=1)
    item_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    required_owner_refs: tuple[str, ...] = ()
    pinned_revisions: dict[str, int] = Field(default_factory=dict)


class SurvivalPolicy(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    policy_ref: str = Field(min_length=1)
    mode: SurvivalMode
    revision: str = Field(min_length=1)


@dataclass(frozen=True)
class SurvivalProjection:
    needs: Mapping[tuple[str, str], NeedState]
    latest_plan: ConsumptionPlan | None
    source_revision_vector: Mapping[str, int]


class SurvivalProjector:
    _TICK = "gameplay.survival.need_tick"
    _CONSUMPTION = "gameplay.survival.consumption_accepted"

    def rebuild(self, events: Sequence[GameplayEvent]) -> SurvivalProjection:
        needs: dict[tuple[str, str], NeedState] = {}
        latest_plan: ConsumptionPlan | None = None
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type not in {self._TICK, self._CONSUMPTION}:
                continue
            payload = event.payload
            actor_ref = str(payload.get("actor_ref", ""))
            need_ref = str(payload.get("need_ref", ""))
            if not actor_ref or not need_ref:
                raise ValueError("survival_event_payload_invalid")
            if event.event_type == self._TICK:
                state = NeedState(
                    need_ref=need_ref,
                    value=float(payload["value"]),
                    last_tick=int(payload["last_tick"]),
                )
                needs[(actor_ref, need_ref)] = state
                plan_payload = payload.get("consumption_plan")
                if plan_payload is not None:
                    if not isinstance(plan_payload, dict):
                        raise ValueError("survival_event_payload_invalid")
                    latest_plan = ConsumptionPlan.model_validate(plan_payload)
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return SurvivalProjection(
            needs=MappingProxyType(dict(sorted(needs.items()))),
            latest_plan=latest_plan,
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
        )


class SurvivalAuthority:
    _PRINCIPAL = "actor_gameplay.survival_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store
        self._projector = SurvivalProjector()

    def projector(self) -> SurvivalProjection:
        return self._projector.rebuild(self._store.read_events())

    def settle_tick(
        self,
        *,
        actor_ref: str,
        policy: SurvivalPolicy,
        definition: NeedDefinition,
        state: NeedState,
        tick: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if policy.mode in {SurvivalMode.DISABLED, SurvivalMode.NARRATIVE}:
            raise ValueError("survival_mode_no_authority_tick")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        next_state, plan = self.tick(policy=policy, definition=definition, state=state, tick=tick)
        stream_id = f"gameplay:survival:{actor_ref}"
        plan_payload = None
        if plan is not None:
            plan_payload = plan.model_dump(mode="json")
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.survival.need_tick",
                    {
                        "actor_ref": actor_ref,
                        "need_ref": next_state.need_ref,
                        "value": next_state.value,
                        "last_tick": next_state.last_tick,
                        "policy_ref": policy.policy_ref,
                        "policy_revision": policy.revision,
                        "consumption_plan": plan_payload,
                    },
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={"survival": tick},
        )
        return self._store.append_batch(batch)

    def settle_consumption(
        self,
        *,
        actor_ref: str,
        plan: ConsumptionPlan,
        accepted_reservation_refs: tuple[str, ...],
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if not accepted_reservation_refs:
            raise ValueError("reservation_required")
        required = set(plan.required_owner_refs)
        provided = set(accepted_reservation_refs)
        if required and not required.issubset(provided):
            raise ValueError("reservation_required")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        stream_id = f"gameplay:survival:{actor_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.survival.consumption_accepted",
                    {
                        "actor_ref": actor_ref,
                        "need_ref": plan.need_ref,
                        "item_ref": plan.item_ref,
                        "quantity": plan.quantity,
                        "accepted_reservation_refs": accepted_reservation_refs,
                    },
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions=plan.pinned_revisions,
        )
        return self._store.append_batch(batch)
    @staticmethod
    def tick(*, policy: SurvivalPolicy, definition: NeedDefinition, state: NeedState, tick: int) -> tuple[NeedState, ConsumptionPlan | None]:
        if tick < state.last_tick:
            raise ValueError("revision_conflict")
        if policy.mode in {SurvivalMode.DISABLED, SurvivalMode.NARRATIVE}:
            return state, None
        elapsed = tick - state.last_tick
        if elapsed == 0:
            return state, None
        next_value = max(0.0, state.value - definition.decay_per_tick * elapsed)
        next_state = state.model_copy(update={"value": next_value, "last_tick": tick}, deep=True)
        plan = ConsumptionPlan(
            need_ref=definition.need_ref,
            item_ref="item:food",
            quantity=1,
            required_owner_refs=("inventory", "ownership"),
            pinned_revisions={"survival": tick},
        ) if next_value < 0.5 else None
        return next_state, plan

__all__ = ["ConsumptionPlan", "NeedDefinition", "NeedState", "SurvivalAuthority", "SurvivalMode", "SurvivalPolicy", "SurvivalProjection", "SurvivalProjector"]
