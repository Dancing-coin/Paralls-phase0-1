from app.character_agent.gateway.context_builder import CharacterContextBuilder
from app.character_agent.models.cognition_delta import CharacterHigherOrderDelta
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.models.cognition_delta import CharacterBeliefDelta
from app.character_agent.models.cognition_delta import CharacterSocialDelta
from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.goal_runtime import CharacterGoalHint
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.observation_memory import CharacterObservationMemoryRecord
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState
from app.character_agent.planning.triple_filter import CharacterTripleFilter
from app.models.character_agent_runtime import CharacterActiveGoalFrame
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation, CharacterSuggestionPacket


class CharacterAgentL3Service:
    def __init__(self, gateway: CharacterModelGateway | None = None) -> None:
        self._gateway = gateway or CharacterModelGateway()
        self._triple_filter = CharacterTripleFilter()

    def build_intent_plan(
        self,
        *,
        interpretation: CharacterInterpretation,
        control_mode: str,
        snapshot: dict[str, object] | None = None,
        profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
    ) -> dict[str, object]:
        interpretation = self._normalize_interpretation(interpretation)
        normalized_snapshot = self._normalize_snapshot(snapshot)
        normalized_profile = self._normalize_profile(profile)
        typed_memory_bundle = self._memory_record_bundle_model(memory_bundle)
        normalized_memory_bundle = CharacterContextBuilder.normalize_memory_bundle(typed_memory_bundle)
        normalized_working_memory_state = self._working_memory_state_mapping(working_memory_state)
        active_goal_tags = self._active_goal_tags(
            interpretation=interpretation,
            snapshot=normalized_snapshot,
            memory_bundle=typed_memory_bundle,
            profile=normalized_profile,
            working_memory_state=normalized_working_memory_state,
        )
        active_goal_frame = self._active_goal_frame(
            active_goal_tags=active_goal_tags,
            interpretation=interpretation,
            snapshot=normalized_snapshot,
            memory_bundle=typed_memory_bundle,
            profile=normalized_profile,
            working_memory_state=normalized_working_memory_state,
        )
        effective_interpretation = interpretation
        attention_target = str(interpretation.attention_target or "")
        guarded_attention_target = self._is_guarded_attention_target(
            attention_target,
            normalized_memory_bundle,
            normalized_profile,
        )
        if (
            interpretation.attention_target is None
            and isinstance(normalized_snapshot.get("recent_constraint_results"), list)
            and normalized_snapshot.get("recent_constraint_results")
            and interpretation.risk_level == "low"
        ):
            effective_interpretation = CharacterInterpretation(
                actor_id=interpretation.actor_id,
                interpreted_summary=interpretation.interpreted_summary,
                interpretation_type=interpretation.interpretation_type,
                salience_score=interpretation.salience_score,
                ambiguity_level=interpretation.ambiguity_level,
                risk_level="medium",
                opportunity_level=interpretation.opportunity_level,
                attention_target=interpretation.attention_target,
                inner_prompt_candidate=interpretation.inner_prompt_candidate,
            )
        if interpretation.attention_target and interpretation.risk_level == "low" and guarded_attention_target:
            effective_interpretation = CharacterInterpretation(
                actor_id=interpretation.actor_id,
                interpreted_summary=interpretation.interpreted_summary,
                interpretation_type=interpretation.interpretation_type,
                salience_score=interpretation.salience_score,
                ambiguity_level=interpretation.ambiguity_level,
                risk_level="medium",
                opportunity_level=interpretation.opportunity_level,
                attention_target=interpretation.attention_target,
                inner_prompt_candidate=interpretation.inner_prompt_candidate,
            )
        if (
            interpretation.attention_target is None
            and (
                (
                    isinstance(normalized_snapshot.get("recent_world_changes"), list)
                    and normalized_snapshot.get("recent_world_changes")
                )
                or str(normalized_snapshot.get("vigilance_level", "") or "") == "elevated"
            )
            and interpretation.opportunity_level == "low"
        ):
            effective_interpretation = CharacterInterpretation(
                actor_id=interpretation.actor_id,
                interpreted_summary=interpretation.interpreted_summary,
                interpretation_type=interpretation.interpretation_type,
                salience_score=interpretation.salience_score,
                ambiguity_level=interpretation.ambiguity_level,
                risk_level=interpretation.risk_level,
                opportunity_level="medium",
                attention_target=interpretation.attention_target,
                inner_prompt_candidate=interpretation.inner_prompt_candidate,
            )
        model_output = self._gateway.run_task(
            task_kind="l3_planning",
            context={
                "actor_id": interpretation.actor_id,
                "control_mode": control_mode,
                "interpretation": effective_interpretation.model_dump(),
                "profile": normalized_profile,
                "snapshot": normalized_snapshot,
                "memory": normalized_memory_bundle,
                "working_memory_state": normalized_working_memory_state,
                "active_goal_tags": active_goal_tags,
                "active_goal_frame": active_goal_frame.model_dump(),
            },
        )
        candidates = self._merge_candidates(
            model_output.get("candidate_intents", []),
            self._generate_candidates(effective_interpretation, control_mode),
        )
        filter_results = [
            self._score_candidate(
                candidate,
                effective_interpretation,
                snapshot=normalized_snapshot,
                memory_bundle=typed_memory_bundle,
                profile=normalized_profile,
                control_mode=control_mode,
                working_memory_state=normalized_working_memory_state,
                active_goal_tags=active_goal_tags,
            )
            for candidate in candidates
        ]
        return {
            "actor_id": interpretation.actor_id,
            "control_mode": control_mode,
            "active_goal_tags": active_goal_tags,
            "active_goal_frame": active_goal_frame.model_dump(),
            "model_output": model_output,
            "candidates": candidates,
            "filter_results": filter_results,
        }

    def select_intent(
        self,
        interpretation: CharacterInterpretation,
        *,
        snapshot: dict[str, object] | None = None,
        profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
    ) -> CharacterIntentDecision:
        plan = self.build_intent_plan(
            interpretation=interpretation,
            control_mode=control_mode,
            snapshot=snapshot,
            profile=profile,
            memory_bundle=memory_bundle,
            working_memory_state=working_memory_state,
        )
        model_selected_candidate = str(plan.get("model_output", {}).get("selected_intent", "") or "")
        model_recommended_candidates = self._as_string_list(plan.get("model_output", {}).get("recommended_intents", []))
        model_prefers_self_protect = (
            model_selected_candidate == "self_protect"
            or (model_recommended_candidates and model_recommended_candidates[0] == "self_protect")
        )
        fallback_candidate = model_selected_candidate or "observe"
        if not model_selected_candidate and model_recommended_candidates:
            fallback_candidate = model_recommended_candidates[0]
        chosen_candidate = ""
        fallback_result = self._filter_result_for_candidate(plan["filter_results"], fallback_candidate)
        if fallback_result and str(fallback_result.get("viability", "") or "") != "rejected":
            chosen_candidate = fallback_candidate
        for result in plan["filter_results"]:
            if chosen_candidate:
                break
            candidate_name = str(result["candidate"])
            if result["viability"] == "highly_compelling":
                chosen_candidate = candidate_name
                break
            if result["viability"] == "viable":
                if model_prefers_self_protect and candidate_name != "self_protect":
                    continue
                chosen_candidate = candidate_name
        if chosen_candidate == "":
            chosen_candidate = "observe"
        selected_result = self._filter_result_for_candidate(plan["filter_results"], chosen_candidate)
        gain_loss_score = float(selected_result.get("gain_loss_score", 0.0) or 0.0) if selected_result else 0.0
        active_goal_frame = plan.get("active_goal_frame", {})
        typed_active_goal_frame = CharacterActiveGoalFrame(
            primary_goal=str(active_goal_frame.get("primary_goal", "") or ""),
            long_term_goal=str(active_goal_frame.get("long_term_goal", "") or ""),
            mid_term_strategy=str(active_goal_frame.get("mid_term_strategy", "") or ""),
            immediate_goal=str(active_goal_frame.get("immediate_goal", "") or ""),
            supporting_goals=self._as_string_list(active_goal_frame.get("supporting_goals", [])),
            blockers=self._as_string_list(active_goal_frame.get("blockers", [])),
            goal_sources=self._as_string_list(active_goal_frame.get("goal_sources", [])),
            urgency=str(active_goal_frame.get("urgency", "low") or "low"),
        )
        return CharacterIntentDecision(
            actor_id=interpretation.actor_id,
            selected_intent=self._map_candidate_to_intent(chosen_candidate),
            persona_passed=bool(selected_result and selected_result.get("persona_passed")),
            logic_passed=bool(selected_result and selected_result.get("logic_passed")),
            gain_loss_passed=gain_loss_score >= 0.5,
            rationale=interpretation.interpreted_summary,
            primary_goal=typed_active_goal_frame.primary_goal,
            long_term_goal=typed_active_goal_frame.long_term_goal,
            mid_term_strategy=typed_active_goal_frame.mid_term_strategy,
            immediate_goal=typed_active_goal_frame.immediate_goal,
            supporting_goals=list(typed_active_goal_frame.supporting_goals),
            blockers=list(typed_active_goal_frame.blockers),
            goal_sources=list(typed_active_goal_frame.goal_sources),
            urgency=typed_active_goal_frame.urgency,
            active_goal_frame=typed_active_goal_frame,
        )

    def build_suggestion_packet(
        self,
        *,
        interpretation: CharacterInterpretation,
        control_mode: str,
        snapshot: dict[str, object] | None = None,
        profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
    ) -> dict[str, object]:
        interpretation = self._normalize_interpretation(interpretation)
        normalized_snapshot = self._normalize_snapshot(snapshot)
        normalized_profile = self._normalize_profile(profile)
        normalized_memory_bundle = CharacterContextBuilder.normalize_memory_bundle(
            self._memory_bundle_mapping(memory_bundle)
        )
        plan = self.build_intent_plan(
            interpretation=interpretation,
            control_mode=control_mode,
            snapshot=normalized_snapshot,
            profile=normalized_profile,
            memory_bundle=normalized_memory_bundle,
            working_memory_state=working_memory_state,
        )
        relational_memories = self._list_entries(normalized_memory_bundle.get("relational_memories"))
        guarded_relation_note = self._guarded_relational_note(
            str(interpretation.attention_target or ""),
            relational_memories,
        )
        model_output = plan.get("model_output", {})
        active_goal_frame = plan.get("active_goal_frame", {})
        recommended = self._as_string_list(model_output.get("recommended_intents", []))
        if not recommended and str(normalized_snapshot.get("vigilance_level", "") or "") == "elevated":
            recommended = ["speak_public"]
        if (
            not recommended
            and isinstance(normalized_snapshot.get("recent_constraint_results"), list)
            and normalized_snapshot.get("recent_constraint_results")
        ):
            recommended = ["self_protect"]
        if not recommended:
            recommended = [
                self._map_candidate_to_intent(str(result["candidate"]))
                for result in plan["filter_results"]
                if result["viability"] in {"highly_compelling", "viable"}
            ]
        if (
            recommended
            and isinstance(normalized_snapshot.get("recent_world_changes"), list)
            and normalized_snapshot.get("recent_world_changes")
            and "speak_public" in recommended
        ):
            recommended = ["speak_public"] + [intent for intent in recommended if intent != "speak_public"]
        if (
            recommended
            and str(normalized_snapshot.get("vigilance_level", "") or "") == "elevated"
            and "speak_public" in recommended
        ):
            recommended = ["speak_public"] + [intent for intent in recommended if intent != "speak_public"]
        if not recommended:
            recommended = ["observe_target"]
        risk_notes = self._as_string_list(model_output.get("risk_notes", []))
        if not risk_notes and guarded_relation_note:
            risk_notes = [guarded_relation_note]
        if not risk_notes:
            risk_notes = [
                str(result["candidate"])
                for result in plan["filter_results"]
                if result["viability"] == "rejected"
            ]
        if not risk_notes and isinstance(normalized_snapshot.get("recent_constraint_results"), list):
            risk_notes = [str(item) for item in normalized_snapshot.get("recent_constraint_results", []) if str(item)]
        why_this_now = str(model_output.get("why_this_now", "") or "")
        if why_this_now == "" or why_this_now == interpretation.interpreted_summary:
            why_this_now = (
                self._recent_world_change_summary(normalized_snapshot)
                or self._recent_constraint_summary(normalized_snapshot)
                or guarded_relation_note
                or self._vigilance_summary(normalized_snapshot)
                or self._distraction_summary(normalized_snapshot)
                or interpretation.interpreted_summary
            )
        packet = CharacterSuggestionPacket(
            actor_id=interpretation.actor_id,
            control_mode="player_priority_assisted",
            producer_ts=0,
            causation_id="",
            correlation_id="",
            recommended_intents=recommended,
            risk_notes=risk_notes,
            primary_goal=str(active_goal_frame.get("primary_goal", "") or ""),
            long_term_goal=str(active_goal_frame.get("long_term_goal", "") or ""),
            mid_term_strategy=str(active_goal_frame.get("mid_term_strategy", "") or ""),
            supporting_goals=self._as_string_list(active_goal_frame.get("supporting_goals", [])),
            blockers=self._as_string_list(active_goal_frame.get("blockers", [])),
            goal_sources=self._as_string_list(active_goal_frame.get("goal_sources", [])),
            urgency=str(active_goal_frame.get("urgency", "low") or "low"),
            belief_cues=self._belief_cues(interpretation),
            higher_order_cues=self._higher_order_cues(interpretation),
            dynamic_pressure=self._dynamic_pressure_summary(interpretation),
            urge_vector="social_probe" if interpretation.attention_target else "hold",
            social_read=interpretation.interpretation_type,
            why_this_now=why_this_now,
            role_consistency_hint=str(
                model_output.get("role_consistency_hint", "")
                or interpretation.inner_prompt_candidate
                or self._recent_world_change_summary(normalized_snapshot)
                or self._recent_constraint_summary(normalized_snapshot)
                or guarded_relation_note
                or self._vigilance_summary(normalized_snapshot)
                or self._distraction_summary(normalized_snapshot)
                or interpretation.interpreted_summary
            ),
            reasoning_trace_summary=str(interpretation.reasoning_trace_summary or interpretation.inner_prompt_candidate or ""),
        )
        return packet.model_dump(exclude_none=True)

    def _generate_candidates(
        self,
        interpretation: CharacterInterpretation,
        control_mode: str,
    ) -> list[str]:
        candidates = ["observe", "inspect_object", "self_protect"]
        candidates.extend(["pause", "defer", "withhold"])
        if interpretation.attention_target:
            candidates.extend(
                [
                    "ask_probe",
                    "share_info",
                    "speak_private",
                    "follow_target",
                    "seek_private_distance",
                    "break_contact",
                    "withdraw",
                    "approach",
                ]
            )
        if interpretation.opportunity_level in {"medium", "high"}:
            candidates.append("speak_public")
        if control_mode == "player_priority_assisted":
            candidates.append("stay_silent")
        return candidates

    def _score_candidate(
        self,
        candidate: str,
        interpretation: CharacterInterpretation,
        *,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        control_mode: str,
        working_memory_state: dict[str, object],
        active_goal_tags: list[str],
    ) -> dict[str, object]:
        persona_ok, persona_notes = self._evaluate_persona(
            candidate,
            interpretation,
            memory_bundle=memory_bundle,
            profile=profile,
            working_memory_state=working_memory_state,
        )
        logic_ok, logic_notes = self._evaluate_logic(
            candidate,
            interpretation,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
            profile=profile,
            control_mode=control_mode,
            working_memory_state=working_memory_state,
        )
        gain_loss_score, gain_loss_notes = self._score_gain_loss(
            candidate,
            interpretation,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
            profile=profile,
            control_mode=control_mode,
            working_memory_state=working_memory_state,
        )
        return self._triple_filter.evaluate_candidate(
            candidate=candidate,
            persona_ok=persona_ok,
            logic_ok=logic_ok,
            gain_loss_score=gain_loss_score,
            persona_notes=persona_notes,
            logic_notes=logic_notes,
            gain_loss_notes=gain_loss_notes,
        )

    def _evaluate_persona(
        self,
        candidate: str,
        interpretation: CharacterInterpretation,
        *,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        working_memory_state: dict[str, object] | None = None,
    ) -> tuple[bool, list[str]]:
        notes: list[str] = []
        attention_target = str(interpretation.attention_target or "")
        conversation = self._dict_entry(profile.get("conversation_personality_layer"))
        privacy_sensitivity = self._as_float(conversation.get("privacy_sensitivity"), 0.5)
        talk_initiative = self._as_float(conversation.get("talk_initiative"), 0.5)
        trust_threshold = self._trust_threshold(profile)
        target_trust = self._social_trust_baseline(attention_target, memory_bundle)
        guarded_target = self._is_guarded_attention_target(attention_target, memory_bundle, profile)
        value_priorities = self._lowered_string_set(self._string_list(self._dict_entry(profile.get("virtue_value_layer")).get("value_priorities")))
        dynamic_state = self._dict_entry((working_memory_state or {}).get("dynamic_state"))
        masking_pressure = self._as_float(dynamic_state.get("masking_pressure"), 0.0)

        if candidate == "share_info":
            if attention_target == "":
                notes.append("share_info requires an attention target")
            if target_trust is not None and target_trust < trust_threshold:
                notes.append("target trust is below the profile private-talk threshold")
            if guarded_target and privacy_sensitivity >= 0.6:
                notes.append("privacy-sensitive profile avoids disclosure under guarded relations")
            if guarded_target and {"duty", "safety", "clarity"} & value_priorities:
                notes.append("value priorities favor containment over disclosure")
            if masking_pressure >= 0.7:
                notes.append("high masking pressure suppresses disclosure")
        elif candidate == "speak_public":
            if guarded_target and privacy_sensitivity >= 0.8:
                notes.append("privacy-sensitive profile avoids public escalation around guarded targets")
        elif candidate == "ask_probe":
            if attention_target and talk_initiative < 0.2 and interpretation.opportunity_level == "low":
                notes.append("low-initiative profile avoids probing without a clear opening")
        elif candidate == "speak_private":
            if attention_target == "":
                notes.append("speak_private requires an attention target")
            if target_trust is not None and target_trust < trust_threshold:
                notes.append("private speech requires sufficient trust")
        elif candidate == "approach":
            if guarded_target and {"safety", "duty"} & value_priorities:
                notes.append("guarded target blocks approach under protective values")
        elif candidate == "withhold":
            if masking_pressure < 0.3 and privacy_sensitivity < 0.5:
                notes.append("withhold is weak when concealment pressure is low")

        return not notes, notes

    def _evaluate_logic(
        self,
        candidate: str,
        interpretation: CharacterInterpretation,
        *,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        control_mode: str,
        working_memory_state: dict[str, object] | None = None,
    ) -> tuple[bool, list[str]]:
        notes: list[str] = []
        attention_target = str(interpretation.attention_target or "")
        recent_world_changes = self._as_string_list(snapshot.get("recent_world_changes", []))
        recent_constraint_results = self._as_string_list(snapshot.get("recent_constraint_results", []))
        vigilance_level = str(snapshot.get("vigilance_level", "") or "")
        guarded_target = self._is_guarded_attention_target(attention_target, memory_bundle, profile)
        has_target_memory_context = self._has_target_memory_context(attention_target, memory_bundle)
        interpretation_type = interpretation.interpretation_type

        if candidate == "inspect_object":
            if not (
                recent_world_changes
                or interpretation_type in {"state_change", "opportunity"}
                or attention_target.startswith("obj_")
                or attention_target.startswith("env_")
            ):
                notes.append("inspect_object requires a world-state cue or object-like target")
        elif candidate == "ask_probe":
            if attention_target == "":
                notes.append("ask_probe requires an attention target")
            elif not (interpretation_type in {"social_signal", "body_state"} or has_target_memory_context):
                notes.append("ask_probe requires social or remembered context around the target")
        elif candidate == "share_info":
            if attention_target == "":
                notes.append("share_info requires an attention target")
            elif not (interpretation_type == "social_signal" or has_target_memory_context):
                notes.append("share_info requires social context or remembered context about the target")
        elif candidate == "speak_public":
            if not (
                interpretation.opportunity_level in {"medium", "high"}
                or recent_world_changes
                or vigilance_level == "elevated"
            ):
                notes.append("speak_public requires a public opening or elevated vigilance")
        elif candidate == "self_protect":
            if not (
                interpretation.risk_level in {"medium", "high"}
                or recent_constraint_results
                or guarded_target
                or vigilance_level == "elevated"
            ):
                notes.append("self_protect requires elevated risk, constraints, or guarded context")
        elif candidate == "stay_silent":
            if not (control_mode == "player_priority_assisted" or interpretation.ambiguity_level != "low"):
                notes.append("stay_silent requires assisted control or unresolved ambiguity")
        elif candidate == "seek_private_distance":
            if attention_target == "":
                notes.append("seek_private_distance requires an attention target")
        elif candidate == "break_contact":
            if attention_target == "":
                notes.append("break_contact requires an attention target")
        elif candidate == "follow_target":
            if attention_target == "":
                notes.append("follow_target requires an attention target")
        elif candidate == "approach":
            if attention_target == "":
                notes.append("approach requires an attention target")
        elif candidate == "withdraw":
            if not (
                interpretation.risk_level in {"medium", "high"}
                or recent_constraint_results
                or guarded_target
                or interpretation.ambiguity_level != "low"
            ):
                notes.append("withdraw requires pressure, guarded context, or unresolved ambiguity")
        elif candidate == "pause":
            if not (interpretation.ambiguity_level != "low" or recent_constraint_results or guarded_target):
                notes.append("pause requires ambiguity, constraints, or guarded context")
        elif candidate == "defer":
            if not (
                interpretation.ambiguity_level != "low"
                or recent_constraint_results
                or recent_world_changes
                or guarded_target
            ):
                notes.append("defer requires unresolved pressure or evolving context")
        elif candidate == "withhold":
            if attention_target == "" and not has_target_memory_context:
                notes.append("withhold requires someone or something to withhold around")

        return not notes, notes

    def _score_gain_loss(
        self,
        candidate: str,
        interpretation: CharacterInterpretation,
        *,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        control_mode: str,
        working_memory_state: dict[str, object] | None = None,
        active_goal_tags: list[str] | None = None,
    ) -> tuple[float, list[str]]:
        notes: list[str] = []
        base_scores = {
            "observe": 0.78,
            "inspect_object": 0.42,
            "ask_probe": 0.56,
            "share_info": 0.48,
            "speak_public": 0.4,
            "self_protect": 0.45,
            "stay_silent": 0.35,
            "pause": 0.44,
            "defer": 0.46,
            "withhold": 0.52,
            "speak_private": 0.54,
            "follow_target": 0.49,
            "seek_private_distance": 0.57,
            "break_contact": 0.5,
            "withdraw": 0.51,
            "approach": 0.47,
        }
        score = base_scores.get(candidate, 0.3)
        attention_target = str(interpretation.attention_target or "")
        conversation = self._dict_entry(profile.get("conversation_personality_layer"))
        privacy_sensitivity = self._as_float(conversation.get("privacy_sensitivity"), 0.5)
        social_openness = self._as_float(conversation.get("social_openness"), 0.5)
        trust_threshold = self._trust_threshold(profile)
        target_trust = self._social_trust_baseline(attention_target, memory_bundle)
        guarded_target = self._is_guarded_attention_target(attention_target, memory_bundle, profile)
        recent_world_changes = self._as_string_list(snapshot.get("recent_world_changes", []))
        recent_constraint_results = self._as_string_list(snapshot.get("recent_constraint_results", []))
        vigilance_level = str(snapshot.get("vigilance_level", "") or "")
        value_priorities = self._lowered_string_set(self._string_list(self._dict_entry(profile.get("virtue_value_layer")).get("value_priorities")))
        dynamic_state = self._dict_entry((working_memory_state or {}).get("dynamic_state"))
        masking_pressure = self._as_float(dynamic_state.get("masking_pressure"), 0.0)
        higher_order_memories = self._higher_order_memory_records(memory_bundle)
        target_is_meta_suspicious = any(
            entry.subject_actor_id == attention_target
            for entry in higher_order_memories
        )
        goal_tags = set(active_goal_tags or [])
        target_knowledge_state = self._knowledge_state_for_target(attention_target, memory_bundle)
        ambient_knowledge_state = self._ambient_knowledge_state(memory_bundle)

        if candidate == "observe":
            if interpretation.ambiguity_level != "low":
                score += 0.05
                notes.append("observation preserves optionality under ambiguity")
        elif candidate == "inspect_object":
            if recent_world_changes or attention_target.startswith("obj_") or attention_target.startswith("env_"):
                score += 0.25
                notes.append("recent world-state changes make inspection useful")
            else:
                score -= 0.08
                notes.append("inspection has low value without an object-state cue")
        elif candidate == "ask_probe":
            if attention_target:
                score += 0.08
                notes.append("targeted probing can clarify the active social cue")
            if interpretation.interpretation_type == "social_signal":
                score += 0.07
                notes.append("social signal supports a probing response")
            if guarded_target:
                score -= 0.15
                notes.append("guarded target raises probing risk")
            if target_knowledge_state in {"suspected", "tentatively_believed"}:
                score += 0.16
                notes.append("uncertain target knowledge favors probing for confirmation")
        elif candidate == "share_info":
            if target_trust is not None and target_trust >= trust_threshold:
                score += 0.12
                notes.append("social trust clears the disclosure threshold")
            if interpretation.opportunity_level in {"medium", "high"} and social_openness >= 0.3:
                score += 0.08
                notes.append("current opening supports limited disclosure")
            if target_trust is not None and target_trust < trust_threshold:
                score -= 0.25
                notes.append("low trust makes disclosure costly")
            if guarded_target:
                score -= 0.2
                notes.append("guarded relation increases disclosure risk")
            if privacy_sensitivity >= 0.7:
                score -= 0.12
                notes.append("privacy sensitivity suppresses information sharing")
            if {"safety", "duty"} & value_priorities:
                score -= 0.06
                notes.append("value priorities favor controlled disclosure")
            if masking_pressure >= 0.7:
                score -= 0.3
                notes.append("masking pressure strongly suppresses disclosure")
            if target_is_meta_suspicious:
                score -= 0.14
                notes.append("target already suspects hidden knowledge, so disclosure grows riskier")
        elif candidate == "speak_public":
            if interpretation.opportunity_level in {"medium", "high"} or recent_world_changes or vigilance_level == "elevated":
                score += 0.18
                notes.append("the scene supports a public intervention")
            if guarded_target:
                score -= 0.18
                notes.append("guarded target makes public speech costly")
            if privacy_sensitivity >= 0.7:
                score -= 0.1
                notes.append("privacy sensitivity suppresses public exposure")
            if "clarity" in value_priorities and recent_world_changes:
                score += 0.06
                notes.append("clarity priority rewards making the change explicit")
            if ambient_knowledge_state == "disputed":
                score -= 0.18
                notes.append("disputed knowledge suppresses public commitment")
        elif candidate == "self_protect":
            if interpretation.risk_level in {"medium", "high"}:
                score += 0.3
                notes.append("risk level supports a protective response")
            if recent_constraint_results:
                score += 0.2
                notes.append("recent constraints justify a protective fallback")
            if guarded_target:
                score += 0.18
                notes.append("guarded relation increases the value of self-protection")
            if {"duty", "safety", "clarity"} & value_priorities:
                score += 0.08
                notes.append("value priorities reward protective containment")
            if "protect_self" in goal_tags:
                score += 0.12
                notes.append("active protect_self goal reinforces defensive action")
        elif candidate == "stay_silent":
            if control_mode == "player_priority_assisted":
                score += 0.12
                notes.append("assisted mode tolerates holding action")
            if privacy_sensitivity >= 0.7 or interpretation.ambiguity_level != "low":
                score += 0.08
                notes.append("silence reduces exposure while the read is incomplete")
        elif candidate == "pause":
            if interpretation.ambiguity_level != "low" or recent_constraint_results:
                score += 0.14
                notes.append("pause preserves optionality under pressure")
        elif candidate == "defer":
            if recent_constraint_results or recent_world_changes or interpretation.ambiguity_level != "low":
                score += 0.16
                notes.append("defer keeps the role from overcommitting too early")
            if ambient_knowledge_state == "disputed":
                score += 0.14
                notes.append("disputed knowledge makes deferral more valuable")
            if "preserve_optionality" in goal_tags:
                score += 0.12
                notes.append("active preserve_optionality goal rewards deferral")
        elif candidate == "withhold":
            if masking_pressure >= 0.6 or privacy_sensitivity >= 0.7:
                score += 0.18
                notes.append("concealment pressure supports withholding")
            if target_is_meta_suspicious:
                score += 0.16
                notes.append("higher-order suspicion increases the value of withholding")
            if "protect_secret" in goal_tags:
                score += 0.14
                notes.append("active protect_secret goal rewards withholding")
        elif candidate == "speak_private":
            if target_trust is not None and target_trust >= trust_threshold:
                score += 0.16
                notes.append("trust supports private disclosure or negotiation")
            if guarded_target:
                score -= 0.08
                notes.append("guarded context makes private speech cautious")
        elif candidate == "seek_private_distance":
            if guarded_target or privacy_sensitivity >= 0.7:
                score += 0.18
                notes.append("privacy pressure supports private spacing")
        elif candidate == "break_contact":
            if guarded_target or interpretation.risk_level in {"medium", "high"}:
                score += 0.16
                notes.append("risk or guarded context supports contact break")
        elif candidate == "withdraw":
            if guarded_target or interpretation.risk_level in {"medium", "high"}:
                score += 0.14
                notes.append("withdraw preserves safety under pressure")
        elif candidate == "approach":
            if interpretation.opportunity_level in {"medium", "high"} and not guarded_target:
                score += 0.14
                notes.append("approach is rewarded when the opening is real")
        elif candidate == "follow_target":
            if attention_target:
                score += 0.08
                notes.append("follow maintains pressure on a live target")

        if candidate == "ask_probe" and any(
            entry.subject_actor_id == attention_target
            for entry in higher_order_memories
        ):
            score += 0.09
            notes.append("higher-order memory strengthens probing relevance")

        return self._clamp(score), notes

    def _map_candidate_to_intent(self, candidate: str) -> str:
        mapping = {
            "observe": "observe",
            "inspect_object": "observe_target",
            "ask_probe": "ask_probe",
            "share_info": "share_info",
            "withhold": "observe_target",
            "pause": "observe_target",
            "defer": "observe_target",
            "speak_private": "share_info",
            "follow_target": "observe_target",
            "seek_private_distance": "observe_target",
            "break_contact": "physiology_hint",
            "withdraw": "physiology_hint",
            "approach": "observe_target",
            "speak_public": "speak_public",
            "self_protect": "physiology_hint",
            "stay_silent": "observe_target",
        }
        return mapping.get(candidate, "observe_target")

    def _is_guarded_attention_target(
        self,
        attention_target: str,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
    ) -> bool:
        if attention_target == "":
            return False
        relational_memories = self._list_entries(self._normalized_memory_bundle(memory_bundle).get("relational_memories"))
        if self._is_guarded_relational_target(attention_target, relational_memories):
            return True
        suspicion_baseline = self._social_suspicion_baseline(attention_target, memory_bundle)
        if suspicion_baseline is not None and suspicion_baseline >= 0.75:
            return True
        trust_baseline = self._social_trust_baseline(attention_target, memory_bundle)
        if trust_baseline is None:
            return False
        return trust_baseline < max(0.4, self._trust_threshold(profile) - 0.15)

    def _is_guarded_relational_target(self, attention_target: str, relational_memories: list[object]) -> bool:
        if attention_target == "":
            return False
        for entry in relational_memories:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("entity_id", "") or "") != attention_target:
                continue
            if str(entry.get("belief_type", "") or "") != "trust_level":
                continue
            if str(entry.get("value", "") or "") == "guarded":
                return True
        return False

    def _guarded_relational_note(self, attention_target: str, relational_memories: list[object]) -> str:
        if self._is_guarded_relational_target(attention_target, relational_memories):
            return f"guarded relation with {attention_target}"
        return ""

    def _merge_candidates(self, model_candidates: object, fallback_candidates: list[str]) -> list[str]:
        merged: list[str] = []
        if isinstance(model_candidates, list):
            for candidate in model_candidates:
                candidate_name = str(candidate)
                if candidate_name and candidate_name not in merged:
                    merged.append(candidate_name)
        for candidate in fallback_candidates:
            if candidate not in merged:
                merged.append(candidate)
        return merged

    def _filter_result_for_candidate(
        self,
        filter_results: list[dict[str, object]],
        candidate: str,
    ) -> dict[str, object] | None:
        for result in filter_results:
            if str(result.get("candidate", "") or "") == candidate:
                return result
        return None

    def _normalize_snapshot(self, snapshot: dict[str, object] | None) -> dict[str, object]:
        if not isinstance(snapshot, dict):
            return {}
        return dict(snapshot)

    def _normalize_profile(self, profile: dict[str, object] | None) -> dict[str, object]:
        if not isinstance(profile, dict):
            return {}
        return dict(profile)

    def _list_entries(self, value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        return [entry for entry in value if isinstance(entry, dict)]

    def _has_target_memory_context(
        self,
        attention_target: str,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
    ) -> bool:
        if attention_target == "":
            return False
        typed_memory_bundle = self._memory_record_bundle_model(memory_bundle)
        if any(entry.entity_id == attention_target for entry in typed_memory_bundle.social_memories):
            return True
        if any(
            attention_target in entry.refs
            for entry in typed_memory_bundle.event_memories
        ):
            return True
        if any(
            entry.observed_entity_id == attention_target or attention_target in entry.refs
            for entry in typed_memory_bundle.observation_memories
        ):
            return True
        if any(
            self._knowledge_record_references_attention_target(entry, attention_target)
            for entry in typed_memory_bundle.knowledge_memories
        ):
            return True
        if any(entry.subject_actor_id == attention_target for entry in typed_memory_bundle.higher_order_memories):
            return True
        normalized_memory_bundle = self._normalized_memory_bundle(memory_bundle)
        for key in ("episodic_memories", "relational_memories"):
            for entry in self._list_entries(normalized_memory_bundle.get(key)):
                if self._entry_references_attention_target(entry, attention_target):
                    return True
        return False

    def _knowledge_record_references_attention_target(
        self,
        entry: CharacterKnowledgeMemoryRecord,
        attention_target: str,
    ) -> bool:
        proposition_key = entry.proposition_key
        proposition = entry.proposition
        return proposition_key.startswith(f"{attention_target}:") or proposition.startswith(f"{attention_target}:")

    def _entry_references_attention_target(
        self,
        entry: dict[str, object],
        attention_target: str,
    ) -> bool:
        if str(entry.get("entity_id", "") or "") == attention_target:
            return True
        for key in (
            "target_actor_id",
            "target_object_id",
            "target_environment_id",
            "observed_entity_id",
            "focus_entity_id",
            "counterparty_id",
            "subject_actor_id",
        ):
            if str(entry.get(key, "") or "") == attention_target:
                return True
        proposition_key = str(entry.get("proposition_key", "") or "")
        if proposition_key.startswith("social:"):
            parts = proposition_key.split(":", 2)
            if len(parts) >= 3 and parts[1] == attention_target:
                return True
        return False

    def _social_trust_baseline(
        self,
        attention_target: str,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
    ) -> float | None:
        if attention_target == "":
            return None
        for entry in self._memory_record_bundle_model(memory_bundle).social_memories:
            if entry.entity_id != attention_target:
                continue
            return entry.trust_baseline
        return None

    def _social_suspicion_baseline(
        self,
        attention_target: str,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
    ) -> float | None:
        if attention_target == "":
            return None
        for entry in self._memory_record_bundle_model(memory_bundle).social_memories:
            if entry.entity_id != attention_target:
                continue
            return entry.suspicion_baseline
        return None

    def _knowledge_state_for_target(
        self,
        attention_target: str,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
    ) -> str | None:
        if attention_target == "":
            return None
        for entry in self._memory_record_bundle_model(memory_bundle).knowledge_memories:
            if entry.proposition_key.startswith(f"{attention_target}:"):
                return entry.state or None
        return None

    def _ambient_knowledge_state(
        self,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
    ) -> str | None:
        for entry in self._memory_record_bundle_model(memory_bundle).knowledge_memories:
            state = entry.state
            if state:
                return state
        return None

    def _trust_threshold(self, profile: dict[str, object]) -> float:
        conversation = self._dict_entry(profile.get("conversation_personality_layer"))
        return self._as_float(conversation.get("trust_threshold_for_private_talk"), 0.55)

    def _lowered_string_set(self, values: list[str]) -> set[str]:
        return {value.lower() for value in values if value}

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item)]

    def _dict_entry(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            return {}
        return value

    def _as_float(self, value: object, default: float) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        return default

    def _as_float_or_none(self, value: object) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def _clamp(self, value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def _as_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def _recent_world_change_summary(self, snapshot: dict[str, object] | None) -> str:
        if not isinstance(snapshot, dict):
            return ""
        value = snapshot.get("recent_world_changes", [])
        if not isinstance(value, list) or not value:
            return ""
        return str(value[-1] or "")

    def _recent_constraint_summary(self, snapshot: dict[str, object] | None) -> str:
        if not isinstance(snapshot, dict):
            return ""
        value = snapshot.get("recent_constraint_results", [])
        if not isinstance(value, list) or not value:
            return ""
        return str(value[-1] or "")

    def _vigilance_summary(self, snapshot: dict[str, object] | None) -> str:
        if not isinstance(snapshot, dict):
            return ""
        vigilance_level = str(snapshot.get("vigilance_level", "") or "")
        if vigilance_level == "elevated":
            return "heightened vigilance"
        return ""

    def _distraction_summary(self, snapshot: dict[str, object] | None) -> str:
        if not isinstance(snapshot, dict):
            return ""
        distraction_level = str(snapshot.get("distraction_level", "") or "")
        if distraction_level == "elevated":
            return "uncertain signal"
        return ""

    def _belief_cues(self, interpretation: CharacterInterpretation) -> list[str]:
        cues: list[str] = []
        for delta in interpretation.belief_deltas:
            if isinstance(delta, CharacterBeliefDelta):
                proposition_key = delta.proposition_key
                state = delta.state
            else:
                proposition_key = str(delta.get("proposition_key", "") or "")
                state = str(delta.get("state", "") or "")
            if proposition_key == "":
                continue
            cues.append(f"{proposition_key}={state}" if state else proposition_key)
        return cues

    def _active_goal_tags(
        self,
        *,
        interpretation: CharacterInterpretation,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        working_memory_state: dict[str, object],
    ) -> list[str]:
        tags: list[str] = []
        value_priorities = self._lowered_string_set(
            self._string_list(self._dict_entry(profile.get("virtue_value_layer")).get("value_priorities"))
        )
        dynamic_state = self._dict_entry(working_memory_state.get("dynamic_state"))
        masking_pressure = self._as_float(dynamic_state.get("masking_pressure"), 0.0)
        stress_load = self._as_float(dynamic_state.get("stress_load"), 0.0)
        motivation_stack = self._string_list(dynamic_state.get("motivation_stack"))
        ambient_knowledge_state = self._ambient_knowledge_state(memory_bundle)
        for item in interpretation.goal_hints:
            goal = self._goal_hint_goal(item)
            if goal != "":
                tags.append(goal)
        if {"safety", "duty"} & value_priorities or interpretation.risk_level in {"medium", "high"} or stress_load >= 0.6:
            tags.append("protect_self")
        if masking_pressure >= 0.6:
            tags.append("protect_secret")
        if ambient_knowledge_state in {"suspected", "tentatively_believed"}:
            tags.append("clarify_intent")
        if ambient_knowledge_state == "disputed" or interpretation.ambiguity_level != "low":
            tags.append("preserve_optionality")
        if "clarity" in value_priorities and isinstance(snapshot.get("recent_world_changes"), list) and snapshot.get("recent_world_changes"):
            tags.append("stabilize_situation")
        for item in motivation_stack:
            normalized = item.strip()
            if normalized != "":
                tags.append(normalized)
        deduped: list[str] = []
        for tag in tags:
            if tag not in deduped:
                deduped.append(tag)
        return deduped

    def _active_goal_frame(
        self,
        *,
        active_goal_tags: list[str],
        interpretation: CharacterInterpretation,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        working_memory_state: dict[str, object],
    ) -> CharacterActiveGoalFrame:
        value_priority_list = self._string_list(
            self._dict_entry(profile.get("virtue_value_layer")).get("value_priorities")
        )
        value_priorities = self._lowered_string_set(value_priority_list)
        dynamic_state = self._dict_entry(working_memory_state.get("dynamic_state"))
        masking_pressure = self._as_float(dynamic_state.get("masking_pressure"), 0.0)
        stress_load = self._as_float(dynamic_state.get("stress_load"), 0.0)
        motivation_stack = self._string_list(dynamic_state.get("motivation_stack"))
        blockers: list[str] = []
        if masking_pressure >= 0.7:
            blockers.append("high_masking_pressure")
        if stress_load >= 0.6:
            blockers.append("high_stress_load")
        if isinstance(snapshot.get("recent_constraint_results"), list) and snapshot.get("recent_constraint_results"):
            blockers.append("recent_constraint_pressure")
        ambient_knowledge_state = self._ambient_knowledge_state(memory_bundle)
        if ambient_knowledge_state == "disputed":
            blockers.append("disputed_knowledge")

        urgency = "low"
        if interpretation.risk_level in {"medium", "high"} or stress_load >= 0.6 or blockers:
            urgency = "high"
        elif interpretation.ambiguity_level != "low" or ambient_knowledge_state in {"suspected", "tentatively_believed"}:
            urgency = "medium"

        priority_order = [
            "protect_secret",
            "protect_self",
            "clarify_intent",
            "preserve_optionality",
            "stabilize_situation",
        ]
        primary_goal = "hold_position"
        strongest_goal_hint = self._strongest_goal_hint(interpretation.goal_hints)
        if strongest_goal_hint != "":
            primary_goal = strongest_goal_hint
        for goal in priority_order:
            if primary_goal == "hold_position" and goal in active_goal_tags:
                primary_goal = goal
                break
        if primary_goal == "hold_position" and active_goal_tags:
            primary_goal = active_goal_tags[0]
        long_term_goal = motivation_stack[0] if motivation_stack else ""
        if long_term_goal == "":
            if "clarity" in value_priorities:
                long_term_goal = "preserve_clarity"
            elif "safety" in value_priorities:
                long_term_goal = "preserve_safety"
            elif "duty" in value_priorities:
                long_term_goal = "fulfill_duty"
            elif value_priority_list:
                long_term_goal = f"uphold_{value_priority_list[0].strip().lower()}"
        supporting_goals = [goal for goal in active_goal_tags if goal != primary_goal]
        goal_sources: list[str] = []
        if motivation_stack or masking_pressure > 0.0 or stress_load > 0.0:
            goal_sources.append("dynamic_state")
        if ambient_knowledge_state is not None:
            goal_sources.append("knowledge_state")
        if value_priorities:
            goal_sources.append("profile_values")
        goal_sources.extend(self._goal_hint_sources(interpretation.goal_hints))
        deduped_sources: list[str] = []
        for source in goal_sources:
            if source not in deduped_sources:
                deduped_sources.append(source)
        return CharacterActiveGoalFrame(
            primary_goal=primary_goal,
            long_term_goal=long_term_goal,
            mid_term_strategy=self._derive_mid_term_strategy(
                primary_goal=primary_goal,
                blockers=blockers,
                interpretation=interpretation,
            ),
            immediate_goal=primary_goal,
            supporting_goals=supporting_goals,
            blockers=blockers,
            goal_sources=deduped_sources,
            urgency=urgency,
        )

    def _higher_order_cues(self, interpretation: CharacterInterpretation) -> list[str]:
        cues: list[str] = []
        for delta in interpretation.higher_order_deltas:
            if isinstance(delta, CharacterHigherOrderDelta):
                meta_belief = delta.meta_belief
            else:
                meta_belief = str(delta.get("meta_belief", "") or "")
            if meta_belief:
                cues.append(meta_belief)
        return cues

    def _dynamic_pressure_summary(self, interpretation: CharacterInterpretation) -> str:
        dynamic_state_delta = interpretation.dynamic_state_delta.as_mapping()
        if not dynamic_state_delta:
            return ""
        ordered_keys = ["vigilance_level", "distraction_level", "stress_load", "social_pressure", "masking_pressure"]
        parts: list[str] = []
        for key in ordered_keys:
            if key in dynamic_state_delta:
                parts.append(f"{key}={dynamic_state_delta[key]}")
        for key, value in dynamic_state_delta.items():
            if key in ordered_keys:
                continue
            parts.append(f"{key}={value}")
        return "|".join(parts)

    def _goal_hint_goal(self, value: object) -> str:
        if isinstance(value, CharacterGoalHint):
            return value.goal.strip()
        if isinstance(value, dict):
            return str(value.get("goal", "") or "").strip()
        return str(value or "").strip()

    def _goal_hint_sources(self, values: list[object]) -> list[str]:
        sources: list[str] = []
        for value in values:
            if isinstance(value, CharacterGoalHint):
                source = value.source.strip()
                if source:
                    sources.append(f"l2_goal_hint:{source}")
                    continue
            if isinstance(value, dict):
                source = str(value.get("source", "") or "").strip()
                if source:
                    sources.append(f"l2_goal_hint:{source}")
                    continue
            goal = self._goal_hint_goal(value)
            if goal:
                sources.append("l2_goal_hint")
        return sources

    def _strongest_goal_hint(self, values: list[object]) -> str:
        strongest_goal = ""
        strongest_strength = -1.0
        for value in values:
            if isinstance(value, CharacterGoalHint):
                goal = value.goal.strip()
                strength = value.strength
                if goal != "" and strength > strongest_strength:
                    strongest_goal = goal
                    strongest_strength = strength
                continue
            if not isinstance(value, dict):
                continue
            goal = str(value.get("goal", "") or "").strip()
            strength = float(value.get("strength", 0.0) or 0.0)
            if goal == "":
                continue
            if strength > strongest_strength:
                strongest_goal = goal
                strongest_strength = strength
        return strongest_goal

    def _normalize_interpretation(self, interpretation: CharacterInterpretation) -> CharacterInterpretation:
        normalized_belief_deltas = [self._belief_delta_model(item) for item in interpretation.belief_deltas]
        normalized_social_deltas = [self._social_delta_model(item) for item in interpretation.social_deltas]
        normalized_higher_order_deltas = [self._higher_order_delta_model(item) for item in interpretation.higher_order_deltas]
        normalized_goal_hints = [self._goal_hint_model(item) for item in interpretation.goal_hints]
        return CharacterInterpretation(
            actor_id=interpretation.actor_id,
            interpreted_summary=interpretation.interpreted_summary,
            interpretation_type=interpretation.interpretation_type,
            salience_score=interpretation.salience_score,
            ambiguity_level=interpretation.ambiguity_level,
            risk_level=interpretation.risk_level,
            opportunity_level=interpretation.opportunity_level,
            attention_target=interpretation.attention_target,
            inner_prompt_candidate=interpretation.inner_prompt_candidate,
            belief_deltas=normalized_belief_deltas,
            social_deltas=normalized_social_deltas,
            higher_order_deltas=normalized_higher_order_deltas,
            dynamic_state_delta=interpretation.dynamic_state_delta,
            goal_hints=normalized_goal_hints,
            reasoning_trace_summary=interpretation.reasoning_trace_summary,
        )

    def _belief_delta_model(self, value: object) -> CharacterBeliefDelta:
        if isinstance(value, CharacterBeliefDelta):
            return value
        if isinstance(value, dict):
            return CharacterBeliefDelta(
                proposition_key=str(value.get("proposition_key", "") or ""),
                proposition=str(value.get("proposition", "") or ""),
                state=str(value.get("state", "suspected") or "suspected"),
                confidence=float(value.get("confidence", 0.0) or 0.0),
            )
        return CharacterBeliefDelta(proposition_key=str(value or "").strip())

    def _social_delta_model(self, value: object) -> CharacterSocialDelta:
        if isinstance(value, CharacterSocialDelta):
            return value
        if isinstance(value, dict):
            return CharacterSocialDelta(
                entity_id=str(value.get("entity_id", "") or ""),
                trust_baseline=float(value.get("trust_baseline", 0.5) or 0.5),
                suspicion_baseline=float(value.get("suspicion_baseline", 0.0) or 0.0),
                intimacy=float(value.get("intimacy", 0.0) or 0.0),
                dependency=float(value.get("dependency", 0.0) or 0.0),
                unresolved_tension=float(value.get("unresolved_tension", 0.0) or 0.0),
                shared_secret_refs=[
                    str(ref)
                    for ref in value.get("shared_secret_refs", [])
                    if str(ref)
                ]
                if isinstance(value.get("shared_secret_refs", []), list)
                else [],
            )
        return CharacterSocialDelta(entity_id=str(value or "").strip())

    def _higher_order_delta_model(self, value: object) -> CharacterHigherOrderDelta:
        if isinstance(value, CharacterHigherOrderDelta):
            return value
        if isinstance(value, dict):
            return CharacterHigherOrderDelta(
                subject_actor_id=str(value.get("subject_actor_id", "") or ""),
                proposition_key=str(value.get("proposition_key", "") or ""),
                meta_belief=str(value.get("meta_belief", "") or ""),
                confidence=float(value.get("confidence", 0.0) or 0.0),
            )
        return CharacterHigherOrderDelta(subject_actor_id="", meta_belief=str(value or "").strip())

    def _goal_hint_model(self, value: object) -> CharacterGoalHint:
        if isinstance(value, CharacterGoalHint):
            return value
        if isinstance(value, dict):
            return CharacterGoalHint(
                goal=str(value.get("goal", "") or ""),
                source=str(value.get("source", "") or "model"),
                strength=float(value.get("strength", 0.5) or 0.5),
                evidence_tags=[
                    str(tag)
                    for tag in value.get("evidence_tags", [])
                    if str(tag)
                ]
                if isinstance(value.get("evidence_tags", []), list)
                else [],
            )
        return CharacterGoalHint(goal=str(value or "").strip(), source="model", strength=0.5, evidence_tags=[])

    def _derive_mid_term_strategy(
        self,
        *,
        primary_goal: str,
        blockers: list[str],
        interpretation: CharacterInterpretation,
    ) -> str:
        if primary_goal == "protect_secret":
            if blockers or interpretation.risk_level in {"medium", "high"}:
                return "contain_exposure"
            return "hold_information"
        if primary_goal == "protect_self":
            return "stabilize_self"
        if primary_goal == "clarify_intent":
            return "probe_safely"
        if primary_goal == "preserve_optionality":
            return "avoid_commitment"
        if primary_goal == "stabilize_situation":
            return "reestablish_control"
        return "hold_position"

    def _normalized_memory_bundle(
        self,
        value: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None,
    ) -> dict[str, list[dict[str, object]]]:
        return CharacterContextBuilder.normalize_memory_bundle(value)

    def _memory_record_bundle_model(
        self,
        value: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None,
    ) -> CharacterMemoryRecordBundle:
        if isinstance(value, CharacterMemoryRecordBundle):
            return value
        bundle = self._normalized_memory_bundle(value)
        return CharacterMemoryRecordBundle(
            event_memories=[self._event_memory_record_model(item) for item in bundle.get("event_memories", [])],
            observation_memories=[
                self._observation_memory_record_model(item) for item in bundle.get("observation_memories", [])
            ],
            knowledge_memories=[self._knowledge_memory_record_model(item) for item in bundle.get("knowledge_memories", [])],
            social_memories=[self._social_memory_record_model(item) for item in bundle.get("social_memories", [])],
            higher_order_memories=[
                self._higher_order_memory_record_model(item) for item in bundle.get("higher_order_memories", [])
            ],
        )

    def _event_memory_record_model(self, value: object) -> CharacterEventMemoryRecord:
        if isinstance(value, CharacterEventMemoryRecord):
            return value
        entry = self._dict_entry(value)
        return CharacterEventMemoryRecord(
            memory_id=str(entry.get("memory_id", "") or ""),
            actor_id=str(entry.get("actor_id", "") or ""),
            event_id=str(entry.get("event_id", "") or ""),
            source_event_id=str(entry.get("source_event_id", "") or ""),
            world_ts=int(entry.get("world_ts", 0) or 0),
            event_type=str(entry.get("event_type", "") or ""),
            summary=str(entry.get("summary", "") or ""),
            clarity_score=self._as_float(entry.get("clarity_score"), 0.0),
            certainty_score=self._as_float(entry.get("certainty_score"), 0.0),
            refs=self._as_string_list(entry.get("refs", [])),
        )

    def _observation_memory_record_model(self, value: object) -> CharacterObservationMemoryRecord:
        if isinstance(value, CharacterObservationMemoryRecord):
            return value
        entry = self._dict_entry(value)
        return CharacterObservationMemoryRecord(
            memory_id=str(entry.get("memory_id", "") or ""),
            actor_id=str(entry.get("actor_id", "") or ""),
            source_event_id=str(entry.get("source_event_id", "") or ""),
            world_ts=int(entry.get("world_ts", 0) or 0),
            observed_entity_id=str(entry.get("observed_entity_id", "") or ""),
            observation_type=str(entry.get("observation_type", "") or ""),
            observation_summary=str(entry.get("observation_summary", "") or ""),
            clarity_score=self._as_float(entry.get("clarity_score"), 0.0),
            certainty_score=self._as_float(entry.get("certainty_score"), 0.0),
            distortion_tags=self._as_string_list(entry.get("distortion_tags", [])),
            refs=self._as_string_list(entry.get("refs", [])),
        )

    def _knowledge_memory_record_model(self, value: object) -> CharacterKnowledgeMemoryRecord:
        if isinstance(value, CharacterKnowledgeMemoryRecord):
            return value
        entry = self._dict_entry(value)
        return CharacterKnowledgeMemoryRecord(
            memory_id=str(entry.get("memory_id", "") or ""),
            actor_id=str(entry.get("actor_id", "") or ""),
            proposition_key=str(entry.get("proposition_key", "") or ""),
            proposition=str(entry.get("proposition", "") or ""),
            state=str(entry.get("state", "") or ""),
            confidence=self._as_float(entry.get("confidence"), 0.0),
            source_event_id=str(entry.get("source_event_id", "") or ""),
            producer_ts=int(entry.get("producer_ts", 0) or 0),
        )

    def _social_memory_record_model(self, value: object) -> CharacterSocialMemoryRecord:
        if isinstance(value, CharacterSocialMemoryRecord):
            return value
        entry = self._dict_entry(value)
        return CharacterSocialMemoryRecord(
            memory_id=str(entry.get("memory_id", "") or ""),
            actor_id=str(entry.get("actor_id", "") or ""),
            entity_id=str(entry.get("entity_id", "") or ""),
            trust_baseline=self._as_float(entry.get("trust_baseline"), 0.0),
            suspicion_baseline=self._as_float(entry.get("suspicion_baseline"), 0.0),
            intimacy=self._as_float(entry.get("intimacy"), 0.0),
            dependency=self._as_float(entry.get("dependency"), 0.0),
            unresolved_tension=self._as_float(entry.get("unresolved_tension"), 0.0),
            shared_secret_refs=self._as_string_list(entry.get("shared_secret_refs", [])),
            source_event_id=str(entry.get("source_event_id", "") or ""),
            producer_ts=int(entry.get("producer_ts", 0) or 0),
        )

    def _higher_order_memory_record_model(self, value: object) -> CharacterHigherOrderMemoryRecord:
        if isinstance(value, CharacterHigherOrderMemoryRecord):
            return value
        entry = self._dict_entry(value)
        return CharacterHigherOrderMemoryRecord(
            memory_id=str(entry.get("memory_id", "") or ""),
            actor_id=str(entry.get("actor_id", "") or ""),
            subject_actor_id=str(entry.get("subject_actor_id", "") or ""),
            proposition_key=str(entry.get("proposition_key", "") or ""),
            meta_belief=str(entry.get("meta_belief", "") or ""),
            confidence=self._as_float(entry.get("confidence"), 0.0),
            source_event_id=str(entry.get("source_event_id", "") or ""),
            producer_ts=int(entry.get("producer_ts", 0) or 0),
        )

    def _higher_order_memory_records(
        self,
        value: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None,
    ) -> list[CharacterHigherOrderMemoryRecord]:
        return list(self._memory_record_bundle_model(value).higher_order_memories)

    def _working_memory_state_mapping(
        self,
        value: dict[str, object] | CharacterWorkingMemoryState | None,
    ) -> dict[str, object]:
        if isinstance(value, CharacterWorkingMemoryState):
            return value.model_dump()
        if isinstance(value, dict):
            return dict(value)
        return {}

    def _memory_bundle_mapping(
        self,
        value: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None,
    ) -> dict[str, list[dict[str, object]]]:
        if isinstance(value, CharacterMemoryRecordBundle):
            return {
                "event_memories": [item.model_dump() for item in value.event_memories],
                "observation_memories": [item.model_dump() for item in value.observation_memories],
                "knowledge_memories": [item.model_dump() for item in value.knowledge_memories],
                "social_memories": [item.model_dump() for item in value.social_memories],
                "higher_order_memories": [item.model_dump() for item in value.higher_order_memories],
            }
        if isinstance(value, dict):
            return dict(value)
        return {}
