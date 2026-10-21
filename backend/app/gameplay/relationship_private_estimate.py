"""Actor-private Fear/Morale estimate admission.

This is a deliberately narrow Task5 slice.  Fear and morale are observations
held by one character, not shared relationship facts and not world truth.  The
adapter reuses the existing character relational-memory owner and does not
append gameplay events or create a second store.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.character_agent.memory.relational_memory import CharacterRelationalMemory


EstimateKind = Literal["fear", "morale"]


@dataclass(frozen=True)
class PrivateEstimateResult:
    committed: bool
    actor_id: str
    estimate_kind: EstimateKind | None = None
    value: float | None = None
    source_event_id: str | None = None
    stop_reason: str | None = None


class ActorPrivateAffectEstimateAuthority:
    """Owner for character-private affect estimates.

    ``CharacterRelationalMemory`` is the existing private-memory owner.  This
    boundary only admits finite normalized estimates with explicit provenance;
    it never accepts a threat, target, relationship, or shared visibility
    payload.
    """

    _ALLOWED_KINDS = frozenset({"fear", "morale"})

    def __init__(self, *, memory: CharacterRelationalMemory) -> None:
        self._memory = memory

    def record(
        self,
        *,
        actor_id: str,
        estimate_kind: EstimateKind,
        value: float,
        source_event_id: str,
        producer_ts: int,
        visibility_scope: str = "actor_private",
    ) -> PrivateEstimateResult:
        if not isinstance(actor_id, str) or not actor_id:
            return self._reject(actor_id, "private_estimate_actor_invalid")
        if estimate_kind not in self._ALLOWED_KINDS:
            return self._reject(actor_id, "private_estimate_kind_invalid")
        if type(value) is not float or value != value or value < 0.0 or value > 1.0:
            return self._reject(actor_id, "private_estimate_value_invalid")
        if not isinstance(source_event_id, str) or not source_event_id:
            return self._reject(actor_id, "private_estimate_source_missing")
        if type(producer_ts) is not int or producer_ts < 0:
            return self._reject(actor_id, "private_estimate_timestamp_invalid")
        if visibility_scope != "actor_private":
            return self._reject(actor_id, "private_estimate_visibility_invalid")
        self._memory.upsert_belief(
            actor_id=actor_id,
            entity_id=actor_id,
            belief_type=f"{estimate_kind}_estimate",
            value=str(value),
            source_event_id=source_event_id,
            producer_ts=producer_ts,
        )
        return PrivateEstimateResult(
            committed=True,
            actor_id=actor_id,
            estimate_kind=estimate_kind,
            value=value,
            source_event_id=source_event_id,
        )

    def recall(self, *, requester_actor_id: str, owner_actor_id: str) -> tuple[dict[str, object], ...]:
        """Return estimates only to their owning character."""
        if requester_actor_id != owner_actor_id or not requester_actor_id:
            return ()
        return tuple(
            entry
            for entry in self._memory.recall(owner_actor_id)
            if entry.get("entity_id") == owner_actor_id
            and entry.get("belief_type") in {"fear_estimate", "morale_estimate"}
        )

    @staticmethod
    def _reject(actor_id: str, reason: str) -> PrivateEstimateResult:
        return PrivateEstimateResult(committed=False, actor_id=actor_id, stop_reason=reason)


__all__ = ["ActorPrivateAffectEstimateAuthority", "PrivateEstimateResult"]
