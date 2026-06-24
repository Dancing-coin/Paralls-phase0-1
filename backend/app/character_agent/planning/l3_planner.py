from app.character_agent.gateway.context_builder import CharacterContextBuilder
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.planning.triple_filter import CharacterTripleFilter
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
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
        working_memory_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        normalized_snapshot = self._normalize_snapshot(snapshot)
        normalized_profile = self._normalize_profile(profile)
        normalized_memory_bundle = CharacterContextBuilder.normalize_memory_bundle(memory_bundle)
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
                "working_memory_state": working_memory_state or {},
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
                memory_bundle=normalized_memory_bundle,
                profile=normalized_profile,
                control_mode=control_mode,
            )
            for candidate in candidates
        ]
        return {
            "actor_id": interpretation.actor_id,
            "control_mode": control_mode,
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
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | None = None,
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
        return CharacterIntentDecision(
            actor_id=interpretation.actor_id,
            selected_intent=self._map_candidate_to_intent(chosen_candidate),
            persona_passed=bool(selected_result and selected_result.get("persona_passed")),
            logic_passed=bool(selected_result and selected_result.get("logic_passed")),
            gain_loss_passed=gain_loss_score >= 0.5,
            rationale=interpretation.interpreted_summary,
        )

    def build_suggestion_packet(
        self,
        *,
        interpretation: CharacterInterpretation,
        control_mode: str,
        snapshot: dict[str, object] | None = None,
        profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
        working_memory_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        normalized_snapshot = self._normalize_snapshot(snapshot)
        normalized_profile = self._normalize_profile(profile)
        normalized_memory_bundle = CharacterContextBuilder.normalize_memory_bundle(memory_bundle)
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
        )
        return packet.model_dump(exclude_none=True)

    def _generate_candidates(
        self,
        interpretation: CharacterInterpretation,
        control_mode: str,
    ) -> list[str]:
        candidates = ["observe", "inspect_object", "self_protect"]
        if interpretation.attention_target:
            candidates.append("ask_probe")
            candidates.append("share_info")
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
        memory_bundle: dict[str, list[dict[str, object]]],
        profile: dict[str, object],
        control_mode: str,
    ) -> dict[str, object]:
        persona_ok, persona_notes = self._evaluate_persona(
            candidate,
            interpretation,
            memory_bundle=memory_bundle,
            profile=profile,
        )
        logic_ok, logic_notes = self._evaluate_logic(
            candidate,
            interpretation,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
            profile=profile,
            control_mode=control_mode,
        )
        gain_loss_score, gain_loss_notes = self._score_gain_loss(
            candidate,
            interpretation,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
            profile=profile,
            control_mode=control_mode,
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
        memory_bundle: dict[str, list[dict[str, object]]],
        profile: dict[str, object],
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

        if candidate == "share_info":
            if attention_target == "":
                notes.append("share_info requires an attention target")
            if target_trust is not None and target_trust < trust_threshold:
                notes.append("target trust is below the profile private-talk threshold")
            if guarded_target and privacy_sensitivity >= 0.6:
                notes.append("privacy-sensitive profile avoids disclosure under guarded relations")
            if guarded_target and {"duty", "safety", "clarity"} & value_priorities:
                notes.append("value priorities favor containment over disclosure")
        elif candidate == "speak_public":
            if guarded_target and privacy_sensitivity >= 0.8:
                notes.append("privacy-sensitive profile avoids public escalation around guarded targets")
        elif candidate == "ask_probe":
            if attention_target and talk_initiative < 0.2 and interpretation.opportunity_level == "low":
                notes.append("low-initiative profile avoids probing without a clear opening")

        return not notes, notes

    def _evaluate_logic(
        self,
        candidate: str,
        interpretation: CharacterInterpretation,
        *,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]],
        profile: dict[str, object],
        control_mode: str,
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

        return not notes, notes

    def _score_gain_loss(
        self,
        candidate: str,
        interpretation: CharacterInterpretation,
        *,
        snapshot: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]],
        profile: dict[str, object],
        control_mode: str,
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
        elif candidate == "stay_silent":
            if control_mode == "player_priority_assisted":
                score += 0.12
                notes.append("assisted mode tolerates holding action")
            if privacy_sensitivity >= 0.7 or interpretation.ambiguity_level != "low":
                score += 0.08
                notes.append("silence reduces exposure while the read is incomplete")

        return self._clamp(score), notes

    def _map_candidate_to_intent(self, candidate: str) -> str:
        mapping = {
            "observe": "observe",
            "inspect_object": "observe_target",
            "ask_probe": "ask_probe",
            "share_info": "share_info",
            "speak_public": "speak_public",
            "self_protect": "physiology_hint",
            "stay_silent": "observe_target",
        }
        return mapping.get(candidate, "observe_target")

    def _is_guarded_attention_target(
        self,
        attention_target: str,
        memory_bundle: dict[str, list[dict[str, object]]],
        profile: dict[str, object],
    ) -> bool:
        if attention_target == "":
            return False
        relational_memories = self._list_entries(memory_bundle.get("relational_memories"))
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
        memory_bundle: dict[str, list[dict[str, object]]],
    ) -> bool:
        if attention_target == "":
            return False
        for key in ("social_memories", "event_memories", "episodic_memories", "knowledge_memories", "relational_memories"):
            for entry in self._list_entries(memory_bundle.get(key)):
                if self._entry_references_attention_target(entry, attention_target):
                    return True
        return False

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
        memory_bundle: dict[str, list[dict[str, object]]],
    ) -> float | None:
        if attention_target == "":
            return None
        for entry in self._list_entries(memory_bundle.get("social_memories")):
            if str(entry.get("entity_id", "") or "") != attention_target:
                continue
            return self._as_float_or_none(entry.get("trust_baseline"))
        return None

    def _social_suspicion_baseline(
        self,
        attention_target: str,
        memory_bundle: dict[str, list[dict[str, object]]],
    ) -> float | None:
        if attention_target == "":
            return None
        for entry in self._list_entries(memory_bundle.get("social_memories")):
            if str(entry.get("entity_id", "") or "") != attention_target:
                continue
            return self._as_float_or_none(entry.get("suspicion_baseline"))
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
