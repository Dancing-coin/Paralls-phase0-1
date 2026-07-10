from app.models.character_agent_runtime import (
    CharacterIntentDecision,
    CharacterInterpretation,
)
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.skills.models import CompositeActionProposal


class CharacterAgentL4Executor:
    def build_execution_plan(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> dict[str, object]:
        target = interpretation.attention_target or (snapshot.attention_targets[0] if snapshot.attention_targets else "")
        composite_action_proposal = self._composite_action_proposal(
            actor_id=decision.actor_id,
            selected_intent=decision.selected_intent,
            target=target,
            interpretation=interpretation,
            producer_ts=snapshot.updated_at,
        )
        guarding_elevated = self._guarding_elevated(snapshot=snapshot, interpretation=interpretation, decision=decision)
        physiology_hint = self._physiology_hint(snapshot=snapshot, interpretation=interpretation, decision=decision, guarding_elevated=guarding_elevated)
        spacing_behavior = self._spacing_behavior(target=target, snapshot=snapshot, interpretation=interpretation, decision=decision)
        orientation_mode = self._orientation_mode(
            target=target,
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
        )
        posture = self._body_posture(
            target=target,
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
            guarding_elevated=guarding_elevated,
        )
        gesture_hint = self._gesture_hint(target=target, decision=decision, posture=posture)
        hesitation_hint = self._hesitation_hint(interpretation=interpretation)
        focus_mode = self._focus_mode(target=target, snapshot=snapshot, interpretation=interpretation, decision=decision)
        contact_phase = self._contact_phase(target=target, interpretation=interpretation, decision=decision)
        execution_semantics = self._execution_semantics(
            decision=decision,
            contact_phase=contact_phase,
            gesture_hint=gesture_hint,
        )
        expression_hint = self._expression_hint(snapshot=snapshot, interpretation=interpretation)
        breath = "elevated" if snapshot.vigilance_level == "elevated" or guarding_elevated else "steady"
        micro_expression_plan = self._micro_expression_plan(
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
        )
        facs_ready_tags = self._facs_ready_tags(
            expression_hint=expression_hint,
            micro_expression_plan=micro_expression_plan,
        )
        motion_emphasis = self._motion_emphasis(
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
        )
        breath_state = "tight" if breath == "elevated" else "steady"
        fatigue_signal = "latent_strain" if bool(snapshot.body_state_hints) else "none"
        physiology_state_band = self._physiology_state_band(
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
            guarding_elevated=guarding_elevated,
        )
        return {
            "actor_id": decision.actor_id,
            "execution_semantics": execution_semantics,
            "speech_channel": {
                "dialogue_act": decision.selected_intent,
                "utterance_request": interpretation.interpreted_summary,
            },
            "face_channel": {
                "expression_hint": expression_hint,
                "micro_expression_plan": micro_expression_plan,
                "facs_ready_tags": facs_ready_tags,
            },
            "body_channel": {
                "posture": posture,
                "gesture_hint": gesture_hint,
                "hesitation_hint": hesitation_hint,
                "motion_emphasis": motion_emphasis,
            },
            "social_spatial_channel": {
                "spacing_behavior": spacing_behavior,
                "target_ref": target,
                "orientation_mode": orientation_mode,
                "contact_phase": contact_phase,
            },
            "physiology_channel": {
                "breath": breath,
                "breath_state": breath_state,
                "guarding": "elevated" if guarding_elevated else "low",
                "state_band": physiology_state_band,
                "fatigue_signal": fatigue_signal,
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
                "motion_state": {
                    "posture": posture,
                    "gesture_hint": gesture_hint,
                    "hesitation_hint": hesitation_hint,
                    "motion_emphasis": motion_emphasis,
                },
                "focus_state": {
                    "target_id": target,
                    "spacing_behavior": spacing_behavior,
                    "orientation_mode": orientation_mode,
                    "focus_mode": focus_mode,
                },
                "action_state": {
                    "requested_action": decision.selected_intent,
                    "override_state": "",
                },
                "contact_phase": contact_phase,
                "execution_semantics": execution_semantics,
                "equipment_state": {},
                "expression_hint": expression_hint,
                "face_state": {
                    "micro_expression_plan": micro_expression_plan,
                    "facs_ready_tags": facs_ready_tags,
                },
                "physiology_hint": physiology_hint,
                "physiology_state": {
                    "breath": breath,
                    "breath_state": breath_state,
                    "guarding": "elevated" if guarding_elevated else "low",
                    "state_band": physiology_state_band,
                    "fatigue_signal": fatigue_signal,
                },
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
            "composite_action_proposal": composite_action_proposal.model_dump(),
        }

    def _composite_action_proposal(
        self,
        *,
        actor_id: str,
        selected_intent: str,
        target: str,
        interpretation: CharacterInterpretation,
        producer_ts: int,
    ) -> CompositeActionProposal:
        target_refs: dict[str, str] = {}
        if target.startswith("char_"):
            target_refs["actor"] = target
        elif target.startswith("obj_"):
            target_refs["object"] = target
        elif target.startswith("env_"):
            target_refs["environment"] = target
        preferred_strategy_tags: list[str] = []
        if selected_intent in {"share_info", "speak_public", "speak_private"}:
            preferred_strategy_tags.append("social")
        if selected_intent in {"withdraw", "break_contact", "self_protect"}:
            preferred_strategy_tags.append("defensive")
        if interpretation.risk_level in {"medium", "high"}:
            preferred_strategy_tags.append("risk_aware")
        return CompositeActionProposal(
            proposal_id=f"composite_action:{producer_ts}:{actor_id}:{selected_intent}",
            actor_id=actor_id,
            source_intent=selected_intent,
            action_id=selected_intent,
            target_refs=target_refs,
            preferred_strategy_tags=preferred_strategy_tags,
            forbidden_strategy_tags=[],
            desired_outcomes=[interpretation.interpreted_summary] if interpretation.interpreted_summary else [],
        )

    def _contact_phase(
        self,
        *,
        target: str,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> str:
        if not self._has_actor_target(target):
            return "none"
        if decision.selected_intent in {"approach", "speak_public", "speak_private"}:
            return "greeting"
        if decision.selected_intent in {"follow_target", "share_info", "withhold"}:
            return "contact_hold"
        if interpretation.interpretation_type == "social_signal" and decision.selected_intent in {"observe_target", "attention_shift"}:
            return "contact_probe"
        return "none"

    def _execution_semantics(
        self,
        *,
        decision: CharacterIntentDecision,
        contact_phase: str,
        gesture_hint: str,
    ) -> dict[str, str]:
        return {
            "movement_intent": decision.selected_intent,
            "contact_phase": contact_phase,
            "speech_mode": self._speech_mode(decision.selected_intent),
            "gesture_mode": self._gesture_mode(decision.selected_intent, gesture_hint),
        }

    def _speech_mode(self, selected_intent: str) -> str:
        if selected_intent == "speak_public":
            return "public"
        if selected_intent == "speak_private":
            return "private"
        if selected_intent in {"share_info", "withhold"}:
            return "targeted"
        return "none"

    def _gesture_mode(self, selected_intent: str, gesture_hint: str) -> str:
        if selected_intent in {"approach", "speak_public", "speak_private"}:
            return "acknowledge"
        if gesture_hint in {"draw_back", "brace"}:
            return "guard"
        if gesture_hint in {"inspect", "trail"}:
            return gesture_hint
        return "steady"

    def _guarding_elevated(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> bool:
        return (
            interpretation.risk_level in {"medium", "high"}
            or decision.selected_intent in {"self_protect", "withdraw", "break_contact", "seek_private_distance"}
            or bool(snapshot.recent_constraint_results)
            or bool(snapshot.body_state_hints)
        )

    def _physiology_hint(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
        guarding_elevated: bool,
    ) -> str:
        if decision.selected_intent in {"withdraw", "break_contact", "seek_private_distance"}:
            return "guarded"
        if guarding_elevated or snapshot.vigilance_level == "elevated" or interpretation.risk_level in {"medium", "high"}:
            return "elevated"
        if interpretation.ambiguity_level in {"medium", "high"}:
            return "hesitant"
        return "stable"

    def _spacing_behavior(
        self,
        *,
        target: str,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> str:
        if decision.selected_intent == "pause":
            return "hold"
        if decision.selected_intent == "inspect_object":
            return "hold_attention"
        if decision.selected_intent in {"withdraw", "break_contact", "seek_private_distance", "self_protect"}:
            return "increase_distance"
        if decision.selected_intent in {"follow_target", "approach"}:
            if self._has_actor_target(target):
                return "close_distance"
            return "hold"
        if decision.selected_intent == "speak_private" and self._has_actor_target(target):
            return "hold_attention"
        if target == "":
            return "hold"
        if snapshot.vigilance_level == "elevated" or bool(snapshot.recent_world_changes) or interpretation.ambiguity_level in {"medium", "high"}:
            return "orient_to_target"
        return "orient_to_target"

    def _body_posture(
        self,
        *,
        target: str,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
        guarding_elevated: bool,
    ) -> str:
        if decision.selected_intent == "pause":
            return "paused"
        if decision.selected_intent == "inspect_object":
            return "inspect"
        if decision.selected_intent == "withdraw":
            return "withdrawn"
        if decision.selected_intent in {"break_contact", "seek_private_distance"}:
            return "guarded"
        if decision.selected_intent == "self_protect":
            return "guarded"
        if decision.selected_intent in {"approach", "follow_target"}:
            if not self._has_actor_target(target):
                return "attentive"
            return "advancing"
        if decision.selected_intent == "speak_private":
            return "attentive"
        if snapshot.vigilance_level == "elevated" or interpretation.risk_level in {"medium", "high"}:
            return "attentive_guard"
        if interpretation.ambiguity_level in {"medium", "high"}:
            return "attentive"
        if guarding_elevated:
            return "guarded"
        return "attentive"

    def _gesture_hint(self, *, target: str, decision: CharacterIntentDecision, posture: str) -> str:
        if decision.selected_intent == "pause":
            return "hold"
        if decision.selected_intent == "inspect_object":
            return "inspect"
        if decision.selected_intent in {"withdraw", "break_contact", "seek_private_distance"}:
            return "draw_back"
        if decision.selected_intent == "self_protect":
            return "brace"
        if decision.selected_intent in {"speak_public", "speak_private", "share_info", "withhold"}:
            return "present"
        if decision.selected_intent == "approach":
            if not self._has_actor_target(target):
                return "steady_point"
            return "reach_forward"
        if decision.selected_intent == "follow_target":
            if not self._has_actor_target(target):
                return "steady_point"
            return "trail"
        if posture == "attentive_guard":
            return "steady_point"
        return "steady_point"

    def _orientation_mode(
        self,
        *,
        target: str,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> str:
        if decision.selected_intent == "pause":
            return "hold"
        if decision.selected_intent == "inspect_object":
            return "hold_attention"
        if decision.selected_intent in {"withdraw", "break_contact", "seek_private_distance", "self_protect"}:
            return "increase_distance"
        if decision.selected_intent in {"approach", "follow_target"}:
            return "close_distance" if self._has_actor_target(target) else "hold"
        if target == "":
            return "hold"
        if decision.selected_intent in {"observe_target", "attention_shift", "speak_public", "speak_private", "share_info", "withhold"}:
            return "hold_attention"
        if interpretation.ambiguity_level in {"medium", "high"} or snapshot.vigilance_level == "elevated":
            return "hold_attention"
        return "orient_to_target"

    def _focus_mode(
        self,
        *,
        target: str,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> str:
        if decision.selected_intent == "pause":
            return "hold"
        if decision.selected_intent == "inspect_object":
            return "inspect"
        if decision.selected_intent == "speak_private":
            return "hold_attention"
        if decision.selected_intent in {"withdraw", "break_contact", "seek_private_distance", "self_protect"}:
            return "pull_back"
        if decision.selected_intent in {"approach", "follow_target"}:
            return "track_target" if self._has_actor_target(target) else "hold"
        if target == "":
            return "hold"
        if decision.selected_intent in {"observe_target", "attention_shift", "speak_public", "share_info", "withhold"}:
            return "hold_attention"
        if interpretation.ambiguity_level in {"medium", "high"} or snapshot.vigilance_level == "elevated":
            return "hold_attention"
        return "track_target"

    def _hesitation_hint(self, *, interpretation: CharacterInterpretation) -> str:
        if interpretation.ambiguity_level == "high":
            return "sustained_hesitation"
        if interpretation.ambiguity_level == "medium":
            return "brief_hesitation"
        return "steady_motion"

    def _physiology_state_band(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
        guarding_elevated: bool,
    ) -> str:
        if decision.selected_intent in {"withdraw", "break_contact", "seek_private_distance", "self_protect"}:
            return "guarded"
        if bool(snapshot.recent_constraint_results) or bool(snapshot.body_state_hints):
            return "guarded"
        if interpretation.risk_level in {"medium", "high"} or snapshot.vigilance_level == "elevated":
            return "elevated"
        if interpretation.ambiguity_level in {"medium", "high"}:
            return "hesitant"
        if guarding_elevated:
            return "elevated"
        return "stable"

    def _has_actor_target(self, target: str) -> bool:
        return target.startswith("char_")

    def _expression_hint(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
    ) -> str:
        if snapshot.vigilance_level == "elevated":
            return "heightened_vigilance"
        return interpretation.interpretation_type

    def _micro_expression_plan(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> list[str]:
        plan: list[str] = []
        if interpretation.ambiguity_level in {"medium", "high"}:
            plan.append("brow_tension")
        if snapshot.vigilance_level == "elevated" or interpretation.risk_level in {"medium", "high"}:
            plan.append("eye_narrow")
        if decision.selected_intent in {"withhold", "speak_private"}:
            plan.append("lip_press")
        if not plan:
            plan.append("neutral_hold")
        return plan

    def _facs_ready_tags(self, *, expression_hint: str, micro_expression_plan: list[str]) -> list[str]:
        tags = [f"expression:{expression_hint}"]
        tags.extend(f"micro:{item}" for item in micro_expression_plan)
        return tags

    def _motion_emphasis(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> str:
        if decision.selected_intent in {"approach", "follow_target"}:
            return "forward_intent"
        if decision.selected_intent in {"withdraw", "break_contact", "seek_private_distance"}:
            return "defensive_recoil"
        if snapshot.vigilance_level == "elevated" or interpretation.risk_level in {"medium", "high"}:
            return "guarded_precision"
        if interpretation.ambiguity_level in {"medium", "high"}:
            return "hesitant_precision"
        return "neutral"

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
