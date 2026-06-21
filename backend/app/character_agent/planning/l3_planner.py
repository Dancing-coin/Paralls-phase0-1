from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation, CharacterSuggestionPacket
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.planning.triple_filter import CharacterTripleFilter


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
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
        working_memory_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        normalized_snapshot = snapshot or {}
        normalized_memory_bundle = memory_bundle or {
            "working_memory": [],
            "episodic_memories": [],
            "relational_memories": [],
        }
        relational_memories = []
        if isinstance(normalized_memory_bundle, dict):
            relational_candidate = normalized_memory_bundle.get("relational_memories", [])
            if isinstance(relational_candidate, list):
                relational_memories = relational_candidate
        effective_interpretation = interpretation
        if (
            interpretation.attention_target is None
            and isinstance(normalized_snapshot, dict)
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
        if (
            interpretation.attention_target
            and interpretation.risk_level == "low"
            and self._is_guarded_relational_target(str(interpretation.attention_target), relational_memories)
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
        if (
            interpretation.attention_target is None
            and isinstance(normalized_snapshot, dict)
            and (
                (isinstance(normalized_snapshot.get("recent_world_changes"), list) and normalized_snapshot.get("recent_world_changes"))
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
                "snapshot": normalized_snapshot,
                "memory": normalized_memory_bundle,
                "working_memory_state": working_memory_state or {},
            },
        )
        candidates = self._merge_candidates(
            model_output.get("candidate_intents", []),
            self._generate_candidates(effective_interpretation, control_mode),
        )
        filter_results = [self._score_candidate(candidate, effective_interpretation) for candidate in candidates]
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
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | None = None,
    ) -> CharacterIntentDecision:
        plan = self.build_intent_plan(
            interpretation=interpretation,
            control_mode=control_mode,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
            working_memory_state=working_memory_state,
        )
        model_selected_intent = str(plan.get("model_output", {}).get("selected_intent", "") or "")
        model_recommended_intents = self._as_string_list(plan.get("model_output", {}).get("recommended_intents", []))
        model_prefers_self_protect = (
            model_selected_intent == "self_protect"
            or (model_recommended_intents and model_recommended_intents[0] == "self_protect")
        )
        selected_intent = model_selected_intent or "observe_target"
        if not model_selected_intent and model_recommended_intents:
            selected_intent = model_recommended_intents[0]
        if not model_selected_intent and "speak_public" in plan["candidates"]:
            selected_intent = "speak_public"
        if model_selected_intent == "self_protect":
            return CharacterIntentDecision(
                actor_id=interpretation.actor_id,
                selected_intent="physiology_hint",
                persona_passed=True,
                logic_passed=True,
                gain_loss_passed=True,
                rationale=interpretation.interpreted_summary,
            )
        elif model_recommended_intents and model_recommended_intents[0] == "self_protect":
            return CharacterIntentDecision(
                actor_id=interpretation.actor_id,
                selected_intent="physiology_hint",
                persona_passed=True,
                logic_passed=True,
                gain_loss_passed=True,
                rationale=interpretation.interpreted_summary,
            )
        for result in plan["filter_results"]:
            candidate_name = str(result["candidate"])
            if candidate_name == model_selected_intent and result["viability"] != "rejected":
                selected_intent = candidate_name
                break
            if result["viability"] == "highly_compelling":
                selected_intent = self._map_candidate_to_intent(str(result["candidate"]))
                break
            if result["viability"] == "viable":
                if model_prefers_self_protect and candidate_name != "self_protect":
                    continue
                selected_intent = self._map_candidate_to_intent(str(result["candidate"]))
        return CharacterIntentDecision(
            actor_id=interpretation.actor_id,
            selected_intent=selected_intent,
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale=interpretation.interpreted_summary,
        )

    def build_suggestion_packet(
        self,
        *,
        interpretation: CharacterInterpretation,
        control_mode: str,
        snapshot: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
        working_memory_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        plan = self.build_intent_plan(
            interpretation=interpretation,
            control_mode=control_mode,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
            working_memory_state=working_memory_state,
        )
        relational_memories = []
        if isinstance(memory_bundle, dict):
            relational_candidate = memory_bundle.get("relational_memories", [])
            if isinstance(relational_candidate, list):
                relational_memories = relational_candidate
        guarded_relation_note = self._guarded_relational_note(
            str(interpretation.attention_target or ""),
            relational_memories,
        )
        model_output = plan.get("model_output", {})
        recommended = self._as_string_list(model_output.get("recommended_intents", []))
        if (
            not recommended
            and isinstance(snapshot, dict)
            and str(snapshot.get("vigilance_level", "") or "") == "elevated"
        ):
            recommended = ["speak_public"]
        if (
            not recommended
            and isinstance(snapshot, dict)
            and isinstance(snapshot.get("recent_constraint_results"), list)
            and snapshot.get("recent_constraint_results")
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
            and isinstance(snapshot, dict)
            and isinstance(snapshot.get("recent_world_changes"), list)
            and snapshot.get("recent_world_changes")
            and "speak_public" in recommended
        ):
            recommended = ["speak_public"] + [intent for intent in recommended if intent != "speak_public"]
        if (
            recommended
            and isinstance(snapshot, dict)
            and str(snapshot.get("vigilance_level", "") or "") == "elevated"
            and "speak_public" in recommended
        ):
            recommended = ["speak_public"] + [intent for intent in recommended if intent != "speak_public"]
        if not recommended:
            recommended = ["observe_target"]
        risk_notes = self._as_string_list(model_output.get("risk_notes", []))
        if not risk_notes:
            risk_notes = [
                str(result["candidate"])
                for result in plan["filter_results"]
                if result["viability"] == "rejected"
            ]
        if not risk_notes and guarded_relation_note:
            risk_notes = [guarded_relation_note]
        if (
            not risk_notes
            and isinstance(snapshot, dict)
            and isinstance(snapshot.get("recent_constraint_results"), list)
        ):
            risk_notes = [str(item) for item in snapshot.get("recent_constraint_results", []) if str(item)]
        why_this_now = str(model_output.get("why_this_now", "") or "")
        if why_this_now == "" or why_this_now == interpretation.interpreted_summary:
            why_this_now = (
                self._recent_world_change_summary(snapshot)
                or self._recent_constraint_summary(snapshot)
                or guarded_relation_note
                or self._vigilance_summary(snapshot)
                or self._distraction_summary(snapshot)
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
                or self._recent_world_change_summary(snapshot)
                or self._recent_constraint_summary(snapshot)
                or guarded_relation_note
                or self._vigilance_summary(snapshot)
                or self._distraction_summary(snapshot)
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
    ) -> dict[str, object]:
        persona_ok = True
        logic_ok = True
        gain_loss_score = 0.3
        if candidate == "observe":
            gain_loss_score = 0.85
        elif candidate == "ask_probe":
            gain_loss_score = 0.65
        elif candidate == "share_info":
            gain_loss_score = 0.55
        elif candidate == "speak_public":
            gain_loss_score = 0.6 if interpretation.opportunity_level in {"medium", "high"} else 0.2
        elif candidate == "self_protect":
            gain_loss_score = 0.7 if interpretation.risk_level in {"medium", "high"} else 0.25
        elif candidate == "stay_silent":
            gain_loss_score = 0.5
        return self._triple_filter.evaluate_candidate(
            candidate=candidate,
            persona_ok=persona_ok,
            logic_ok=logic_ok,
            gain_loss_score=gain_loss_score,
        )

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
