from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.mind_frame import MindDeltaLedger
from app.models.character_agent_runtime import CharacterInterpretation


class MindLedgerRuntimePort(Protocol):
    def _apply_cognition_update(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        interpretation: CharacterInterpretation,
    ) -> None: ...

    def _session_append_event(
        self,
        *,
        actor_id: str,
        event_type: str,
        producer_ts: int,
        payload: dict[str, object],
    ) -> None: ...


class MindWritebackPolicyRouter:
    _DYNAMIC_STATE_FIELDS = frozenset(CharacterDynamicStateDelta.model_fields)

    def apply(
        self,
        *,
        runtime: MindLedgerRuntimePort,
        actor_id: str,
        producer_ts: int,
        ledger: MindDeltaLedger,
    ) -> None:
        interpretation = self._interpretation_from_ledger(actor_id=actor_id, ledger=ledger)
        if (
            interpretation.belief_deltas
            or interpretation.social_deltas
            or interpretation.higher_order_deltas
            or interpretation.dynamic_state_delta.as_mapping()
        ):
            runtime._apply_cognition_update(
                actor_id=actor_id,
                producer_ts=producer_ts,
                interpretation=interpretation,
            )
        self._append_candidates(
            runtime=runtime,
            actor_id=actor_id,
            producer_ts=producer_ts,
            event_type="character_mind_turn_summary_event",
            candidates=ledger.memory_write_candidates,
        )
        self._append_candidates(
            runtime=runtime,
            actor_id=actor_id,
            producer_ts=producer_ts,
            event_type="character_skill_evidence_candidate_event",
            candidates=ledger.skill_evidence_deltas,
        )
        self._append_candidates(
            runtime=runtime,
            actor_id=actor_id,
            producer_ts=producer_ts,
            event_type="character_drift_candidate_event",
            candidates=ledger.drift_candidates,
        )

    def _interpretation_from_ledger(
        self,
        *,
        actor_id: str,
        ledger: MindDeltaLedger,
    ) -> CharacterInterpretation:
        return CharacterInterpretation(
            actor_id=actor_id,
            interpreted_summary=f"mind delta ledger writeback for {ledger.mind_turn_id}",
            interpretation_type="ledger_writeback",
            salience_score=0.0,
            ambiguity_level="low",
            risk_level="low",
            opportunity_level="low",
            belief_deltas=self._belief_deltas(ledger.belief_deltas),
            social_deltas=self._social_deltas(
                ledger.social_deltas,
                ledger.relationship_update_candidates,
            ),
            higher_order_deltas=self._higher_order_deltas(ledger.higher_order_deltas),
            dynamic_state_delta=self._dynamic_state_delta(ledger.dynamic_state_deltas),
            reasoning_trace_summary=ledger.mind_turn_id,
        )

    def _belief_deltas(
        self,
        belief_deltas: list[dict[str, object]],
    ) -> list[CharacterBeliefDelta]:
        typed: list[CharacterBeliefDelta] = []
        for delta in belief_deltas:
            if not isinstance(delta, dict):
                continue
            typed.append(
                CharacterBeliefDelta(
                    proposition_key=str(delta.get("proposition_key", "") or ""),
                    proposition=str(delta.get("proposition", "") or ""),
                    state=str(delta.get("state", "suspected") or "suspected"),
                    confidence=float(delta.get("confidence", 0.0) or 0.0),
                )
            )
        return typed

    def _social_deltas(
        self,
        social_deltas: list[dict[str, object]],
        relationship_update_candidates: list[dict[str, object]],
    ) -> list[CharacterSocialDelta]:
        typed: list[CharacterSocialDelta] = []
        for delta in [*social_deltas, *relationship_update_candidates]:
            normalized = self._social_delta(delta)
            if normalized is not None:
                typed.append(normalized)
        return typed

    def _social_delta(
        self,
        delta: dict[str, object],
    ) -> CharacterSocialDelta | None:
        if not isinstance(delta, dict):
            return None
        entity_id = str(delta.get("entity_id", "") or "")
        if entity_id == "":
            return None
        shared_secret_refs = delta.get("shared_secret_refs", [])
        return CharacterSocialDelta(
            entity_id=entity_id,
            trust_baseline=float(delta.get("trust_baseline", 0.5) or 0.5),
            suspicion_baseline=float(delta.get("suspicion_baseline", 0.0) or 0.0),
            intimacy=float(delta.get("intimacy", 0.0) or 0.0),
            dependency=float(delta.get("dependency", 0.0) or 0.0),
            unresolved_tension=float(delta.get("unresolved_tension", 0.0) or 0.0),
            shared_secret_refs=[
                str(item) for item in deepcopy(shared_secret_refs) if str(item)
            ]
            if isinstance(shared_secret_refs, list)
            else [],
        )

    def _higher_order_deltas(
        self,
        higher_order_deltas: list[dict[str, object]],
    ) -> list[CharacterHigherOrderDelta]:
        typed: list[CharacterHigherOrderDelta] = []
        for delta in higher_order_deltas:
            normalized = self._higher_order_delta(delta)
            if normalized is not None:
                typed.append(normalized)
        return typed

    def _higher_order_delta(
        self,
        delta: dict[str, object],
    ) -> CharacterHigherOrderDelta | None:
        if not isinstance(delta, dict):
            return None
        subject_actor_id = str(delta.get("subject_actor_id", "") or "")
        proposition_key = str(delta.get("proposition_key", "") or "")
        meta_belief = str(delta.get("meta_belief", "") or "")
        if subject_actor_id == "" or proposition_key == "" or meta_belief == "":
            return None
        return CharacterHigherOrderDelta(
            subject_actor_id=subject_actor_id,
            proposition_key=proposition_key,
            meta_belief=meta_belief,
            confidence=float(delta.get("confidence", 0.0) or 0.0),
        )

    def _append_candidates(
        self,
        *,
        runtime: MindLedgerRuntimePort,
        actor_id: str,
        producer_ts: int,
        event_type: str,
        candidates: list[dict[str, object]],
    ) -> None:
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            runtime._session_append_event(
                actor_id=actor_id,
                event_type=event_type,
                producer_ts=producer_ts,
                payload=deepcopy(candidate),
            )

    def _dynamic_state_delta(
        self,
        dynamic_state_deltas: dict[str, object],
    ) -> CharacterDynamicStateDelta:
        if not isinstance(dynamic_state_deltas, dict):
            return CharacterDynamicStateDelta()
        normalized: dict[str, object] = {}
        for key, value in dynamic_state_deltas.items():
            if key not in self._DYNAMIC_STATE_FIELDS:
                continue
            try:
                validated = CharacterDynamicStateDelta(**{key: deepcopy(value)})
            except Exception:
                continue
            field_value = getattr(validated, key)
            if field_value is not None:
                normalized[key] = field_value
        return CharacterDynamicStateDelta(**normalized)
