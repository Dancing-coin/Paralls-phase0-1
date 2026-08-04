from __future__ import annotations

from app.character_agent.models.cognition_delta import CharacterDynamicStateDelta


class CharacterPromptPolicy:
    _MAX_VALUE_CHARS = 240
    _DYNAMIC_STATE_DELTA_FIELDS = tuple(CharacterDynamicStateDelta.model_fields)

    def build_prompt(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route: dict[str, str],
    ) -> dict[str, object]:
        actor_id = str(context.get("actor_id", "") or "")
        control_mode = str(context.get("control_mode", "") or "")
        return {
            "task_kind": task_kind,
            "system_instruction": self._system_instruction(task_kind=task_kind, route=route),
            "user_instruction": self._user_instruction(
                actor_id=actor_id,
                control_mode=control_mode,
                context=context,
            ),
            "required_output_keys": self._required_output_keys(task_kind),
            "response_format": "json_object",
        }

    def build_policy(
        self,
        *,
        task_kind: str,
        route: dict[str, str],
    ) -> dict[str, object]:
        provider_kind = str(route.get("provider_kind", "") or "")
        return {
            "allow_model_call": provider_kind != "local",
            "fallback_mode": "local" if provider_kind == "local" else "hybrid",
            "provider_kind": provider_kind,
            "task_kind": task_kind,
            "temperature": 0.2 if task_kind == "dialogue_generation" else 0.1,
            "max_tokens": {
                "dialogue_generation": 400,
                "l2_reasoning": 1200,
                "l3_planning": 1800,
            }[task_kind],
        }

    def _system_instruction(self, *, task_kind: str, route: dict[str, str]) -> str:
        route_mode = str(route.get("route_mode", "") or "online_default")
        if task_kind == "dialogue_generation":
            return (
                f"CharacterAgent {task_kind} on {route_mode}: return one JSON object with keys "
                '["content", "tone"] and no extra text.'
            )
        if task_kind == "l3_planning":
            return (
                f"CharacterAgent {task_kind} on {route_mode}: return one JSON object with keys "
                '["candidate_intents", "selected_intent", "recommended_intents", "risk_notes", '
                '"why_this_now", "role_consistency_hint", "active_goal_tags", "active_goal_frame", '
                '"planning_status", "fallback_mode"] and no extra text. '
                'candidate_intents must be a non-empty list of strings. selected_intent must be one of candidate_intents. '
                'recommended_intents must be a non-empty list of strings and must include selected_intent. '
                'active_goal_tags must be a list of strings. '
                'active_goal_frame must be an object with keys '
                '["primary_goal", "long_term_goal", "mid_term_strategy", "immediate_goal", '
                '"supporting_goals", "blockers", "goal_sources", "urgency", "dominant_goal_id", '
                '"preserved_goal_ids", "suppressed_goal_ids", "goal_arbitration_summary", "goal_portfolio"]. '
                'goal_portfolio must be a list of goal objects and should preserve multiple concurrent motives, not only the dominant goal. '
                'planning_status must be "model" on live success. fallback_mode must be JSON null on live success. '
                'active_goal_frame.primary_goal cannot be empty. '
                'active_goal_frame.urgency and each goal_portfolio urgency must be exactly one of "low", "medium", or "high"; do not use numbers.'
            )
        allowed_dynamic_state_fields = ", ".join(
            f'"{field_name}"' for field_name in self._DYNAMIC_STATE_DELTA_FIELDS
        )
        return (
            f"CharacterAgent {task_kind} on {route_mode}: return one JSON object with keys "
            '["interpreted_summary", "interpretation_type", "salience_score", '
            '"ambiguity_level", "risk_level", "opportunity_level", "attention_target", '
            '"inner_prompt_candidate", "belief_deltas", "social_deltas", '
            '"higher_order_deltas", "dynamic_state_delta", "goal_hints", "reasoning_trace_summary"] and no extra text. '
            'salience_score must be a JSON number from 0.0 to 1.0. '
            'ambiguity_level, risk_level, and opportunity_level must each be exactly one of "low", "medium", or "high"; do not use "moderate" or numbers. '
            'All confidence, strength, trust, suspicion, intimacy, dependency, unresolved_tension, and dynamic_state_delta values must be JSON numbers from 0.0 to 1.0, not words. '
            f'dynamic_state_delta may contain only [{allowed_dynamic_state_fields}]. '
            'Do not emit any other dynamic_state_delta key; use {} when no allowed delta applies. '
            'goal_hints must be a list of objects with keys ["goal", "source", "strength", "evidence_tags"].'
        )

    def _user_instruction(
        self,
        *,
        actor_id: str,
        control_mode: str,
        context: dict[str, object],
    ) -> str:
        profile = context.get("profile", {})
        effective_profile = context.get("effective_profile", profile)
        need_tension_state = context.get("need_tension_state", {})
        snapshot = context.get("snapshot", {})
        memory = context.get("memory", {})
        working_memory_state = context.get("working_memory_state", {})
        event = context.get("event", {})
        current_goal_state = context.get("current_goal_state", {})
        goal_state_history = context.get("goal_state_history", {})
        supervision_state = context.get("supervision_state", {})
        unresolved_tensions = context.get("unresolved_tensions", {})
        background_agenda_state = context.get("background_agenda_state", {})
        profile_summary = self._profile_summary(profile if isinstance(profile, dict) else {})
        effective_profile_summary = self._profile_summary(
            effective_profile if isinstance(effective_profile, dict) else {}
        )
        need_tension_state_summary = self._need_tension_state_summary(
            need_tension_state if isinstance(need_tension_state, dict) else {}
        )
        snapshot_summary = self._snapshot_summary(snapshot if isinstance(snapshot, dict) else {})
        memory_summary = self._memory_summary(memory if isinstance(memory, dict) else {})
        working_memory_state_summary = self._working_memory_state_summary(
            working_memory_state if isinstance(working_memory_state, dict) else {}
        )
        event_summary = self._event_summary(event if isinstance(event, dict) else {})
        current_goal_state_summary = self._goal_state_summary(
            current_goal_state if isinstance(current_goal_state, dict) else {}
        )
        goal_state_history_summary = self._goal_state_history_summary(goal_state_history)
        supervision_state_summary = self._supervision_state_summary(
            supervision_state if isinstance(supervision_state, dict) else {}
        )
        unresolved_tension_summary = self._unresolved_tension_summary(unresolved_tensions)
        background_agenda_summary = self._background_agenda_summary(
            background_agenda_state if isinstance(background_agenda_state, dict) else {}
        )
        return (
            f"actor_id={actor_id}; control_mode={control_mode}; "
            f"profile_summary={profile_summary}; "
            f"effective_profile_summary={effective_profile_summary}; "
            f"need_tension_state={need_tension_state_summary}; "
            f"snapshot={snapshot_summary}; memory={memory_summary}; "
            f"working_memory_state={working_memory_state_summary}; "
            f"current_goal_state={current_goal_state_summary}; "
            f"goal_state_history={goal_state_history_summary}; "
            f"supervision_state={supervision_state_summary}; "
            f"unresolved_tensions={unresolved_tension_summary}; "
            f"background_agenda_state={background_agenda_summary}; "
            f"event_summary={event_summary}"
        )

    def _required_output_keys(self, task_kind: str) -> list[str]:
        if task_kind == "dialogue_generation":
            return [
                "content",
                "tone",
            ]
        if task_kind == "l3_planning":
            return [
                "candidate_intents",
                "selected_intent",
                "recommended_intents",
                "risk_notes",
                "why_this_now",
                "role_consistency_hint",
                "active_goal_tags",
                "active_goal_frame",
                "planning_status",
                "fallback_mode",
            ]
        return [
            "interpreted_summary",
            "interpretation_type",
            "salience_score",
            "ambiguity_level",
            "risk_level",
            "opportunity_level",
            "attention_target",
            "inner_prompt_candidate",
            "belief_deltas",
            "social_deltas",
            "higher_order_deltas",
            "dynamic_state_delta",
            "goal_hints",
            "reasoning_trace_summary",
        ]

    def _profile_summary(self, profile: dict[str, object]) -> str:
        identity_core = profile.get("identity_core", {})
        if not isinstance(identity_core, dict):
            identity_core = {}
        trait_vector = profile.get("trait_vector_layer", {})
        if not isinstance(trait_vector, dict):
            trait_vector = {}
        virtue_value_layer = profile.get("virtue_value_layer", {})
        if not isinstance(virtue_value_layer, dict):
            virtue_value_layer = {}
        capability_constraint_layer = profile.get("capability_constraint_layer", {})
        if not isinstance(capability_constraint_layer, dict):
            capability_constraint_layer = {}
        conversation_personality_layer = profile.get("conversation_personality_layer", {})
        if not isinstance(conversation_personality_layer, dict):
            conversation_personality_layer = {}
        personality_projection = profile.get("personality_projection", {})
        if not isinstance(personality_projection, dict):
            personality_projection = {}
        need_hierarchy_layer = profile.get("need_hierarchy_layer", {})
        if not isinstance(need_hierarchy_layer, dict):
            need_hierarchy_layer = {}
        return "; ".join(
            [
                f"character_id={self._truncate(identity_core.get('character_id', ''))}",
                f"canonical_name={self._truncate(identity_core.get('canonical_name', ''))}",
                f"occupation_role={self._truncate(identity_core.get('occupation_role', ''))}",
                f"need_weights={self._need_weight_summary(need_hierarchy_layer)}",
                f"personality_projection={self._personality_projection_summary(personality_projection)}",
                f"legacy_traits={self._trait_summary(trait_vector)}",
                f"value_priorities={self._join_list(virtue_value_layer.get('value_priorities'))}",
                f"red_lines={self._join_list(virtue_value_layer.get('red_lines'))}",
                f"forbidden_behaviors={self._join_list(virtue_value_layer.get('forbidden_behaviors'))}",
                f"skills={self._join_list(capability_constraint_layer.get('skills'))}",
                f"knowledge_domains={self._join_list(capability_constraint_layer.get('knowledge_domains'))}",
                f"social_constraints={self._join_list(capability_constraint_layer.get('social_constraints'))}",
                f"social_openness={self._scalar_summary(conversation_personality_layer.get('social_openness'))}",
                f"privacy_sensitivity={self._scalar_summary(conversation_personality_layer.get('privacy_sensitivity'))}",
                f"talk_initiative={self._scalar_summary(conversation_personality_layer.get('talk_initiative'))}",
                f"deception_control={self._scalar_summary(conversation_personality_layer.get('deception_control'))}",
                f"trust_threshold_for_private_talk={self._scalar_summary(conversation_personality_layer.get('trust_threshold_for_private_talk'))}",
            ]
        )

    def _need_weight_summary(self, layer: dict[str, object]) -> str:
        if not layer:
            return ""
        weights = layer.get("effective_weights", layer.get("base_weights", {}))
        if not isinstance(weights, dict) or not weights:
            return ""
        return self._truncate(
            "|".join(
                f"{key}={weights[key]}"
                for key in sorted(weights)
            )
        )

    def _need_tension_state_summary(self, state: dict[str, object]) -> str:
        if not state:
            return ""
        dominant_need = self._truncate(state.get("dominant_need", "") or "")
        secondary_need = self._truncate(state.get("secondary_need", "") or "")
        motivation_stack = self._join_list(state.get("motivation_stack"))
        pressure_sources = self._join_list(state.get("pressure_sources"))
        pressure_magnitudes = self._pressure_magnitude_summary(state)
        return "; ".join(
            [
                f"dominant_need={dominant_need}",
                f"secondary_need={secondary_need}",
                f"motivation_stack={motivation_stack}",
                f"pressure_sources={pressure_sources}",
                f"pressure_magnitudes={pressure_magnitudes}",
            ]
        )

    def _pressure_magnitude_summary(self, state: dict[str, object]) -> str:
        ordered_keys = (
            ("physiological", "physiological_pressure"),
            ("safety", "safety_pressure"),
            ("belonging", "belonging_pressure"),
            ("esteem", "esteem_pressure"),
            ("self_actualization", "self_actualization_pressure"),
        )
        pairs: list[str] = []
        for label, key in ordered_keys:
            value = state.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) and float(value) > 0.0:
                pairs.append(f"{label}={value}")
        return self._truncate("|".join(pairs))

    def _trait_summary(self, trait_vector: dict[str, object]) -> str:
        if not trait_vector:
            return ""
        trait_order = (
            "courage",
            "scheming",
            "empathy",
            "rationality",
            "sociability",
        )
        return "|".join(
            f"{name}={self._scalar_summary(trait_vector.get(name))}"
            for name in trait_order
            if name in trait_vector
        )

    def _personality_projection_summary(self, projection: dict[str, object]) -> str:
        if not projection:
            return ""
        projection_order = (
            "conflict_deescalation_bias",
            "procedural_discipline",
            "stress_vulnerability",
        )
        return "|".join(
            f"{name}={self._scalar_summary(projection.get(name))}"
            for name in projection_order
            if name in projection
        )

    def _join_list(self, value: object) -> str:
        if not isinstance(value, list):
            return ""
        return self._truncate("|".join(str(item) for item in value if str(item)))

    def _scalar_summary(self, value: object) -> str:
        if isinstance(value, (int, float)):
            return str(value)
        return self._truncate(value)

    def _snapshot_summary(self, snapshot: dict[str, object]) -> str:
        return "; ".join(
            [
                f"visible_entities_count={self._count_of(snapshot.get('visible_entities'))}",
                f"audible_entities_count={self._count_of(snapshot.get('audible_entities'))}",
                f"attention_targets_count={self._count_of(snapshot.get('attention_targets'))}",
                f"focus_target={self._truncate(snapshot.get('current_focus_target') or snapshot.get('attention_target') or '')}",
                f"last_siming_catalyst={self._truncate(snapshot.get('last_siming_catalyst', '') or '')}",
                f"vigilance_level={self._truncate(snapshot.get('vigilance_level', '') or '')}",
                f"body_state_hints_count={self._count_of(snapshot.get('body_state_hints'))}",
                f"recent_world_changes_count={self._count_of(snapshot.get('recent_world_changes'))}",
                f"recent_constraint_results_count={self._count_of(snapshot.get('recent_constraint_results'))}",
                f"recent_world_change_sample={self._sample_summary(snapshot.get('recent_world_changes'))}",
                f"recent_constraint_result_sample={self._sample_summary(snapshot.get('recent_constraint_results'))}",
            ]
        )

    def _memory_summary(self, memory: dict[str, object]) -> str:
        return "; ".join(
            [
                f"working_memory_count={self._count_of(memory.get('working_memory'))}",
                f"event_memories_count={self._count_of(memory.get('event_memories'))}",
                f"observation_memories_count={self._count_of(memory.get('observation_memories'))}",
                f"knowledge_memories_count={self._count_of(memory.get('knowledge_memories'))}",
                f"social_memories_count={self._count_of(memory.get('social_memories'))}",
                f"higher_order_memories_count={self._count_of(memory.get('higher_order_memories'))}",
                f"working_memory_sample={self._sample_summary(memory.get('working_memory'))}",
                f"event_memory_sample={self._sample_summary(memory.get('event_memories'))}",
                f"observation_memory_sample={self._sample_summary(memory.get('observation_memories'))}",
                f"relational_memory_sample={self._sample_summary(memory.get('relational_memories'))}",
                f"knowledge_memory_sample={self._sample_summary(memory.get('knowledge_memories'))}",
                f"social_memory_sample={self._sample_summary(memory.get('social_memories'))}",
                f"higher_order_memory_sample={self._sample_summary(memory.get('higher_order_memories'))}",
            ]
        )

    def _working_memory_state_summary(self, state: dict[str, object]) -> str:
        return "; ".join(
            [
                f"recent_perceived_events_count={self._count_of(state.get('recent_perceived_events'))}",
                f"recent_esm_results_count={self._count_of(state.get('recent_esm_results'))}",
                f"recent_siming_catalysts_count={self._count_of(state.get('recent_siming_catalysts'))}",
                f"private_snapshot_actor_id={self._truncate(self._nested_value(state.get('private_snapshot'), 'actor_id'))}",
                f"dynamic_state_summary={self._dynamic_state_summary(state.get('dynamic_state'))}",
            ]
        )

    def _dynamic_state_summary(self, value: object) -> str:
        if not isinstance(value, dict) or not value:
            return ""
        ordered_keys = [
            "vigilance_level",
            "distraction_level",
            "stress_load",
            "social_pressure",
            "masking_pressure",
        ]
        pairs: list[str] = []
        for key in ordered_keys:
            if key in value:
                pairs.append(f"{key}={self._truncate(value.get(key, ''))}")
        affect_state = value.get("affect_state")
        if isinstance(affect_state, dict) and affect_state:
            affect_summary = self._affect_state_summary(affect_state)
            if affect_summary:
                pairs.append(f"affect_state={affect_summary}")
        for key, item in value.items():
            if key in ordered_keys or key in {"affect_state", "tension_state", "motivation_state"}:
                continue
            pairs.append(f"{key}={self._truncate(item)}")
        return self._truncate("|".join(pairs))

    def _affect_state_summary(self, state: dict[str, object]) -> str:
        ordered_keys = (
            "fear",
            "anger",
            "shame",
            "sadness",
            "relief",
            "curiosity",
            "affection",
            "joy",
            "calm",
            "trust",
            "gratitude",
            "pride",
            "confidence",
            "hope",
        )
        pairs: list[str] = []
        for key in ordered_keys:
            value = state.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) and float(value) > 0.0:
                pairs.append(f"{key}={value}")
        return self._truncate("|".join(pairs))

    def _event_summary(self, event: dict[str, object]) -> str:
        event_type = str(event.get("event_type", "") or event.get("intent_type", "") or event.get("body_state_class", "") or "")
        event_summary = event.get("perceived_summary", "") or event.get("summary", "") or event.get("interaction_type", "")
        return "; ".join(
            [
                f"event_type={self._truncate(event_type)}",
                f"event_summary={self._truncate(event_summary)}",
                f"source_ref={self._truncate(event.get('source_candidate_event_id', '') or event.get('source_body_result_id', '') or event.get('request_id', ''))}",
            ]
        )

    def _goal_state_summary(self, state: dict[str, object]) -> str:
        if not state:
            return ""
        goal_portfolio = state.get("goal_portfolio", [])
        return "; ".join(
            [
                f"primary_goal={self._truncate(state.get('primary_goal', '') or '')}",
                f"long_term_goal={self._truncate(state.get('long_term_goal', '') or '')}",
                f"mid_term_strategy={self._truncate(state.get('mid_term_strategy', '') or '')}",
                f"urgency={self._truncate(state.get('urgency', '') or '')}",
                f"dominant_goal_id={self._truncate(state.get('dominant_goal_id', '') or '')}",
                f"preserved_goal_ids={self._join_list(state.get('preserved_goal_ids'))}",
                f"suppressed_goal_ids={self._join_list(state.get('suppressed_goal_ids'))}",
                f"goal_arbitration_summary={self._truncate(state.get('goal_arbitration_summary', '') or '')}",
                f"goal_portfolio_count={self._count_of(goal_portfolio)}",
                f"goal_portfolio_sample={self._goal_portfolio_sample(goal_portfolio)}",
            ]
        )

    def _goal_state_history_summary(self, value: object) -> str:
        if not isinstance(value, list) or not value:
            return ""
        latest = value[-1] if isinstance(value[-1], dict) else {}
        latest_goal = str(latest.get("primary_goal", "") or "") if isinstance(latest, dict) else ""
        latest_transition = str(latest.get("transition_kind", "") or "") if isinstance(latest, dict) else ""
        return "; ".join(
            [
                f"history_count={len(value)}",
                f"latest_goal={self._truncate(latest_goal)}",
                f"latest_transition={self._truncate(latest_transition)}",
            ]
        )

    def _goal_portfolio_sample(self, value: object) -> str:
        if not isinstance(value, list) or not value:
            return ""
        first = value[0]
        if not isinstance(first, dict):
            return self._truncate(first)
        goal_id = str(first.get("goal_id", "") or "")
        goal = str(first.get("goal", "") or "")
        status = str(first.get("status", "") or "")
        horizon = str(first.get("horizon", "") or "")
        return self._truncate(f"{goal_id}:{goal}:{horizon}:{status}")

    def _supervision_state_summary(self, state: dict[str, object]) -> str:
        if not state:
            return ""
        constraints = state.get("active_constraints", {})
        return "; ".join(
            [
                f"level={self._truncate(state.get('current_level', '') or '')}",
                f"source={self._truncate(state.get('source', '') or '')}",
                f"reason={self._truncate(state.get('last_reason_summary', '') or '')}",
                f"background_mode={self._truncate(self._nested_value(constraints, 'background_mode'))}",
                f"allow_background_loop={self._truncate(self._nested_value(constraints, 'allow_background_loop'))}",
                f"caution_bias={self._truncate(self._nested_value(constraints, 'caution_bias'))}",
                f"pressure_theme={self._truncate(self._nested_value(constraints, 'pressure_theme'))}",
                f"attention_theme={self._join_list(self._nested_value(constraints, 'attention_theme'))}",
                f"blocked_goal_classes={self._join_list(self._nested_value(constraints, 'blocked_goal_classes'))}",
                f"preferred_goal_classes={self._join_list(self._nested_value(constraints, 'preferred_goal_classes'))}",
                f"allow_proactive_initiation={self._truncate(self._nested_value(constraints, 'allow_proactive_initiation'))}",
                f"allow_proactive_tendency_generation={self._truncate(self._nested_value(constraints, 'allow_proactive_tendency_generation'))}",
            ]
        )

    def _unresolved_tension_summary(self, value: object) -> str:
        if not isinstance(value, list) or not value:
            return ""
        first = value[0]
        if not isinstance(first, dict):
            return self._truncate(first)
        return "; ".join(
            [
                f"count={len(value)}",
                f"top_tension_id={self._truncate(first.get('tension_id', '') or '')}",
                f"top_category={self._truncate(first.get('category', '') or '')}",
                f"top_summary={self._truncate(first.get('summary', '') or '')}",
            ]
        )

    def _background_agenda_summary(self, value: dict[str, object]) -> str:
        if not value:
            return ""
        return "; ".join(
            [
                f"latent_tendency={self._truncate(value.get('latent_tendency', '') or '')}",
                f"watch_focus={self._truncate(value.get('watch_focus', '') or '')}",
                f"agenda_phase={self._truncate(value.get('agenda_phase', '') or '')}",
                f"agenda_summary={self._truncate(value.get('agenda_summary', '') or '')}",
                f"supervision_level={self._truncate(value.get('supervision_level', '') or '')}",
            ]
        )

    def _sample_summary(self, value: object) -> str:
        if not isinstance(value, list) or not value:
            return ""
        first = value[0]
        if isinstance(first, dict):
            return self._truncate(
                first.get("summary", "")
                or first.get("observation_summary", "")
                or first.get("value", "")
                or first.get("proposition", "")
                or first.get("event_type", "")
                or first.get("relation_summary", "")
                or first.get("entity_id", "")
            )
        return self._truncate(first)

    def _nested_value(self, value: object, key: str) -> object:
        if not isinstance(value, dict):
            return ""
        return value.get(key, "")

    def _count_of(self, value: object) -> int:
        if isinstance(value, list):
            return len(value)
        return 0

    def _truncate(self, value: object) -> str:
        text = "" if value is None else str(value)
        if len(text) <= self._MAX_VALUE_CHARS:
            return text
        return text[: self._MAX_VALUE_CHARS - 3] + "..."
