from app.character_agent.gateway.context_builder import CharacterContextBuilder
from app.character_agent.models.cognition_delta import CharacterHigherOrderDelta
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.models.cognition_delta import CharacterBeliefDelta
from app.character_agent.models.cognition_delta import CharacterSocialDelta
from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.goal_runtime import CharacterGoalHint, CharacterGoalPortfolioEntry, CharacterGoalStateRecord
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
        effective_profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
        current_goal_state: dict[str, object] | CharacterGoalStateRecord | None = None,
        goal_state_history: list[dict[str, object] | CharacterGoalStateRecord] | None = None,
        supervision_state: dict[str, object] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        background_agenda_state: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        interpretation = self._normalize_interpretation(interpretation)
        normalized_snapshot = self._normalize_snapshot(snapshot)
        normalized_profile = self._normalize_profile(profile)
        normalized_effective_profile = self._normalize_profile(effective_profile) or normalized_profile
        typed_memory_bundle = self._memory_record_bundle_model(memory_bundle)
        normalized_memory_bundle = CharacterContextBuilder.normalize_memory_bundle(typed_memory_bundle)
        normalized_working_memory_state = self._working_memory_state_mapping(working_memory_state)
        normalized_need_tension_state = self._normalize_mapping(need_tension_state)
        normalized_dynamic_state = self._dynamic_state_mapping(
            dynamic_state,
            working_memory_state=normalized_working_memory_state,
        )
        normalized_current_goal_state = self._goal_state_mapping(
            current_goal_state,
            actor_id=interpretation.actor_id,
        )
        normalized_goal_state_history = self._goal_state_history_mappings(
            goal_state_history,
            actor_id=interpretation.actor_id,
        )
        normalized_supervision_state = self._normalize_mapping(supervision_state)
        normalized_unresolved_tensions = self._list_entries(unresolved_tensions)
        normalized_background_agenda_state = self._normalize_mapping(background_agenda_state)
        context_goal_tags = self._model_context_goal_tags(current_goal_state=normalized_current_goal_state)
        context_goal_frame = self._model_context_goal_frame(current_goal_state=normalized_current_goal_state)
        local_active_goal_tags = self._active_goal_tags(
            interpretation=interpretation,
            snapshot=normalized_snapshot,
            memory_bundle=typed_memory_bundle,
            profile=normalized_profile,
            working_memory_state=normalized_working_memory_state,
            current_goal_state=normalized_current_goal_state,
        )
        active_goal_frame = self._active_goal_frame(
            active_goal_tags=local_active_goal_tags,
            interpretation=interpretation,
            snapshot=normalized_snapshot,
            memory_bundle=typed_memory_bundle,
            profile=normalized_profile,
            working_memory_state=normalized_working_memory_state,
            current_goal_state=normalized_current_goal_state,
        )
        model_output = self._gateway.run_task(
            task_kind="l3_planning",
            context={
                "actor_id": interpretation.actor_id,
                "control_mode": control_mode,
                "interpretation": interpretation.model_dump(),
                "profile": normalized_profile,
                "effective_profile": normalized_effective_profile,
                "need_tension_state": normalized_need_tension_state,
                "dynamic_state": normalized_dynamic_state,
                "snapshot": normalized_snapshot,
                "memory": normalized_memory_bundle,
                "working_memory_state": normalized_working_memory_state,
                "active_goal_tags": context_goal_tags,
                "active_goal_frame": context_goal_frame.model_dump(),
                "current_goal_state": normalized_current_goal_state,
                "goal_state_history": normalized_goal_state_history,
                "supervision_state": normalized_supervision_state,
                "unresolved_tensions": normalized_unresolved_tensions,
                "background_agenda_state": normalized_background_agenda_state,
            },
        )
        candidates = self._model_owned_candidates(
            model_candidates=model_output.get("candidate_intents", []),
            local_affordances=self._generate_candidates(interpretation, control_mode),
        )
        active_goal_tags = self._model_owned_active_goal_tags(
            model_goal_tags=model_output.get("active_goal_tags", []),
            fallback_goal_tags=local_active_goal_tags,
        )
        active_goal_frame_payload = self._model_owned_active_goal_frame(
            model_goal_frame=model_output.get("active_goal_frame", {}),
            fallback_goal_frame=active_goal_frame,
        )
        filter_results = [
            self._score_candidate(
                candidate,
                interpretation,
                snapshot=normalized_snapshot,
                memory_bundle=typed_memory_bundle,
                profile=normalized_profile,
                effective_profile=normalized_effective_profile,
                control_mode=control_mode,
                working_memory_state=normalized_working_memory_state,
                need_tension_state=normalized_need_tension_state,
                dynamic_state=normalized_dynamic_state,
            )
            for candidate in candidates
        ]
        return {
            "actor_id": interpretation.actor_id,
            "control_mode": control_mode,
            "active_goal_tags": active_goal_tags,
            "active_goal_frame": active_goal_frame_payload.model_dump(),
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
        effective_profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
        current_goal_state: dict[str, object] | CharacterGoalStateRecord | None = None,
        goal_state_history: list[dict[str, object] | CharacterGoalStateRecord] | None = None,
        supervision_state: dict[str, object] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        background_agenda_state: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
    ) -> CharacterIntentDecision:
        plan = self.build_intent_plan(
            interpretation=interpretation,
            control_mode=control_mode,
            snapshot=snapshot,
            profile=profile,
            effective_profile=effective_profile,
            memory_bundle=memory_bundle,
            working_memory_state=working_memory_state,
            current_goal_state=current_goal_state,
            goal_state_history=goal_state_history,
            supervision_state=supervision_state,
            unresolved_tensions=unresolved_tensions,
            background_agenda_state=background_agenda_state,
            need_tension_state=need_tension_state,
            dynamic_state=dynamic_state,
        )
        model_selected_candidate = str(plan.get("model_output", {}).get("selected_intent", "") or "")
        model_recommended_candidates = self._as_string_list(plan.get("model_output", {}).get("recommended_intents", []))
        planning_status = str(plan.get("model_output", {}).get("planning_status", "") or "model")
        fallback_mode = str(plan.get("model_output", {}).get("fallback_mode", "") or "") or None
        chosen_candidate = self._select_model_owned_candidate(
            candidates=self._ordered_model_candidates(
                selected_candidate=model_selected_candidate,
                recommended_candidates=model_recommended_candidates,
            ),
            available_candidates=plan["candidates"],
            filter_results=plan["filter_results"],
        )
        if chosen_candidate == "":
            raise ValueError("model planning did not produce a locally valid candidate")
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
            dominant_goal_id=str(active_goal_frame.get("dominant_goal_id", "") or ""),
            preserved_goal_ids=self._as_string_list(active_goal_frame.get("preserved_goal_ids", [])),
            suppressed_goal_ids=self._as_string_list(active_goal_frame.get("suppressed_goal_ids", [])),
            goal_arbitration_summary=str(active_goal_frame.get("goal_arbitration_summary", "") or ""),
            goal_portfolio=self._goal_portfolio_entries(active_goal_frame.get("goal_portfolio", [])),
        )
        return CharacterIntentDecision(
            actor_id=interpretation.actor_id,
            selected_intent=self._map_candidate_to_intent(chosen_candidate),
            persona_passed=bool(selected_result and selected_result.get("persona_passed")),
            logic_passed=bool(selected_result and selected_result.get("logic_passed")),
            gain_loss_passed=gain_loss_score >= 0.5,
            rationale=str(plan.get("model_output", {}).get("why_this_now", "") or interpretation.interpreted_summary),
            primary_goal=typed_active_goal_frame.primary_goal,
            long_term_goal=typed_active_goal_frame.long_term_goal,
            mid_term_strategy=typed_active_goal_frame.mid_term_strategy,
            immediate_goal=typed_active_goal_frame.immediate_goal,
            supporting_goals=list(typed_active_goal_frame.supporting_goals),
            blockers=list(typed_active_goal_frame.blockers),
            goal_sources=list(typed_active_goal_frame.goal_sources),
            urgency=typed_active_goal_frame.urgency,
            active_goal_frame=typed_active_goal_frame,
            planning_status=planning_status if planning_status in {"model", "continuity_floor"} else "model",
            fallback_mode=fallback_mode,
        )

    def build_suggestion_packet(
        self,
        *,
        interpretation: CharacterInterpretation,
        control_mode: str,
        snapshot: dict[str, object] | None = None,
        profile: dict[str, object] | None = None,
        effective_profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
        current_goal_state: dict[str, object] | CharacterGoalStateRecord | None = None,
        goal_state_history: list[dict[str, object] | CharacterGoalStateRecord] | None = None,
        supervision_state: dict[str, object] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        background_agenda_state: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
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
            effective_profile=effective_profile,
            memory_bundle=normalized_memory_bundle,
            working_memory_state=working_memory_state,
            current_goal_state=current_goal_state,
            goal_state_history=goal_state_history,
            supervision_state=supervision_state,
            unresolved_tensions=unresolved_tensions,
            background_agenda_state=background_agenda_state,
            need_tension_state=need_tension_state,
            dynamic_state=dynamic_state,
        )
        relational_memories = self._list_entries(normalized_memory_bundle.get("relational_memories"))
        guarded_relation_note = self._guarded_relational_note(
            str(interpretation.attention_target or ""),
            relational_memories,
        )
        model_output = plan.get("model_output", {})
        active_goal_frame = plan.get("active_goal_frame", {})
        planning_status = str(model_output.get("planning_status", "") or "model")
        fallback_mode = str(model_output.get("fallback_mode", "") or "") or None
        recommended = self._valid_model_recommended_intents(
            model_output=model_output,
            available_candidates=plan["candidates"],
            filter_results=plan["filter_results"],
        )
        if planning_status == "continuity_floor" or not recommended:
            return self._continuity_floor_suggestion_packet(
                interpretation=interpretation,
                active_goal_frame=active_goal_frame,
                snapshot=normalized_snapshot,
                guarded_relation_note=guarded_relation_note,
            )
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
            planning_status=planning_status if planning_status in {"model", "continuity_floor"} else "model",
            fallback_mode=fallback_mode,
        )
        return packet.model_dump(exclude_none=True)

    def _valid_model_recommended_intents(
        self,
        *,
        model_output: dict[str, object],
        available_candidates: list[str],
        filter_results: list[dict[str, object]],
    ) -> list[str]:
        ordered_candidates = self._ordered_model_candidates(
            selected_candidate=str(model_output.get("selected_intent", "") or ""),
            recommended_candidates=self._as_string_list(model_output.get("recommended_intents", [])),
        )
        recommended: list[str] = []
        for candidate in ordered_candidates:
            if candidate == "":
                continue
            if candidate not in {str(item) for item in available_candidates}:
                continue
            result = self._filter_result_for_candidate(filter_results, candidate)
            if result is None or str(result.get("viability", "") or "") == "rejected":
                continue
            mapped = self._map_candidate_to_intent(candidate)
            if mapped not in recommended:
                recommended.append(mapped)
        return recommended

    def _model_owned_candidates(
        self,
        *,
        model_candidates: object,
        local_affordances: list[str],
    ) -> list[str]:
        candidate_list = [str(item) for item in model_candidates] if isinstance(model_candidates, list) else []
        deduped_model_candidates: list[str] = []
        for candidate in candidate_list:
            if candidate != "" and candidate not in deduped_model_candidates:
                deduped_model_candidates.append(candidate)
        if deduped_model_candidates:
            return deduped_model_candidates
        return local_affordances

    def _model_owned_active_goal_tags(
        self,
        *,
        model_goal_tags: object,
        fallback_goal_tags: list[str],
    ) -> list[str]:
        if not isinstance(model_goal_tags, list):
            return fallback_goal_tags
        normalized: list[str] = []
        for item in model_goal_tags:
            tag = str(item or "").strip()
            if tag != "" and tag not in normalized:
                normalized.append(tag)
        return normalized or fallback_goal_tags

    def _model_owned_active_goal_frame(
        self,
        *,
        model_goal_frame: object,
        fallback_goal_frame: CharacterActiveGoalFrame,
    ) -> CharacterActiveGoalFrame:
        if not isinstance(model_goal_frame, dict) or not model_goal_frame:
            return fallback_goal_frame
        primary_goal = str(model_goal_frame.get("primary_goal", "") or "")
        if primary_goal == "":
            return fallback_goal_frame
        return CharacterActiveGoalFrame(
            primary_goal=primary_goal,
            long_term_goal=str(model_goal_frame.get("long_term_goal", "") or ""),
            mid_term_strategy=str(model_goal_frame.get("mid_term_strategy", "") or ""),
            immediate_goal=str(model_goal_frame.get("immediate_goal", "") or primary_goal),
            supporting_goals=self._as_string_list(model_goal_frame.get("supporting_goals", [])),
            blockers=self._as_string_list(model_goal_frame.get("blockers", [])),
            goal_sources=self._as_string_list(model_goal_frame.get("goal_sources", [])),
            urgency=str(model_goal_frame.get("urgency", "low") or "low"),
            dominant_goal_id=str(model_goal_frame.get("dominant_goal_id", "") or ""),
            preserved_goal_ids=self._as_string_list(model_goal_frame.get("preserved_goal_ids", [])),
            suppressed_goal_ids=self._as_string_list(model_goal_frame.get("suppressed_goal_ids", [])),
            goal_arbitration_summary=str(model_goal_frame.get("goal_arbitration_summary", "") or ""),
            goal_portfolio=self._goal_portfolio_entries(model_goal_frame.get("goal_portfolio", [])),
        )

    def _model_context_goal_tags(self, *, current_goal_state: dict[str, object]) -> list[str]:
        if current_goal_state:
            tags: list[str] = []
            dominant_goal = str(current_goal_state.get("primary_goal", "") or "")
            if dominant_goal != "":
                tags.append(dominant_goal)
            for goal in self._as_string_list(current_goal_state.get("supporting_goals", [])):
                if goal not in tags:
                    tags.append(goal)
            for entry in self._goal_portfolio_dicts(current_goal_state.get("goal_portfolio", [])):
                goal = str(entry.get("goal", "") or "")
                if goal != "" and goal not in tags:
                    tags.append(goal)
            if tags:
                return tags
        return ["preserve_continuity"]

    def _model_context_goal_frame(self, *, current_goal_state: dict[str, object]) -> CharacterActiveGoalFrame:
        if current_goal_state and str(current_goal_state.get("primary_goal", "") or "") != "":
            return self._active_goal_frame_from_mapping(current_goal_state)
        return CharacterActiveGoalFrame(
            primary_goal="preserve_continuity",
            long_term_goal="preserve_continuity",
            mid_term_strategy="hold_position",
            immediate_goal="preserve_continuity",
            supporting_goals=[],
            blockers=[],
            goal_sources=["local_context_shell"],
            urgency="low",
            dominant_goal_id="goal_preserve_continuity",
            preserved_goal_ids=[],
            suppressed_goal_ids=[],
            goal_arbitration_summary="continuity shell active while no persisted goal state is available",
            goal_portfolio=[
                CharacterGoalPortfolioEntry(
                    goal_id="goal_preserve_continuity",
                    goal="preserve_continuity",
                    horizon="long",
                    status="active",
                    priority=0.5,
                    urgency="low",
                    source="local_context_shell",
                )
            ],
        )

    def _continuity_floor_suggestion_packet(
        self,
        *,
        interpretation: CharacterInterpretation,
        active_goal_frame: dict[str, object],
        snapshot: dict[str, object],
        guarded_relation_note: str,
    ) -> dict[str, object]:
        recommended_intent = self._continuity_floor_suggestion_intent(
            snapshot=snapshot,
            guarded_relation_note=guarded_relation_note,
        )
        why_this_now = (
            self._recent_constraint_summary(snapshot)
            or guarded_relation_note
            or self._vigilance_summary(snapshot)
            or self._distraction_summary(snapshot)
            or self._recent_world_change_summary(snapshot)
            or "model planning unavailable; continuity floor active"
        )
        role_consistency_hint = (
            guarded_relation_note
            or self._recent_constraint_summary(snapshot)
            or self._vigilance_summary(snapshot)
            or self._distraction_summary(snapshot)
            or "continuity floor"
        )
        packet = CharacterSuggestionPacket(
            actor_id=interpretation.actor_id,
            control_mode="player_priority_assisted",
            producer_ts=0,
            causation_id="",
            correlation_id="",
            recommended_intents=[recommended_intent],
            risk_notes=[note for note in [guarded_relation_note, self._recent_constraint_summary(snapshot)] if note != ""],
            primary_goal=str(active_goal_frame.get("primary_goal", "") or "preserve_continuity"),
            long_term_goal=str(active_goal_frame.get("long_term_goal", "") or "preserve_continuity"),
            mid_term_strategy=str(active_goal_frame.get("mid_term_strategy", "") or "hold_position"),
            supporting_goals=self._as_string_list(active_goal_frame.get("supporting_goals", [])),
            blockers=self._as_string_list(active_goal_frame.get("blockers", [])),
            goal_sources=self._as_string_list(active_goal_frame.get("goal_sources", [])) or ["continuity_floor"],
            urgency=str(active_goal_frame.get("urgency", "low") or "low"),
            belief_cues=self._belief_cues(interpretation),
            higher_order_cues=self._higher_order_cues(interpretation),
            dynamic_pressure=self._dynamic_pressure_summary(interpretation),
            urge_vector="preserve_continuity",
            social_read="continuity_floor",
            why_this_now=why_this_now,
            role_consistency_hint=role_consistency_hint,
            reasoning_trace_summary=str(interpretation.reasoning_trace_summary or "continuity_floor"),
            planning_status="continuity_floor",
            fallback_mode="continuity_floor",
        )
        return packet.model_dump(exclude_none=True)

    def _continuity_floor_suggestion_intent(
        self,
        *,
        snapshot: dict[str, object],
        guarded_relation_note: str,
    ) -> str:
        if guarded_relation_note != "":
            return "self_protect"
        if isinstance(snapshot.get("recent_constraint_results"), list) and snapshot.get("recent_constraint_results"):
            return "self_protect"
        return "stay_silent"

    def _ordered_model_candidates(
        self,
        *,
        selected_candidate: str,
        recommended_candidates: list[str],
    ) -> list[str]:
        ordered: list[str] = []
        if selected_candidate != "":
            ordered.append(selected_candidate)
        for candidate in recommended_candidates:
            if candidate != "" and candidate not in ordered:
                ordered.append(candidate)
        return ordered

    def _select_model_owned_candidate(
        self,
        *,
        candidates: list[str],
        available_candidates: list[str],
        filter_results: list[dict[str, object]],
    ) -> str:
        available = {str(candidate) for candidate in available_candidates}
        for candidate in candidates:
            if candidate not in available:
                continue
            result = self._filter_result_for_candidate(filter_results, candidate)
            if result is None:
                continue
            if str(result.get("viability", "") or "") == "rejected":
                continue
            return candidate
        return ""

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
        effective_profile: dict[str, object],
        control_mode: str,
        working_memory_state: dict[str, object],
        need_tension_state: dict[str, object],
        dynamic_state: dict[str, object],
    ) -> dict[str, object]:
        persona_ok = True
        persona_notes: list[str] = []
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
            effective_profile=effective_profile,
            control_mode=control_mode,
            working_memory_state=working_memory_state,
            need_tension_state=need_tension_state,
            dynamic_state=dynamic_state,
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
        _ = snapshot
        _ = interpretation
        _ = memory_bundle
        _ = profile
        _ = working_memory_state

        if candidate == "inspect_object":
            if not (attention_target.startswith("obj_") or attention_target.startswith("env_")):
                notes.append("inspect_object requires an object-like or environment-like target")
        elif candidate == "ask_probe":
            if attention_target == "":
                notes.append("ask_probe requires an attention target")
        elif candidate == "share_info":
            if attention_target == "":
                notes.append("share_info requires an attention target")
        elif candidate == "stay_silent":
            if control_mode != "player_priority_assisted":
                notes.append("stay_silent requires assisted control")
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
        elif candidate == "withhold":
            if attention_target == "":
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
        effective_profile: dict[str, object],
        control_mode: str,
        working_memory_state: dict[str, object] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
    ) -> tuple[float, list[str]]:
        _ = interpretation
        _ = snapshot
        _ = memory_bundle
        _ = profile
        _ = control_mode
        base_scores = {
            "observe": 0.6,
            "inspect_object": 0.42,
            "ask_probe": 0.5,
            "share_info": 0.5,
            "speak_public": 0.5,
            "self_protect": 0.45,
            "stay_silent": 0.35,
            "pause": 0.5,
            "defer": 0.5,
            "withhold": 0.5,
            "speak_private": 0.5,
            "follow_target": 0.5,
            "seek_private_distance": 0.5,
            "break_contact": 0.5,
            "withdraw": 0.5,
            "approach": 0.5,
        }
        score = base_scores.get(candidate, 0.3)
        notes: list[str] = []
        dynamic_signal = self._dynamic_state_mapping(dynamic_state, working_memory_state=working_memory_state)
        need_signal = self._normalize_mapping(need_tension_state)
        dominant_need = str(need_signal.get("dominant_need", "") or "")
        dominant_need_pressure = self._dominant_need_pressure(need_signal)
        if dominant_need_pressure <= 0.0:
            return self._clamp(score), []
        dominant_need_weight = self._need_weight(effective_profile or profile, dominant_need)
        stress_load = self._bounded_float(dynamic_signal.get("stress_load"))
        vigilance_level = self._bounded_float(dynamic_signal.get("vigilance_level"))
        social_pressure = self._bounded_float(dynamic_signal.get("social_pressure"))
        masking_pressure = self._bounded_float(dynamic_signal.get("masking_pressure"))
        protective_pressure = max(stress_load, vigilance_level, social_pressure, masking_pressure)

        if candidate == "self_protect":
            pressure_bias = (0.25 * dominant_need_pressure * dominant_need_weight) + (0.15 * protective_pressure)
            if pressure_bias > 0.0:
                score += pressure_bias
                notes.append("pressure_bias=self_protect")
        elif candidate in {"observe", "ask_probe", "share_info", "speak_public", "approach", "follow_target"}:
            pressure_penalty = (0.12 * dominant_need_pressure * dominant_need_weight) + (0.08 * protective_pressure)
            if pressure_penalty > 0.0:
                score -= pressure_penalty
                notes.append("pressure_penalty=exposure")

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

    def _normalize_mapping(self, value: dict[str, object] | None) -> dict[str, object]:
        if not isinstance(value, dict):
            return {}
        return dict(value)

    def _dynamic_state_mapping(
        self,
        value: dict[str, object] | None,
        *,
        working_memory_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if isinstance(value, dict) and value:
            return dict(value)
        if isinstance(working_memory_state, dict):
            dynamic_state = working_memory_state.get("dynamic_state")
            if isinstance(dynamic_state, dict):
                return dict(dynamic_state)
        return {}

    def _list_entries(self, value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        return [entry for entry in value if isinstance(entry, dict)]

    def _goal_portfolio_dicts(self, value: object) -> list[dict[str, object]]:
        return [entry.model_dump() for entry in self._goal_portfolio_entries(value)]

    def _goal_portfolio_entries(self, value: object) -> list[CharacterGoalPortfolioEntry]:
        if not isinstance(value, list):
            return []
        entries: list[CharacterGoalPortfolioEntry] = []
        for item in value:
            if isinstance(item, CharacterGoalPortfolioEntry):
                entries.append(item)
                continue
            if not isinstance(item, dict):
                continue
            goal_id = str(item.get("goal_id", "") or "")
            goal = str(item.get("goal", "") or "")
            source = str(item.get("source", "") or "model")
            if goal_id == "" or goal == "":
                continue
            entries.append(
                CharacterGoalPortfolioEntry(
                    goal_id=goal_id,
                    goal=goal,
                    horizon=str(item.get("horizon", "mid") or "mid"),
                    status=str(item.get("status", "active") or "active"),
                    priority=self._as_float(item.get("priority"), 0.5),
                    urgency=str(item.get("urgency", "low") or "low"),
                    source=source,
                    target_ref=str(item.get("target_ref", "") or ""),
                    blockers=self._as_string_list(item.get("blockers", [])),
                    supporting_evidence=self._as_string_list(item.get("supporting_evidence", [])),
                )
            )
        return entries

    def _goal_state_mapping(
        self,
        value: dict[str, object] | CharacterGoalStateRecord | None,
        *,
        actor_id: str,
    ) -> dict[str, object]:
        if isinstance(value, CharacterGoalStateRecord):
            payload = value.model_dump()
        elif isinstance(value, dict):
            payload = dict(value)
        else:
            return {}
        if str(payload.get("primary_goal", "") or "") == "":
            return {}
        payload.setdefault("actor_id", actor_id)
        return CharacterGoalStateRecord(
            actor_id=str(payload.get("actor_id", actor_id) or actor_id),
            primary_goal=str(payload.get("primary_goal", "") or ""),
            long_term_goal=str(payload.get("long_term_goal", "") or ""),
            mid_term_strategy=str(payload.get("mid_term_strategy", "") or ""),
            immediate_goal=str(payload.get("immediate_goal", "") or str(payload.get("primary_goal", "") or "")),
            supporting_goals=self._as_string_list(payload.get("supporting_goals", [])),
            blockers=self._as_string_list(payload.get("blockers", [])),
            goal_sources=self._as_string_list(payload.get("goal_sources", [])),
            urgency=str(payload.get("urgency", "low") or "low"),
            dominant_goal_id=str(payload.get("dominant_goal_id", "") or ""),
            preserved_goal_ids=self._as_string_list(payload.get("preserved_goal_ids", [])),
            suppressed_goal_ids=self._as_string_list(payload.get("suppressed_goal_ids", [])),
            goal_arbitration_summary=str(payload.get("goal_arbitration_summary", "") or ""),
            goal_portfolio=self._goal_portfolio_entries(payload.get("goal_portfolio", [])),
            transition_kind=str(payload.get("transition_kind", "initial") or "initial"),
            transition_reason_tags=self._as_string_list(payload.get("transition_reason_tags", [])),
        ).model_dump()

    def _goal_state_history_mappings(
        self,
        value: list[dict[str, object] | CharacterGoalStateRecord] | None,
        *,
        actor_id: str,
    ) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        for item in value or []:
            mapping = self._goal_state_mapping(item, actor_id=actor_id)
            if mapping:
                normalized.append(mapping)
        return normalized

    def _active_goal_frame_from_mapping(self, value: dict[str, object]) -> CharacterActiveGoalFrame:
        primary_goal = str(value.get("primary_goal", "") or "")
        return CharacterActiveGoalFrame(
            primary_goal=primary_goal,
            long_term_goal=str(value.get("long_term_goal", "") or ""),
            mid_term_strategy=str(value.get("mid_term_strategy", "") or ""),
            immediate_goal=str(value.get("immediate_goal", "") or primary_goal),
            supporting_goals=self._as_string_list(value.get("supporting_goals", [])),
            blockers=self._as_string_list(value.get("blockers", [])),
            goal_sources=self._as_string_list(value.get("goal_sources", [])),
            urgency=str(value.get("urgency", "low") or "low"),
            dominant_goal_id=str(value.get("dominant_goal_id", "") or ""),
            preserved_goal_ids=self._as_string_list(value.get("preserved_goal_ids", [])),
            suppressed_goal_ids=self._as_string_list(value.get("suppressed_goal_ids", [])),
            goal_arbitration_summary=str(value.get("goal_arbitration_summary", "") or ""),
            goal_portfolio=self._goal_portfolio_entries(value.get("goal_portfolio", [])),
        )

    def _dict_entry(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            return {}
        return value

    def _as_float(self, value: object, default: float) -> float:
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        return default

    def _bounded_float(self, value: object) -> float:
        return self._clamp(self._as_float(value, 0.0))

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

    def _need_weight(self, profile: dict[str, object], need_key: str) -> float:
        layer = profile.get("need_hierarchy_layer", {})
        if not isinstance(layer, dict):
            return 0.0
        weights = layer.get("effective_weights", layer.get("base_weights", {}))
        if not isinstance(weights, dict):
            return 0.0
        return self._bounded_float(weights.get(need_key))

    def _dominant_need_pressure(self, need_tension_state: dict[str, object]) -> float:
        dominant_need = str(need_tension_state.get("dominant_need", "") or "")
        if dominant_need == "":
            return 0.0
        return self._bounded_float(need_tension_state.get(f"{dominant_need}_pressure"))

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
        current_goal_state: dict[str, object],
    ) -> list[str]:
        _ = interpretation
        _ = memory_bundle
        _ = profile
        _ = working_memory_state
        _ = snapshot
        if current_goal_state:
            tags = self._model_context_goal_tags(current_goal_state=current_goal_state)
            if tags:
                return tags
        return ["preserve_continuity"]

    def _active_goal_frame(
        self,
        *,
        active_goal_tags: list[str],
        interpretation: CharacterInterpretation,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        profile: dict[str, object],
        working_memory_state: dict[str, object],
        current_goal_state: dict[str, object],
    ) -> CharacterActiveGoalFrame:
        if current_goal_state and str(current_goal_state.get("primary_goal", "") or "") != "":
            return self._active_goal_frame_from_mapping(current_goal_state)
        _ = memory_bundle
        _ = profile
        _ = working_memory_state
        primary_goal = "preserve_continuity"
        blockers: list[str] = []
        if isinstance(snapshot.get("recent_constraint_results"), list) and snapshot.get("recent_constraint_results"):
            blockers.append("recent_constraint_pressure")
        urgency = "high" if interpretation.risk_level in {"medium", "high"} or blockers else "low"
        long_term_goal = "preserve_continuity"
        supporting_goals: list[str] = []
        goal_sources = ["local_fallback"]
        mid_term_strategy = "hold_position"
        return CharacterActiveGoalFrame(
            primary_goal=primary_goal,
            long_term_goal=long_term_goal,
            mid_term_strategy=mid_term_strategy,
            immediate_goal=primary_goal,
            supporting_goals=supporting_goals,
            blockers=blockers,
            goal_sources=goal_sources,
            urgency=urgency,
            dominant_goal_id="goal_preserve_continuity",
            preserved_goal_ids=[],
            suppressed_goal_ids=[],
            goal_arbitration_summary="continuity floor shell keeps a single low-risk goal active",
            goal_portfolio=[
                CharacterGoalPortfolioEntry(
                    goal_id="goal_preserve_continuity",
                    goal="preserve_continuity",
                    horizon="long",
                    status="active",
                    priority=0.5,
                    urgency=urgency,
                    source="local_fallback",
                    blockers=blockers,
                    supporting_evidence=active_goal_tags,
                )
            ],
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
