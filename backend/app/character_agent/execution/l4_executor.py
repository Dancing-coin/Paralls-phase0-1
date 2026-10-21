from app.models.character_agent_runtime import (
    CharacterIntentDecision,
    CharacterInterpretation,
)
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.models.character_execution import CharacterExecutionContract
from app.character_agent.models.expression_regulation import DeviationEpisode, ExpressionRegulationFrame
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.skills.models import (
    ActionSettlementResult,
    CompositeActionProposal,
    PrimitiveActionPlan,
    SkillEvaluationResult,
)
from app.models.siming_character_bridge import CharacterSemanticIntentProposal
from copy import deepcopy


class CharacterAgentL4Executor:
    def build_intent_proposal(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
        turn_context: CharacterTurnContext,
    ) -> CharacterSemanticIntentProposal:
        """Project cognition/INF inputs into the shared semantic ingress.

        This is deliberately narrower than the historical execution plan: it
        contains semantic IDs, canonical claims, locomotion relation, and
        provenance only.  Local profile selection and body execution remain in
        Godot's controller port/arbiter path.
        """
        if not isinstance(turn_context, CharacterTurnContext):
            raise TypeError("current canonical turn context is required")
        if turn_context.actor_id != decision.actor_id or turn_context.actor_id != snapshot.actor_id:
            raise ValueError("intent proposal actor does not match canonical turn")
        if turn_context.lifecycle not in {"prepared", "running", "awaiting_settlement"}:
            raise ValueError("intent proposal requires an active canonical turn")

        selected_intent = str(decision.selected_intent or "observe")
        frozen_targets = [
            str(ref).strip() for ref in getattr(decision, "target_refs", [])
            if str(ref).strip()
        ]
        # A choice without a frozen target is intentionally targetless. L2
        # attention and the local snapshot are evidence, never target ingress.
        target_ref = frozen_targets[0] if frozen_targets else None
        claims, locomotion_relation = self._semantic_claims(selected_intent)
        context_tags = self._context_tags(
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
        )
        intent_tags = [f"intent:{selected_intent}"]
        return CharacterSemanticIntentProposal(
            actor_ref=f"character:{decision.actor_id}",
            source_id="character_agent_l4",
            intent_tags=intent_tags,
            context_tags=context_tags,
            semantic_action_id=(
                str(getattr(decision, "semantic_action_id", "") or "")
                or self._semantic_action_id(selected_intent)
            ),
            target_ref=target_ref,
            claims=claims,
            locomotion_relation=locomotion_relation,
            presentation_cues=self._presentation_cues(selected_intent),
            reason_codes=["character_agent:l4", *self._reason_codes(decision)],
            source="character_agent",
            confidence=float(max(0.0, min(1.0, interpretation.salience_score))),
            provenance={
                "turn_id": turn_context.turn_id,
                "source_ref": turn_context.source_event_ref,
                "producer_ts": turn_context.producer_ts,
                "branch_id": turn_context.branch_id,
            },
            privacy_scope=f"actor_private:{decision.actor_id}",
            authority_scope="world:default",
            expected_revision_vector=dict(turn_context.input_revision_vector),
            causation_id=turn_context.causation_id,
            correlation_id=turn_context.correlation_id,
        )

    @staticmethod
    def _semantic_action_id(selected_intent: str) -> str:
        return {
            "short_punch": "action:melee.short_punch",
            "unarmed_punch": "action:melee.unarmed_punch",
            "sword_slash": "action:melee.sword_slash",
            "observe": "action:observe",
            "observe_target": "action:observe",
            "attention_shift": "action:observe",
            "inspect_object": "action:inspect",
            "use_object": "action:use",
            "finish_use": "action:finish_use",
            "speak_public": "action:speak",
            "speak_private": "action:speak",
            "share_info": "action:speak",
            "withhold": "action:speak",
            "approach": "action:approach",
            "follow_target": "action:approach",
            "seek_private_distance": "action:approach",
            "withdraw": "action:withdraw",
            "break_contact": "action:withdraw",
        }.get(selected_intent, f"action:{selected_intent}")

    @staticmethod
    def _semantic_claims(selected_intent: str) -> tuple[list[str], str]:
        if selected_intent == "short_punch":
            return ["upper_body", "right_arm"], "coexist"
        if selected_intent == "unarmed_punch":
            return ["right_arm", "left_arm"], "replace_locomotion"
        if selected_intent == "sword_slash":
            return ["right_arm", "weapon_slot:sword", "weapon_hit_volume:sword"], "replace_locomotion"
        if selected_intent in {"approach", "follow_target", "seek_private_distance", "withdraw", "break_contact"}:
            return ["world_motion", "facing"], "drive_locomotion"
        if selected_intent in {"speak_public", "speak_private", "share_info", "withhold"}:
            return ["upper_body", "voice_channel"], "coexist"
        if selected_intent in {"inspect_object", "use_object", "finish_use", "interact"}:
            return ["upper_body", "interaction_reach"], "coexist"
        return ["head"], "coexist"

    @staticmethod
    def _presentation_cues(selected_intent: str) -> list[str]:
        if selected_intent in {"speak_public", "speak_private", "share_info", "withhold"}:
            return ["presentation:focus_target", "expression:focused"]
        if selected_intent in {"approach", "follow_target", "seek_private_distance"}:
            return ["presentation:locomotion_walk"]
        return ["presentation:observe"]

    @staticmethod
    def _reason_codes(decision: CharacterIntentDecision) -> list[str]:
        return [f"goal_source:{value}" for value in decision.goal_sources if value]

    @staticmethod
    def _context_tags(
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> list[str]:
        tags: list[str] = []

        def add(namespace: str, value: object) -> None:
            rendered = str(value or "").strip()
            if not rendered:
                return
            if ":" in rendered and rendered.split(":", 1)[0] in {
                "goal", "intent", "evidence", "capability", "affordance", "constraint",
                "state", "status", "action", "phase", "occupy", "event", "authority",
                "presentation", "expression",
            }:
                tags.append(rendered)
            else:
                tags.append(f"{namespace}:{rendered}")

        for value in (
            decision.primary_goal,
            decision.long_term_goal,
            decision.mid_term_strategy,
            decision.immediate_goal,
            *decision.supporting_goals,
        ):
            add("goal", value)
        for value in (*decision.evidence_tags, *snapshot.evidence_tags, *snapshot.salience_tags):
            add("evidence", value)
        for value in (*decision.capability_tags, *snapshot.capability_tags):
            add("capability", value)
        for value in (*decision.affordance_tags, *snapshot.affordance_tags):
            add("affordance", value)
        for value in (*decision.constraint_tags, *decision.blockers, *snapshot.recent_constraint_results):
            add("constraint", value)
        if interpretation.attention_target:
            add("evidence", f"target:{interpretation.attention_target}")
        return list(dict.fromkeys(tags))

    def build_execution_contract(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
        turn_context: CharacterTurnContext,
        *,
        skill_evaluation_result: SkillEvaluationResult | None = None,
        action_settlement_result: ActionSettlementResult | None = None,
        expression_regulation: ExpressionRegulationFrame | None = None,
        deviation_episode: DeviationEpisode | None = None,
    ) -> CharacterExecutionContract:
        """Build the sole production-shaped L4 output for a canonical turn.

        The existing execution plan remains a useful local shadow projection;
        this method selects only semantic and presentation-safe data for the
        authority boundary.  It deliberately does not copy body/world-write
        fields or authoritative settlement effects.
        """
        if not isinstance(turn_context, CharacterTurnContext):
            raise TypeError("current canonical turn context is required")
        if turn_context.actor_id != decision.actor_id or turn_context.actor_id != snapshot.actor_id:
            raise ValueError("execution contract actor does not match canonical turn")
        if turn_context.lifecycle not in {"prepared", "running", "awaiting_settlement"}:
            raise ValueError("execution contract requires an active canonical turn")
        if expression_regulation is not None and expression_regulation.intent != decision.selected_intent:
            raise ValueError("expression frame cannot change selected intent")

        plan = self.build_execution_plan(
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
        )
        action_bundle = plan.get("action_request_bundle", {})
        requested_actions = (
            action_bundle.get("requested_actions", [])
            if isinstance(action_bundle, dict)
            else []
        )
        action = requested_actions[0] if requested_actions and isinstance(requested_actions[0], dict) else {}
        semantic_proposal = self.build_intent_proposal(
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
            turn_context=turn_context,
        )
        frozen_target_refs = [
            str(ref).strip() for ref in getattr(decision, "target_refs", [])
            if str(ref).strip()
        ]
        target_refs: list[str] = list(dict.fromkeys(frozen_target_refs))
        if decision.selected_intent in {
            "inspect_object", "use_object", "finish_use", "share_info", "speak_private", "follow_target",
            "seek_private_distance", "break_contact", "withdraw", "approach",
            "withhold", "short_punch", "unarmed_punch", "sword_slash",
        } and not target_refs:
            raise ValueError("execution target_ref required")

        metadata = plan.get("skill_realization_metadata", {})
        metadata = metadata if isinstance(metadata, dict) else {}
        selected_path = metadata.get("selected_skill_path", {})
        selected_path = selected_path if isinstance(selected_path, dict) else {}
        if skill_evaluation_result is not None:
            selected_path = dict(skill_evaluation_result.selected_path)
        primitive_tags = metadata.get("primitive_action_tags", [])
        primitive_tags = list(primitive_tags) if isinstance(primitive_tags, list) else []
        primitive_keys = metadata.get("primitive_realization_keys", [])
        primitive_keys = list(primitive_keys) if isinstance(primitive_keys, list) else []
        presentation = plan.get("presentation_plan", {})
        presentation = presentation if isinstance(presentation, dict) else {}
        # Keep the hint vocabulary intentionally local/presentation-safe.  The
        # contract scanner rejects any accidental body/world authority fields.
        allowed_hints: dict[str, object] = {
            "expression_regulation": (expression_regulation or ExpressionRegulationFrame(
                intent=decision.selected_intent,
                body_constraints=tuple(snapshot.body_state_hints),
                source_revisions=(("snapshot", str(turn_context.snapshot_revision)),),
            )).model_dump(mode="json"),
            "expression_plan": {
                channel: deepcopy(plan[channel])
                for channel in ("speech_channel", "face_channel", "body_channel",
                                "social_spatial_channel", "physiology_channel")
            },
            "presentation": {
                "motion_state": presentation.get("motion_state", {}),
                "focus_state": presentation.get("focus_state", {}),
                "action_state": presentation.get("action_state", {}),
                "expression_hint": presentation.get("expression_hint", ""),
                "physiology_hint": presentation.get("physiology_hint", ""),
                "speech_state": presentation.get("speech_state", {}),
            },
            "skill": {
                "selected_path": selected_path,
                "primitive_action_tags": primitive_tags,
                "primitive_realization_keys": primitive_keys,
            },
        }
        if deviation_episode is not None:
            allowed_hints["deviation_episode"] = deviation_episode.model_dump(mode="json")
        # Presentation may not reintroduce L2 attention as a choice target.
        allowed_hints["expression_plan"]["social_spatial_channel"]["target_ref"] = (
            target_refs[0] if target_refs else ""
        )
        frozen_semantic_action_id = str(getattr(decision, "semantic_action_id", "") or "")
        candidate_pins = dict(getattr(decision, "candidate_revision_pins", {}) or {})
        target_revision_vector = candidate_pins.get("target_revision_vector", {})
        if not isinstance(target_revision_vector, dict):
            target_revision_vector = {}
        expected_observation: dict[str, object] = {
            "semantic_intent_id": decision.selected_intent,
            "semantic_action_id": str(
                frozen_semantic_action_id
                or plan.get("composite_action_proposal", {}).get("action_id", decision.selected_intent)
                if isinstance(plan.get("composite_action_proposal"), dict)
                else decision.selected_intent
            ),
            "target_refs": target_refs,
            "requested_action": str(action.get("request_type", "") or decision.selected_intent),
            "candidate_id": str(getattr(decision, "candidate_id", "") or ""),
            "candidate_digest": str(getattr(decision, "candidate_digest", "") or ""),
            "owner_route": str(getattr(decision, "owner_route", "") or ""),
            "target_admission_digest": str(candidate_pins.get("target_admission_digest", "") or ""),
            "execution_scope": {
                "room_id": snapshot.room_id,
                "scene_id": snapshot.scene_id,
                "zone_id": snapshot.zone_id,
            },
        }
        if interpretation.interpreted_summary:
            expected_observation["summary"] = interpretation.interpreted_summary

        return CharacterExecutionContract(
            turn_id=turn_context.turn_id,
            actor_ref=f"character:{decision.actor_id}",
            source_ref=turn_context.source_event_ref,
            producer_ts=turn_context.producer_ts,
            target_refs=tuple(target_refs),
            target_ref=target_refs[0] if len(target_refs) == 1 else None,
            semantic_intent_id=decision.selected_intent,
            semantic_action_id=str(
                getattr(decision, "semantic_action_id", None)
                or semantic_proposal.semantic_action_id
                or expected_observation["semantic_action_id"]
            ),
            source_id=semantic_proposal.source_id,
            intent_tags=tuple(semantic_proposal.intent_tags),
            context_tags=tuple(semantic_proposal.context_tags),
            claims=tuple(semantic_proposal.claims),
            locomotion_relation=semantic_proposal.locomotion_relation,
            allowed_realization_hints=allowed_hints,
            expected_revision_vector=dict(turn_context.input_revision_vector),
            expected_memory_revision_vector=dict(turn_context.memory_revision_vector),
            expected_snapshot_revision=turn_context.snapshot_revision,
            expected_target_revision_vector={str(key): int(value) for key, value in target_revision_vector.items()},
            context_revision=str(
                getattr(decision, "candidate_digest", "")
                or candidate_pins.get("frame_digest", "")
                or turn_context.policy_revision
            ),
            idempotency_key=f"execution:{turn_context.turn_id}",
            causation_id=turn_context.causation_id,
            correlation_id=turn_context.correlation_id,
            privacy_scope=f"actor_private:{turn_context.actor_id}",
            authority_scope="world:default",
            expected_observation=expected_observation,
        )

    def attach_realization_hints(self, plan: dict[str, object]) -> dict[str, object]:
        presentation_plan = plan.get("presentation_plan", {})
        if not isinstance(presentation_plan, dict):
            presentation_plan = {}
            plan["presentation_plan"] = presentation_plan
        presentation_plan["realization_hints"] = {
            "selected_skill_path": self._realization_selected_skill_path(plan),
            "primitive_action_tags": self._realization_primitive_action_tags(plan),
            "settlement_outcome": self._realization_settlement_outcome(plan),
        }
        return plan

    def attach_skill_realization_metadata(
        self,
        *,
        plan: dict[str, object],
        skill_evaluation_result: SkillEvaluationResult,
        primitive_action_plan: PrimitiveActionPlan | None = None,
        action_settlement_result: ActionSettlementResult | None = None,
    ) -> None:
        settlement_outcome: dict[str, object] = {}
        if action_settlement_result is not None:
            settlement_outcome = {
                "outcome_band": action_settlement_result.outcome_band,
                "failure_domains": list(action_settlement_result.failure_domains),
                "primary_failure_domain": action_settlement_result.primary_failure_domain,
                "realization_hints": list(action_settlement_result.realization_hints),
            }
        metadata = {
            "selected_skill_path": dict(skill_evaluation_result.selected_path),
            "primitive_action_tags": list(primitive_action_plan.primitive_actions) if primitive_action_plan else [],
            "primitive_realization_keys": list(primitive_action_plan.realization_keys) if primitive_action_plan else [],
            "settlement_outcome": settlement_outcome,
        }
        plan["skill_realization_metadata"] = metadata
        presentation_plan = plan.get("presentation_plan")
        if isinstance(presentation_plan, dict):
            presentation_plan["skill_realization_metadata"] = dict(metadata)

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
        plan = {
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
        return self.attach_realization_hints(plan)

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
            action_id={
                "observe": "survey_scene",
                "observe_target": "survey_scene",
                "attention_shift": "survey_scene",
                "inspect_object": "survey_scene",
                "self_protect": "assess_visible_threat",
            }.get(selected_intent, selected_intent),
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
        if selected_intent in {"inspect_object", "use_object", "finish_use"} and target_ref.startswith("obj_"):
            interaction_type = {"inspect_object": "inspect", "use_object": "use",
                                "finish_use": "finish_use"}[selected_intent]
            return [
                {
                    "request_type": "interact",
                    "actor_id": actor_id,
                    "target_object_id": target_ref,
                    "interaction_type": interaction_type,
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

    def _realization_selected_skill_path(self, plan: dict[str, object]) -> dict[str, object]:
        skill_evaluation_result = plan.get("skill_evaluation_result", {})
        if not isinstance(skill_evaluation_result, dict):
            return {}
        selected_path = skill_evaluation_result.get("selected_path", {})
        if not isinstance(selected_path, dict):
            return {}
        return deepcopy(selected_path)

    def _realization_primitive_action_tags(self, plan: dict[str, object]) -> list[str]:
        primitive_action_plan = plan.get("primitive_action_plan", {})
        if not isinstance(primitive_action_plan, dict):
            return []
        primitive_actions = primitive_action_plan.get("primitive_actions", [])
        if not isinstance(primitive_actions, list):
            return []
        return [str(action) for action in primitive_actions if str(action or "") != ""]

    def _realization_settlement_outcome(self, plan: dict[str, object]) -> dict[str, object]:
        action_settlement_result = plan.get("action_settlement_result", {})
        if not isinstance(action_settlement_result, dict):
            return {}
        settlement_outcome: dict[str, object] = {}
        for key in (
            "outcome_band",
            "failure_domains",
            "primary_failure_domain",
            "realization_hints",
        ):
            value = action_settlement_result.get(key)
            if isinstance(value, list):
                settlement_outcome[key] = [str(entry) for entry in value if str(entry or "") != ""]
            elif isinstance(value, str):
                if value != "":
                    settlement_outcome[key] = value
        return settlement_outcome
