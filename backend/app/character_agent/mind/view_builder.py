from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.mind_frame import (
    CharacterMindFrame,
    CognitionWorkspace,
    L2InterpretationView,
    L3PlanningView,
    L4ExecutionView,
    MentalFactorProjectionCard,
    WritebackView,
)


class LayerContextViewBuilder:
    def build_l2_view(self, frame: CharacterMindFrame) -> L2InterpretationView:
        return L2InterpretationView(
            actor_id=frame.actor_id,
            mind_turn_id=frame.mind_turn_id,
            perception_context=self._payload_for(frame.runtime_state.cards, "perception_context"),
            effective_profile_summary=self._payload_for(frame.enduring_truth.cards, "effective_profile"),
            memory_activation_summary=deepcopy(frame.memory_evidence.summary),
            cognitive_anchor_summary=self._payload_for(frame.memory_evidence.cards, "memory_activation"),
            relationship_context_summary=self._payload_for(
                frame.memory_evidence.cards, "relationship_context"
            ),
            need_pressure_summary=self._payload_for(frame.runtime_state.cards, "need_pressure"),
            affective_body_summary=self._payload_for(frame.runtime_state.cards, "affective_body_state"),
            goal_context_summary=self._goal_context_summary(frame),
            unresolved_tension_summary=self._payload_for(
                frame.runtime_state.cards, "unresolved_tension"
            ),
            supervision_summary=self._payload_for(frame.runtime_state.cards, "supervision"),
        )

    def build_l3_view(
        self,
        frame: CharacterMindFrame,
        *,
        interpretation_summary: dict[str, object],
        workspace: CognitionWorkspace,
    ) -> L3PlanningView:
        workspace_copy = workspace.model_copy(deep=True)
        return L3PlanningView(
            actor_id=frame.actor_id,
            mind_turn_id=frame.mind_turn_id,
            interpretation_summary=deepcopy(interpretation_summary),
            cognition_workspace=workspace_copy,
            goal_context_summary=self._goal_context_summary(frame),
            need_pressure_summary=self._payload_for(frame.runtime_state.cards, "need_pressure"),
            affective_body_summary=self._payload_for(frame.runtime_state.cards, "affective_body_state"),
            skill_affordance_summary=self._payload_for(frame.affordances.cards, "skill_affordance"),
            action_affordance_summary=self._payload_for(frame.affordances.cards, "action_affordance"),
            relationship_affordance_summary=self._payload_for(
                frame.memory_evidence.cards, "relationship_context"
            ),
            hard_constraints=list(workspace_copy.hard_constraints),
            unresolved_tension_summary=self._payload_for(
                frame.runtime_state.cards, "unresolved_tension"
            ),
            supervision_summary=self._payload_for(frame.runtime_state.cards, "supervision"),
        )

    def build_l4_view(
        self,
        frame: CharacterMindFrame,
        *,
        selected_intent: str,
        selected_skill_path: dict[str, object] | None = None,
        target_refs: dict[str, str] | None = None,
    ) -> L4ExecutionView:
        physical_feasibility_summary = self._payload_for(
            frame.affordances.cards, "physical_feasibility"
        )
        return L4ExecutionView(
            actor_id=frame.actor_id,
            mind_turn_id=frame.mind_turn_id,
            selected_intent=selected_intent,
            selected_skill_path=deepcopy(selected_skill_path or {}),
            target_refs=deepcopy(target_refs or {}),
            affective_body_summary=self._payload_for(frame.runtime_state.cards, "affective_body_state"),
            presentation_constraints=[],
            realization_hints=[],
            physical_feasibility_summary=physical_feasibility_summary or {"status": "advisory"},
        )

    def build_writeback_view(
        self,
        frame: CharacterMindFrame,
        *,
        l2_deltas: dict[str, object] | None = None,
        l3_decision: dict[str, object] | None = None,
        l4_execution_proposal: dict[str, object] | None = None,
        settlement_result: dict[str, object] | None = None,
        dialogue_or_action_outcome: dict[str, object] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> WritebackView:
        return WritebackView(
            actor_id=frame.actor_id,
            mind_turn_id=frame.mind_turn_id,
            l2_deltas=deepcopy(l2_deltas or {}),
            l3_decision=deepcopy(l3_decision or {}),
            l4_execution_proposal=deepcopy(l4_execution_proposal or {}),
            settlement_result=deepcopy(settlement_result or {}),
            dialogue_or_action_outcome=deepcopy(dialogue_or_action_outcome or {}),
            evidence_refs=deepcopy(evidence_refs or []),
        )

    @staticmethod
    def _payload_for(
        cards: list[MentalFactorProjectionCard],
        factor_type: str,
    ) -> dict[str, object]:
        for card in cards:
            if card.factor_type == factor_type:
                return deepcopy(card.payload)
        return {}

    def _goal_context_summary(self, frame: CharacterMindFrame) -> dict[str, object]:
        payload = self._payload_for(frame.runtime_state.cards, "goal_context")
        current = payload.get("current_goal_state", {})
        if isinstance(current, dict):
            return deepcopy(current)
        return {}
