from __future__ import annotations


class CharacterPromptPolicy:
    _MAX_VALUE_CHARS = 240

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
            "max_tokens": 800,
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
                '"why_this_now", "role_consistency_hint"] and no extra text.'
            )
        return (
            f"CharacterAgent {task_kind} on {route_mode}: return one JSON object with keys "
            '["interpreted_summary", "interpretation_type", "salience_score", '
            '"ambiguity_level", "risk_level", "opportunity_level", "attention_target", '
            '"inner_prompt_candidate"] and no extra text.'
        )

    def _user_instruction(
        self,
        *,
        actor_id: str,
        control_mode: str,
        context: dict[str, object],
    ) -> str:
        profile = context.get("profile", {})
        snapshot = context.get("snapshot", {})
        memory = context.get("memory", {})
        working_memory_state = context.get("working_memory_state", {})
        event = context.get("event", {})
        profile_summary = self._profile_summary(profile if isinstance(profile, dict) else {})
        snapshot_summary = self._snapshot_summary(snapshot if isinstance(snapshot, dict) else {})
        memory_summary = self._memory_summary(memory if isinstance(memory, dict) else {})
        working_memory_state_summary = self._working_memory_state_summary(
            working_memory_state if isinstance(working_memory_state, dict) else {}
        )
        event_summary = self._event_summary(event if isinstance(event, dict) else {})
        return (
            f"actor_id={actor_id}; control_mode={control_mode}; "
            f"profile_summary={profile_summary}; "
            f"snapshot={snapshot_summary}; memory={memory_summary}; "
            f"working_memory_state={working_memory_state_summary}; event_summary={event_summary}"
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
        ]

    def _profile_summary(self, profile: dict[str, object]) -> str:
        identity_core = profile.get("identity_core", {})
        if not isinstance(identity_core, dict):
            identity_core = {}
        return "; ".join(
            [
                f"character_id={self._truncate(identity_core.get('character_id', ''))}",
                f"canonical_name={self._truncate(identity_core.get('canonical_name', ''))}",
                f"occupation_role={self._truncate(identity_core.get('occupation_role', ''))}",
            ]
        )

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
                f"working_memory_sample={self._sample_summary(memory.get('working_memory'))}",
                f"event_memory_sample={self._sample_summary(memory.get('event_memories'))}",
                f"observation_memory_sample={self._sample_summary(memory.get('observation_memories'))}",
                f"relational_memory_sample={self._sample_summary(memory.get('relational_memories'))}",
                f"knowledge_memory_sample={self._sample_summary(memory.get('knowledge_memories'))}",
                f"social_memory_sample={self._sample_summary(memory.get('social_memories'))}",
            ]
        )

    def _working_memory_state_summary(self, state: dict[str, object]) -> str:
        return "; ".join(
            [
                f"recent_perceived_events_count={self._count_of(state.get('recent_perceived_events'))}",
                f"recent_esm_results_count={self._count_of(state.get('recent_esm_results'))}",
                f"recent_siming_catalysts_count={self._count_of(state.get('recent_siming_catalysts'))}",
                f"private_snapshot_actor_id={self._truncate(self._nested_value(state.get('private_snapshot'), 'actor_id'))}",
            ]
        )

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
        text = str(value or "")
        if len(text) <= self._MAX_VALUE_CHARS:
            return text
        return text[: self._MAX_VALUE_CHARS - 3] + "..."
