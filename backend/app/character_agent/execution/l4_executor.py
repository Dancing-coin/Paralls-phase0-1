from app.models.character_agent_runtime import (
    CharacterIntentDecision,
    CharacterInterpretation,
)
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot


class CharacterAgentL4Executor:
    def build_execution_plan(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> dict[str, object]:
        target = interpretation.attention_target or (snapshot.attention_targets[0] if snapshot.attention_targets else "")
        guarding_elevated = self._guarding_elevated(snapshot=snapshot, interpretation=interpretation, decision=decision)
        physiology_hint = "elevated" if guarding_elevated or snapshot.vigilance_level == "elevated" else "stable"
        spacing_behavior = self._spacing_behavior(target=target, snapshot=snapshot, decision=decision)
        posture = self._body_posture(snapshot=snapshot, decision=decision, guarding_elevated=guarding_elevated)
        expression_hint = self._expression_hint(snapshot=snapshot, interpretation=interpretation)
        breath = "elevated" if snapshot.vigilance_level == "elevated" or guarding_elevated else "steady"
        return {
            "actor_id": decision.actor_id,
            "speech_channel": {
                "dialogue_act": decision.selected_intent,
                "utterance_request": interpretation.interpreted_summary,
            },
            "face_channel": {
                "expression_hint": expression_hint,
            },
            "body_channel": {
                "posture": posture,
                "gesture_hint": decision.selected_intent,
            },
            "social_spatial_channel": {
                "spacing_behavior": spacing_behavior,
                "target_ref": target,
            },
            "physiology_channel": {
                "breath": breath,
                "guarding": "elevated" if guarding_elevated else "low",
            },
            "actor_control_frames": [
                {
                    "actor_id": decision.actor_id,
                    "producer_ts": snapshot.updated_at,
                    "causation_id": f"character_agent:{snapshot.updated_at}:{decision.actor_id}",
                    "correlation_id": f"character_agent:{snapshot.updated_at}:{decision.actor_id}",
                    "controller_source": "agent",
                    "control_mode": "agent_controlled",
                    "target_ref": target,
                    "action": decision.selected_intent,
                    "gait": "walk",
                }
            ],
            "presentation_plan": {
                "actor_id": decision.actor_id,
                "target_ref": target,
                "motion_state": {},
                "focus_state": {
                    "target_id": target,
                },
                "action_state": {
                    "requested_action": decision.selected_intent,
                    "override_state": "",
                },
                "equipment_state": {},
                "expression_hint": expression_hint,
                "physiology_hint": physiology_hint,
                "speech_state": {
                    "active_command_type": decision.selected_intent,
                    "utterance_request": interpretation.interpreted_summary,
                },
            },
            "action_request_bundle": {
                "requested_actions": self._build_requested_actions(
                    actor_id=decision.actor_id,
                    selected_intent=decision.selected_intent,
                    target_ref=target,
                    interpretation=interpretation,
                ),
            },
        }

    def _guarding_elevated(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> bool:
        return (
            interpretation.risk_level in {"medium", "high"}
            or decision.selected_intent == "self_protect"
            or bool(snapshot.recent_constraint_results)
            or bool(snapshot.body_state_hints)
        )

    def _spacing_behavior(
        self,
        *,
        target: str,
        snapshot: CharacterPrivateWorldSnapshot,
        decision: CharacterIntentDecision,
    ) -> str:
        if decision.selected_intent in {"withdraw", "break_contact", "seek_private_distance", "self_protect"}:
            return "increase_distance"
        if decision.selected_intent in {"follow_target", "approach"} and target != "":
            return "close_distance"
        if target == "":
            return "hold"
        if snapshot.vigilance_level == "elevated" or bool(snapshot.recent_world_changes):
            return "orient_to_target"
        return "orient_to_target"

    def _body_posture(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        decision: CharacterIntentDecision,
        guarding_elevated: bool,
    ) -> str:
        if decision.selected_intent == "self_protect":
            return "guarded"
        if snapshot.vigilance_level == "elevated":
            return "attentive_guard"
        if guarding_elevated:
            return "guarded"
        return "attentive"

    def _expression_hint(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
    ) -> str:
        if snapshot.vigilance_level == "elevated":
            return "heightened_vigilance"
        return interpretation.interpretation_type

    def _build_requested_actions(
        self,
        *,
        actor_id: str,
        selected_intent: str,
        target_ref: str,
        interpretation: CharacterInterpretation,
    ) -> list[dict[str, object]]:
        if selected_intent == "inspect_object" and target_ref.startswith("obj_"):
            return [
                {
                    "request_type": "interact",
                    "actor_id": actor_id,
                    "target_object_id": target_ref,
                    "interaction_type": "inspect",
                }
            ]
        if selected_intent == "approach" and target_ref.startswith("char_"):
            return [
                {
                    "request_type": "approach",
                    "actor_id": actor_id,
                    "target_actor_id": target_ref,
                }
            ]
        if selected_intent == "speak_public" and target_ref.startswith("char_"):
            return [
                {
                    "request_type": "speak_public",
                    "actor_id": actor_id,
                    "target_actor_id": target_ref,
                    "content": interpretation.interpreted_summary,
                }
            ]
        if selected_intent == "speak_private" and target_ref.startswith("char_"):
            return [
                {
                    "request_type": "speak_private",
                    "actor_id": actor_id,
                    "target_actor_id": target_ref,
                    "content": interpretation.interpreted_summary,
                }
            ]
        if selected_intent == "share_info" and target_ref.startswith("char_"):
            return [
                {
                    "request_type": "share_info",
                    "actor_id": actor_id,
                    "target_actor_id": target_ref,
                    "content": interpretation.interpreted_summary,
                }
            ]
        if selected_intent == "withhold" and target_ref.startswith("char_"):
            return [
                {
                    "request_type": "withhold",
                    "actor_id": actor_id,
                    "target_actor_id": target_ref,
                    "content": interpretation.interpreted_summary,
                }
            ]
        if selected_intent == "seek_private_distance" and target_ref.startswith("char_"):
            return [
                {
                    "request_type": "seek_private_distance",
                    "actor_id": actor_id,
                    "target_actor_id": target_ref,
                }
            ]
        if selected_intent == "withdraw" and target_ref.startswith("char_"):
            return [
                {
                    "request_type": "withdraw",
                    "actor_id": actor_id,
                    "target_actor_id": target_ref,
                }
            ]
        if selected_intent == "follow_target" and target_ref.startswith("char_"):
            return [
                {
                    "request_type": "follow_target",
                    "actor_id": actor_id,
                    "target_actor_id": target_ref,
                }
            ]
        if selected_intent == "break_contact" and target_ref.startswith("char_"):
            return [
                {
                    "request_type": "break_contact",
                    "actor_id": actor_id,
                    "target_actor_id": target_ref,
                }
            ]
        return []
