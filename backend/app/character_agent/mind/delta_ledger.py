from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.mind_frame import MindDeltaLedger
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation


def _model_or_mapping(value: object) -> dict[str, object]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return deepcopy(dumped) if isinstance(dumped, dict) else {}
    return deepcopy(value) if isinstance(value, dict) else {}


def _model_list(values: object) -> list[dict[str, object]]:
    if not isinstance(values, list):
        return []
    return [_model_or_mapping(value) for value in values]


class MindDeltaLedgerBuilder:
    def build(
        self,
        *,
        actor_id: str,
        mind_turn_id: str,
        interpretation: CharacterInterpretation | None = None,
        l3_decision: dict[str, object] | CharacterIntentDecision | None = None,
        l4_execution_proposal: dict[str, object] | None = None,
        settlement_result: dict[str, object] | None = None,
        dialogue_or_action_outcome: dict[str, object] | None = None,
        need_tension_delta: dict[str, object] | None = None,
        skill_evidence: list[dict[str, object]] | None = None,
        relationship_update_candidates: list[dict[str, object]] | None = None,
        drift_candidates: list[dict[str, object]] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> MindDeltaLedger:
        evidence = list(evidence_refs or [])
        l3_payload = _model_or_mapping(l3_decision)
        l4_payload = deepcopy(l4_execution_proposal or {})
        settlement_payload = deepcopy(settlement_result or {})
        outcome_payload = deepcopy(dialogue_or_action_outcome or {})
        memory_candidate = {
            "event_type": "character_mind_turn_summary",
            "l3_decision": deepcopy(l3_payload),
            "l4_execution_proposal": deepcopy(l4_payload),
            "settlement_result": deepcopy(settlement_payload),
            "dialogue_or_action_outcome": deepcopy(outcome_payload),
            "evidence_refs": deepcopy(evidence),
        }
        return MindDeltaLedger(
            actor_id=actor_id,
            mind_turn_id=mind_turn_id,
            belief_deltas=_model_list(getattr(interpretation, "belief_deltas", [])),
            social_deltas=_model_list(getattr(interpretation, "social_deltas", [])),
            higher_order_deltas=_model_list(getattr(interpretation, "higher_order_deltas", [])),
            dynamic_state_deltas=self._dynamic_state_delta(interpretation),
            need_tension_deltas=deepcopy(need_tension_delta or {}),
            goal_deltas=[deepcopy(l3_payload)] if l3_payload else [],
            skill_evidence_deltas=deepcopy(skill_evidence or []),
            memory_write_candidates=[memory_candidate],
            relationship_update_candidates=deepcopy(relationship_update_candidates or []),
            drift_candidates=deepcopy(drift_candidates or []),
        )

    @staticmethod
    def _dynamic_state_delta(interpretation: CharacterInterpretation | None) -> dict[str, object]:
        if interpretation is None:
            return {}
        delta = getattr(interpretation, "dynamic_state_delta", None)
        if delta is None:
            return {}
        if hasattr(delta, "as_mapping"):
            return deepcopy(delta.as_mapping())
        return _model_or_mapping(delta)
