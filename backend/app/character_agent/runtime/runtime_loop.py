from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.models.character_agent_runtime import CharacterGoalCommand
from app.models.character_agent_runtime import CHARACTER_AGENT_CONTROL_MODES
from app.models.character_agent_runtime import CHARACTER_ACTOR_AUTONOMY_MODES
from app.models.character_agent_runtime import SHARED_CHARACTER_COMMANDS
from app.models.character_agent_runtime import CharacterInterpretation
from app.models.character_agent_runtime import CharacterIntentDecision
from app.models.character_agent_runtime import CharacterSuggestionPacket
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.character_agent.reasoning.l1_perception import CharacterAgentL1Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.execution.l4_adapter import CharacterAgentL4Adapter
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.services.character_agent_debug_projection import CharacterAgentDebugProjection
from app.models.siming_character_bridge import SimingCharacterCompatibilityInput


class CharacterAgentRuntime:
    AWAY_CONSERVATIVE_ALLOWED_COMMANDS = {"look_at", "observe", "speak"}
    _RECENT_HISTORY_LIMIT = 4
    _PROFILE_DIRECTORY = Path(__file__).resolve().parents[4] / "assets" / "characters" / "profiles"

    def __init__(self, storage_root: str | Path | None = None) -> None:
        self._profile_registry = CharacterProfileRegistry.from_directory(self._PROFILE_DIRECTORY)
        self._supported_actor_ids = set(self._profile_registry.actor_ids())
        self._l1 = CharacterAgentL1Service()
        self._l2 = CharacterAgentL2Service(profile_registry=self._profile_registry)
        self._l3 = CharacterAgentL3Service()
        self._l4 = CharacterAgentL4Adapter()
        self._l4_executor = CharacterAgentL4Executor()
        self._observatory_projection = CharacterAgentDebugProjection()
        self._control_modes = self._build_default_control_modes()
        self._pending_suggestions: list[CharacterSuggestionPacket] = []
        self._pending_observatory_messages: list[dict[str, object]] = []
        self._observatory_actor_context: dict[str, dict[str, str]] = {}
        self._session_store = CharacterAgentSessionStore(storage_root=storage_root)
        self._memory_store = CharacterAgentMemoryStore()
        self._rehydrate_memory_from_timeline()

    def ingest_character_perceived_event(self, event: CharacterPerceivedEvent) -> list[CharacterGoalCommand]:
        if not self.supports_actor(event.actor_id):
            return []
        self._record_character_perceived_event(event)
        self._record_relational_belief_from_perceived_event(event)
        snapshot = self._l1.apply_character_perceived_event(event)
        self._queue_observatory_stage_event(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            stage="character_perceived_event",
            summary=event.perceived_summary,
            focus_target=self._snapshot_focus_target(snapshot),
            intent_label="",
            participants=self._participants_for_actor(event.actor_id, self._snapshot_focus_target(snapshot)),
            detail=event.model_dump(),
        )
        memory_bundle = self.get_memory_bundle(event.actor_id)
        working_memory_state = self.get_working_memory_state(event.actor_id, snapshot.model_dump())
        self._queue_observatory_snapshot(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
        )
        reasoning_request = self._l2.prepare_reasoning_request(
            snapshot=snapshot,
            event=event,
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._record_reasoning_request(event.actor_id, event.producer_ts, reasoning_request)
        interpretation = self._l2.interpret_perceived_event(
            snapshot,
            event,
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._record_interpretation_event(event.actor_id, event.producer_ts, interpretation)
        self._set_observatory_context(event.actor_id, "interpretation_summary", interpretation.interpreted_summary)
        self._queue_observatory_stage_event(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            stage="interpretation",
            summary=interpretation.interpreted_summary,
            focus_target=str(interpretation.attention_target or self._snapshot_focus_target(snapshot)),
            intent_label=interpretation.interpretation_type,
            participants=self._participants_for_actor(event.actor_id, str(interpretation.attention_target or self._snapshot_focus_target(snapshot))),
            detail=interpretation.model_dump(),
        )
        self._queue_observatory_snapshot(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
        )
        decision = self._l3.select_intent(
            interpretation,
            snapshot=snapshot.model_dump(),
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._set_observatory_context(event.actor_id, "decision_summary", decision.selected_intent)
        self._queue_observatory_stage_event(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            stage="decision",
            summary=decision.rationale or interpretation.interpreted_summary,
            focus_target=str(interpretation.attention_target or self._snapshot_focus_target(snapshot)),
            intent_label=decision.selected_intent,
            participants=self._participants_for_actor(event.actor_id, str(interpretation.attention_target or self._snapshot_focus_target(snapshot))),
            detail=decision.model_dump(),
        )
        self._queue_observatory_snapshot(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
        )
        if self.get_control_mode(event.actor_id) == "player_priority_assisted":
            self._pending_suggestions.append(self._planner_suggestion_packet(
                actor_id=event.actor_id,
                producer_ts=event.producer_ts,
                interpretation=interpretation,
                working_memory_state=working_memory_state,
            ))
            return []
        execution_plan = self._record_execution_plan(
            event.actor_id,
            event.producer_ts,
            snapshot,
            interpretation,
            decision,
        )
        return self.filter_commands_for_actor(
            event.actor_id,
            self._l4.build_commands_from_execution_plan(execution_plan),
        )

    def is_command_allowed_for_mode(self, mode: str, command: str) -> bool:
        if command not in SHARED_CHARACTER_COMMANDS:
            return False
        if mode in CHARACTER_AGENT_CONTROL_MODES:
            if mode == "away_conservative_takeover":
                return command in self.AWAY_CONSERVATIVE_ALLOWED_COMMANDS
            return True
        if mode not in CHARACTER_ACTOR_AUTONOMY_MODES:
            return False
        if mode == "away_conservative_takeover":
            return command in self.AWAY_CONSERVATIVE_ALLOWED_COMMANDS
        return True

    def is_valid_control_mode(self, mode: str) -> bool:
        return mode in CHARACTER_AGENT_CONTROL_MODES

    def get_control_mode(self, actor_id: str) -> str:
        return self._control_modes.get(actor_id, "agent_full_auto")

    def set_control_mode(self, actor_id: str, mode: str) -> None:
        if not self.supports_actor(actor_id):
            raise ValueError(f"unsupported actor_id: {actor_id}")
        if not self.is_valid_control_mode(mode):
            raise ValueError(f"unsupported control mode: {mode}")
        self._control_modes[actor_id] = mode

    def ingest_self_body_perceived_event(self, event: SelfBodyPerceivedEvent) -> list[CharacterGoalCommand]:
        if not self.supports_actor(event.actor_id):
            return []
        self._record_self_body_event(event)
        snapshot = self._l1.apply_self_body_perceived_event(event)
        self._queue_observatory_stage_event(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            stage="self_body_perceived_event",
            summary=event.perceived_summary,
            focus_target=self._snapshot_focus_target(snapshot),
            intent_label=event.body_state_class,
            participants=self._participants_for_actor(event.actor_id, self._snapshot_focus_target(snapshot)),
            detail=event.model_dump(),
        )
        memory_bundle = self.get_memory_bundle(event.actor_id)
        working_memory_state = self.get_working_memory_state(event.actor_id, snapshot.model_dump())
        self._queue_observatory_snapshot(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
        )
        reasoning_request = self._l2.prepare_reasoning_request(
            snapshot=snapshot,
            event=event,
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._record_reasoning_request(event.actor_id, event.producer_ts, reasoning_request)
        interpretation = self._l2.interpret_self_body_event(
            snapshot,
            event,
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._record_interpretation_event(event.actor_id, event.producer_ts, interpretation)
        self._set_observatory_context(event.actor_id, "interpretation_summary", interpretation.interpreted_summary)
        self._queue_observatory_stage_event(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            stage="interpretation",
            summary=interpretation.interpreted_summary,
            focus_target=str(interpretation.attention_target or self._snapshot_focus_target(snapshot)),
            intent_label=interpretation.interpretation_type,
            participants=self._participants_for_actor(event.actor_id, str(interpretation.attention_target or self._snapshot_focus_target(snapshot))),
            detail=interpretation.model_dump(),
        )
        self._queue_observatory_snapshot(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
        )
        decision = self._l3.select_intent(
            interpretation,
            snapshot=snapshot.model_dump(),
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._set_observatory_context(event.actor_id, "decision_summary", decision.selected_intent)
        self._queue_observatory_stage_event(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            stage="decision",
            summary=decision.rationale or interpretation.interpreted_summary,
            focus_target=str(interpretation.attention_target or self._snapshot_focus_target(snapshot)),
            intent_label=decision.selected_intent,
            participants=self._participants_for_actor(event.actor_id, str(interpretation.attention_target or self._snapshot_focus_target(snapshot))),
            detail=decision.model_dump(),
        )
        self._queue_observatory_snapshot(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
        )
        if self.get_control_mode(event.actor_id) == "player_priority_assisted":
            self._pending_suggestions.append(self._planner_suggestion_packet(
                actor_id=event.actor_id,
                producer_ts=event.producer_ts,
                interpretation=interpretation,
                working_memory_state=working_memory_state,
            ))
            return []
        execution_plan = self._record_execution_plan(
            event.actor_id,
            event.producer_ts,
            snapshot,
            interpretation,
            decision,
        )
        return self.filter_commands_for_actor(
            event.actor_id,
            self._l4.build_commands_from_execution_plan(execution_plan),
        )

    def ingest_siming_output(
        self,
        payload: dict[str, object] | SimingCharacterCompatibilityInput,
    ) -> list[CharacterGoalCommand]:
        validated_payload = (
            payload
            if isinstance(payload, SimingCharacterCompatibilityInput)
            else SimingCharacterCompatibilityInput.model_validate(payload)
        )
        normalized_payload = self._normalize_siming_payload(
            validated_payload.model_dump(exclude_none=True)
        )
        actor_id = str(
            normalized_payload.get("target_actor_id")
            or normalized_payload.get("actor_id")
            or ""
        )
        if not self.supports_actor(actor_id):
            return []
        normalized_payload["target_actor_id"] = actor_id
        self._record_siming_event(normalized_payload)
        snapshot = self._l1.apply_siming_output(normalized_payload)
        self._set_observatory_context(
            actor_id,
            "latest_siming_summary",
            str(normalized_payload.get("presentation_hint", "") or ""),
        )
        self._queue_observatory_stage_event(
            actor_id=actor_id,
            producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
            stage="siming_output_event",
            summary=str(normalized_payload.get("presentation_hint", "") or ""),
            focus_target=self._snapshot_focus_target(snapshot),
            intent_label=str(normalized_payload.get("output_type", "siming_output") or "siming_output"),
            participants=self._participants_for_actor(actor_id, self._snapshot_focus_target(snapshot)),
            detail=dict(normalized_payload),
        )
        memory_bundle = self.get_memory_bundle(actor_id)
        working_memory_state = self.get_working_memory_state(actor_id, snapshot.model_dump())
        reasoning_request = self._gateway_reasoning_request_for_siming(
            actor_id,
            snapshot,
            normalized_payload,
            memory_bundle,
            working_memory_state,
        )
        self._record_reasoning_request(
            actor_id,
            int(normalized_payload.get("producer_ts", 0) or 0),
            reasoning_request,
        )
        self._queue_observatory_snapshot(
            actor_id=actor_id,
            producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
            snapshot=snapshot,
            memory_bundle=memory_bundle,
        )
        interpretation = self._l2.interpret_siming_output(
            snapshot,
            normalized_payload,
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(actor_id),
            working_memory_state=working_memory_state,
        )
        self._record_interpretation_event(
            actor_id,
            int(normalized_payload.get("producer_ts", 0) or 0),
            interpretation,
        )
        self._set_observatory_context(actor_id, "interpretation_summary", interpretation.interpreted_summary)
        self._queue_observatory_stage_event(
            actor_id=actor_id,
            producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
            stage="interpretation",
            summary=interpretation.interpreted_summary,
            focus_target=str(interpretation.attention_target or self._snapshot_focus_target(snapshot)),
            intent_label=interpretation.interpretation_type,
            participants=self._participants_for_actor(actor_id, str(interpretation.attention_target or self._snapshot_focus_target(snapshot))),
            detail=interpretation.model_dump(),
        )
        self._queue_observatory_snapshot(
            actor_id=actor_id,
            producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
            snapshot=snapshot,
            memory_bundle=memory_bundle,
        )
        decision = self._l3.select_intent(
            interpretation,
            snapshot=snapshot.model_dump(),
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(actor_id),
            working_memory_state=working_memory_state,
        )
        self._set_observatory_context(actor_id, "decision_summary", decision.selected_intent)
        self._queue_observatory_stage_event(
            actor_id=actor_id,
            producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
            stage="decision",
            summary=decision.rationale or interpretation.interpreted_summary,
            focus_target=str(interpretation.attention_target or self._snapshot_focus_target(snapshot)),
            intent_label=decision.selected_intent,
            participants=self._participants_for_actor(actor_id, str(interpretation.attention_target or self._snapshot_focus_target(snapshot))),
            detail=decision.model_dump(),
        )
        self._queue_observatory_snapshot(
            actor_id=actor_id,
            producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
            snapshot=snapshot,
            memory_bundle=memory_bundle,
        )
        if self.get_control_mode(actor_id) == "player_priority_assisted":
            self._pending_suggestions.append(self._planner_suggestion_packet(
                actor_id=actor_id,
                producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
                interpretation=interpretation,
                working_memory_state=working_memory_state,
            ))
            return []
        execution_plan = self._record_execution_plan(
            actor_id,
            int(normalized_payload.get("producer_ts", 0) or 0),
            snapshot,
            interpretation,
            decision,
        )
        return self.filter_commands_for_actor(
            actor_id,
            self._l4.build_commands_from_execution_plan(execution_plan),
        )

    def supports_actor(self, actor_id: str) -> bool:
        return actor_id in self._supported_actor_ids

    def get_private_snapshot(self, actor_id: str):
        return self._l1.get_snapshot(actor_id)

    def get_session_timeline(self, actor_id: str) -> list[dict[str, object]]:
        return self._session_store.list_events(actor_id)

    def get_memory_bundle(self, actor_id: str) -> dict[str, list[dict[str, object]]]:
        return self._memory_store.retrieval_bundle(actor_id)

    def get_working_memory_state(self, actor_id: str, private_snapshot: dict[str, object] | None = None) -> dict[str, object]:
        return self._memory_store.working_memory_state(actor_id, private_snapshot=private_snapshot).model_dump()

    def drain_suggestion_packets(self, actor_id: str | None = None) -> list[CharacterSuggestionPacket]:
        if actor_id is None:
            packets = self._pending_suggestions
            self._pending_suggestions = []
            return packets
        matched = [packet for packet in self._pending_suggestions if packet.actor_id == actor_id]
        self._pending_suggestions = [packet for packet in self._pending_suggestions if packet.actor_id != actor_id]
        return matched

    def drain_observatory_messages(self, actor_id: str | None = None) -> list[dict[str, object]]:
        if actor_id is None:
            messages = self._pending_observatory_messages
            self._pending_observatory_messages = []
            return messages
        matched: list[dict[str, object]] = []
        remaining: list[dict[str, object]] = []
        for message in self._pending_observatory_messages:
            payload = message.get("payload", {})
            if isinstance(payload, dict) and str(payload.get("actor_id", "") or "") == actor_id:
                matched.append(message)
            else:
                remaining.append(message)
        self._pending_observatory_messages = remaining
        return matched

    def filter_commands_for_actor(
        self,
        actor_id: str,
        commands: list[CharacterGoalCommand],
    ) -> list[CharacterGoalCommand]:
        mode = self.get_control_mode(actor_id)
        if mode == "player_priority_assisted":
            return []
        return [command for command in commands if self.is_command_allowed_for_mode(mode, command.command_type)]

    def _record_character_perceived_event(self, event: CharacterPerceivedEvent) -> None:
        stored = self._session_store.append_event(
            actor_id=event.actor_id,
            event_type="character_perceived_event",
            producer_ts=event.producer_ts,
            payload={
                "percept_channel": event.percept_channel,
                "summary": event.perceived_summary,
                "tags": [event.percept_channel],
                "source_candidate_event_id": event.source_candidate_event_id,
            },
        )
        self._memory_store.write_event(stored)

    def _record_relational_belief_from_perceived_event(self, event: CharacterPerceivedEvent) -> None:
        entity_id = str(event.source_actor_id or "")
        if entity_id == "" or entity_id == event.actor_id:
            return
        value = self._infer_relational_belief_value(event)
        stored = self._session_store.append_event(
            actor_id=event.actor_id,
            event_type="relational_belief_event",
            producer_ts=event.producer_ts,
            payload={
                "entity_id": entity_id,
                "belief_type": "trust_level",
                "value": value,
            },
        )
        self._memory_store.write_event(stored)

    def _infer_relational_belief_value(self, event: CharacterPerceivedEvent) -> str:
        if event.certainty_score < 0.75 or event.clarity_score < 0.85:
            return "guarded"
        return "noticed"

    def _record_self_body_event(self, event: SelfBodyPerceivedEvent) -> None:
        stored = self._session_store.append_event(
            actor_id=event.actor_id,
            event_type="self_body_perceived_event",
            producer_ts=event.producer_ts,
            payload={
                "body_state_class": event.body_state_class,
                "summary": event.perceived_summary,
                "source_body_result_id": event.source_body_result_id,
            },
        )
        self._memory_store.write_event(stored)

    def _record_siming_event(self, payload: dict[str, object]) -> None:
        actor_id = str(payload.get("target_actor_id", "") or "")
        if actor_id == "":
            return
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="siming_output_event",
            producer_ts=int(payload.get("producer_ts", 0) or 0),
            payload={
                "summary": str(payload.get("presentation_hint", "") or ""),
                "pressure_hint": str(payload.get("pressure_hint", "") or ""),
                "salience_boost": payload.get("salience_boost"),
                "reason_scope": str(payload.get("reason_scope", "") or ""),
                "target_object_id": str(payload.get("target_object_id", "") or ""),
                "target_environment_id": str(payload.get("target_environment_id", "") or ""),
            },
        )
        self._memory_store.write_event(stored)

    def record_execution_request(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        payload: dict[str, object],
    ) -> None:
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_agent_execution_request",
            producer_ts=producer_ts,
            payload=payload,
        )
        self._memory_store.write_event(stored)

    def record_settlement_result(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        payload: dict[str, object],
    ) -> None:
        snapshot = self._l1.get_snapshot(actor_id)
        if snapshot is not None:
            result_type = str(payload.get("result_type", "") or "")
            if result_type == "constraint_state_result":
                snapshot.recent_constraint_results = self._append_recent_entry(
                    snapshot.recent_constraint_results,
                    str(payload.get("constraint_summary", "") or ""),
                )
            else:
                snapshot.recent_world_changes = self._append_recent_entry(
                    snapshot.recent_world_changes,
                    str(payload.get("change_summary", "") or result_type or "world_result"),
        )
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_agent_settlement_result",
            producer_ts=producer_ts,
            payload=payload,
        )
        self._memory_store.write_event(stored)
        outcome_summary = str(payload.get("constraint_summary", "") or payload.get("change_summary", "") or payload.get("stable_state_summary", "") or payload.get("result_type", "") or "")
        self._set_observatory_context(actor_id, "latest_outcome_summary", outcome_summary)
        self._queue_observatory_stage_event(
            actor_id=actor_id,
            producer_ts=producer_ts,
            stage="settlement_result",
            summary=outcome_summary,
            focus_target=self._snapshot_focus_target(self._get_snapshot_for_observatory(actor_id, producer_ts)),
            intent_label=str(payload.get("result_type", "") or ""),
            participants=self._participants_for_actor(actor_id, str(payload.get("target_actor_id", "") or str(payload.get("target_object_id", "") or str(payload.get("target_environment_id", "") or "")))),
            detail=dict(payload),
        )
        self._queue_observatory_snapshot(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=self._get_snapshot_for_observatory(actor_id, producer_ts),
            memory_bundle=self.get_memory_bundle(actor_id),
        )

    def record_dialogue_response(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        payload: dict[str, object],
    ) -> None:
        snapshot = self._l1.get_snapshot(actor_id)
        if snapshot is not None:
            dialogue_summary = str(payload.get("content", "") or payload.get("summary", "") or "").strip()
            snapshot.recent_world_changes = self._append_recent_entry(
                snapshot.recent_world_changes,
                "dialogue_response:%s" % dialogue_summary if dialogue_summary != "" else "dialogue_response",
            )
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_agent_dialogue_response",
            producer_ts=producer_ts,
            payload=payload,
        )
        self._memory_store.write_event(stored)
        dialogue_summary = str(payload.get("content", "") or payload.get("summary", "") or "")
        self._set_observatory_context(actor_id, "latest_outcome_summary", dialogue_summary)
        self._queue_observatory_stage_event(
            actor_id=actor_id,
            producer_ts=producer_ts,
            stage="dialogue_writeback",
            summary=dialogue_summary,
            focus_target=self._snapshot_focus_target(self._get_snapshot_for_observatory(actor_id, producer_ts)),
            intent_label="dialogue_response",
            participants=self._participants_for_actor(actor_id, ""),
            detail={
                **dict(payload),
                "spoken_content": dialogue_summary,
                "interpreted_summary": self._observatory_context(actor_id).get("interpretation_summary", ""),
                "perceived_summary": self._get_snapshot_for_observatory(actor_id, producer_ts).visible_entities[0]
                if self._get_snapshot_for_observatory(actor_id, producer_ts).visible_entities
                else "",
                "alignment_label": "alignment",
                "target_actor_id": str(payload.get("target_actor_id", "") or ""),
            },
        )
        self._queue_observatory_snapshot(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=self._get_snapshot_for_observatory(actor_id, producer_ts),
            memory_bundle=self.get_memory_bundle(actor_id),
        )

    def _record_reasoning_request(
        self,
        actor_id: str,
        producer_ts: int,
        request: dict[str, object],
    ) -> None:
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="l2_reasoning_request",
            producer_ts=producer_ts,
            payload=request,
        )
        self._memory_store.write_event(stored)

    def _record_interpretation_event(
        self,
        actor_id: str,
        producer_ts: int,
        interpretation: CharacterInterpretation,
    ) -> None:
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_interpretation_event",
            producer_ts=producer_ts,
            payload=interpretation.model_dump(),
        )
        self._memory_store.write_event(stored)

    def _record_execution_plan(
        self,
        actor_id: str,
        producer_ts: int,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> dict[str, object]:
        plan = self._l4_executor.build_execution_plan(
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
        )
        self._set_observatory_context(actor_id, "execution_summary", str(plan.get("social_spatial_channel", {}).get("spacing_behavior", "") if isinstance(plan.get("social_spatial_channel"), dict) else ""))
        self.record_execution_request(
            actor_id=actor_id,
            producer_ts=producer_ts,
            payload=plan,
        )
        self._queue_observatory_stage_event(
            actor_id=actor_id,
            producer_ts=producer_ts,
            stage="execution_request",
            summary=self._observatory_context(actor_id).get("execution_summary", "") or "execution request staged",
            focus_target=self._snapshot_focus_target(snapshot),
            intent_label=decision.selected_intent,
            participants=self._participants_for_actor(actor_id, self._snapshot_focus_target(snapshot)),
            detail=plan,
        )
        self._queue_observatory_snapshot(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            memory_bundle=self.get_memory_bundle(actor_id),
        )
        return plan

    def _gateway_reasoning_request_for_siming(
        self,
        actor_id: str,
        snapshot: object,
        payload: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]],
        working_memory_state: dict[str, object],
    ) -> dict[str, object]:
        class _SimingEvent:
            def __init__(self, actor_id: str, payload: dict[str, object]) -> None:
                self.actor_id = actor_id
                self.percept_channel = str(payload.get("percept_channel", "") or "siming")
                self.producer_ts = int(payload.get("producer_ts", 0) or 0)
                self.room_id = str(payload.get("room_id", "") or "")
                self.scene_id = str(payload.get("scene_id", "") or "")
                self.zone_id = str(payload.get("zone_id", "") or "")
                self.perceived_summary = str(
                    payload.get("perceived_summary", "")
                    or payload.get("presentation_hint", "")
                    or "siming_catalyst"
                )
                self.source_candidate_event_id = str(payload.get("causation_id", "") or f"siming:{self.producer_ts}")
                self.clarity_score = float(payload.get("clarity_score", 1.0) or 1.0)
                self.certainty_score = float(payload.get("certainty_score", 1.0) or 1.0)
                self.target_actor_id = str(payload.get("target_actor_id", "") or "")
                self.target_object_id = str(payload.get("target_object_id", "") or "")
                self.target_environment_id = str(payload.get("target_environment_id", "") or "")
                self.presentation_hint = str(payload.get("presentation_hint", "") or "")
                self.pressure_hint = str(payload.get("pressure_hint", "") or "")
                self.reason_scope = str(payload.get("reason_scope", "") or "")
                self.salience_boost = payload.get("salience_boost")

            def model_dump(self) -> dict[str, object]:
                return {
                    "actor_id": self.actor_id,
                    "percept_channel": self.percept_channel,
                    "producer_ts": self.producer_ts,
                    "room_id": self.room_id,
                    "scene_id": self.scene_id,
                    "zone_id": self.zone_id,
                    "perceived_summary": self.perceived_summary,
                    "source_candidate_event_id": self.source_candidate_event_id,
                    "clarity_score": self.clarity_score,
                    "certainty_score": self.certainty_score,
                    "target_actor_id": self.target_actor_id,
                    "target_object_id": self.target_object_id,
                    "target_environment_id": self.target_environment_id,
                    "presentation_hint": self.presentation_hint,
                    "pressure_hint": self.pressure_hint,
                    "reason_scope": self.reason_scope,
                    "salience_boost": self.salience_boost,
                }

        return self._l2.prepare_reasoning_request(
            snapshot=snapshot,
            event=_SimingEvent(actor_id, payload),
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(actor_id),
            working_memory_state=working_memory_state,
        )

    def _normalize_siming_payload(self, payload: dict[str, object]) -> dict[str, object]:
        normalized = dict(payload)
        presentation_hint = str(normalized.get("presentation_hint", "") or "").strip()
        if presentation_hint != "":
            normalized["presentation_hint"] = presentation_hint
            normalized.setdefault("perceived_summary", presentation_hint)
        else:
            normalized.pop("presentation_hint", None)
        normalized.setdefault("percept_channel", "siming")

        pressure_hint = str(normalized.get("pressure_hint", "") or "").strip()
        if pressure_hint != "":
            normalized["pressure_hint"] = pressure_hint
        else:
            normalized.pop("pressure_hint", None)

        reason_scope = str(normalized.get("reason_scope", "") or "").strip()
        if reason_scope != "":
            normalized["reason_scope"] = reason_scope
        else:
            normalized.pop("reason_scope", None)

        salience_boost = normalized.get("salience_boost")
        if isinstance(salience_boost, int | float):
            normalized_boost = min(1.0, max(0.0, float(salience_boost)))
            normalized["salience_boost"] = normalized_boost
            normalized.setdefault("clarity_score", normalized_boost if normalized_boost >= 0.5 else 0.5)
        return normalized

    def _planner_suggestion_packet(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        interpretation: CharacterInterpretation,
        working_memory_state: dict[str, object] | None = None,
    ) -> CharacterSuggestionPacket:
        packet = self._l3.build_suggestion_packet(
            interpretation=interpretation,
            control_mode="player_priority_assisted",
            snapshot=self._l1.get_snapshot(actor_id).model_dump() if self._l1.get_snapshot(actor_id) is not None else {},
            memory_bundle=self.get_memory_bundle(actor_id),
            working_memory_state=working_memory_state or {},
        )
        packet["actor_id"] = actor_id
        packet["producer_ts"] = producer_ts
        packet["causation_id"] = f"character_suggestion:{producer_ts}:{actor_id}"
        packet["correlation_id"] = f"character_suggestion:{producer_ts}:{actor_id}"
        suggestion_packet = CharacterSuggestionPacket(**packet)
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_agent_suggestion_packet",
            producer_ts=producer_ts,
            payload=suggestion_packet.model_dump(exclude_none=True),
        )
        self._memory_store.write_event(stored)
        self._set_observatory_context(actor_id, "decision_summary", suggestion_packet.why_this_now or (suggestion_packet.recommended_intents[0] if suggestion_packet.recommended_intents else ""))
        self._queue_observatory_stage_event(
            actor_id=actor_id,
            producer_ts=producer_ts,
            stage="suggestion_packet",
            summary=suggestion_packet.why_this_now,
            focus_target=self._snapshot_focus_target(self._get_snapshot_for_observatory(actor_id, producer_ts)),
            intent_label=suggestion_packet.recommended_intents[0] if suggestion_packet.recommended_intents else "",
            participants=self._participants_for_actor(actor_id, self._snapshot_focus_target(self._get_snapshot_for_observatory(actor_id, producer_ts))),
            detail={
                **suggestion_packet.model_dump(exclude_none=True),
                "target_actor_id": self._snapshot_focus_target(self._get_snapshot_for_observatory(actor_id, producer_ts)),
                "interpreted_summary": self._observatory_context(actor_id).get("interpretation_summary", ""),
                "perceived_summary": self._snapshot_focus_target(self._get_snapshot_for_observatory(actor_id, producer_ts)),
                "spoken_content": suggestion_packet.why_this_now,
                "alignment_label": "alignment",
            },
        )
        self._queue_observatory_snapshot(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=self._get_snapshot_for_observatory(actor_id, producer_ts),
            memory_bundle=self.get_memory_bundle(actor_id),
        )
        return suggestion_packet

    def _append_recent_entry(self, entries: list[str], value: str) -> list[str]:
        if value == "":
            return entries
        updated = list(entries)
        updated.append(value)
        return updated[-self._RECENT_HISTORY_LIMIT :]

    def _build_default_control_modes(self) -> dict[str, str]:
        return {
            actor_id: self._profile_registry.get(actor_id).runtime_defaults.default_control_mode
            for actor_id in self._supported_actor_ids
        }

    def _rehydrate_memory_from_timeline(self) -> None:
        for actor_id, events in self._session_store.list_all_events().items():
            for event in events:
                if isinstance(event, dict):
                    self._memory_store.write_event(event)

    def _observatory_context(self, actor_id: str) -> dict[str, str]:
        return self._observatory_actor_context.setdefault(
            actor_id,
            {
                "interpretation_summary": "",
                "decision_summary": "",
                "execution_summary": "",
                "latest_outcome_summary": "",
                "latest_siming_summary": "",
            },
        )

    def _set_observatory_context(self, actor_id: str, key: str, value: str) -> None:
        self._observatory_context(actor_id)[key] = value

    def _queue_observatory_stage_event(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        stage: str,
        summary: str,
        focus_target: str,
        intent_label: str,
        participants: list[str],
        detail: dict[str, object],
    ) -> None:
        event = self._observatory_projection.project_stage_event(
            actor_id=actor_id,
            producer_ts=producer_ts,
            stage=stage,
            summary=summary,
            focus_target=focus_target,
            intent_label=intent_label,
            participants=participants,
            detail=detail,
        )
        self._pending_observatory_messages.append(
            {
                "message_type": "character_agent_debug_event",
                "payload": event.model_dump(exclude_none=True),
            }
        )

    def _queue_observatory_snapshot(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        snapshot: CharacterPrivateWorldSnapshot,
        memory_bundle: dict[str, list[dict[str, object]]],
    ) -> None:
        context = self._observatory_context(actor_id)
        state = self._observatory_projection.project_snapshot(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            memory_bundle=memory_bundle,
            interpretation_summary=context.get("interpretation_summary", ""),
            decision_summary=context.get("decision_summary", ""),
            execution_summary=context.get("execution_summary", ""),
            latest_outcome_summary=context.get("latest_outcome_summary", ""),
            latest_siming_summary=context.get("latest_siming_summary", ""),
        )
        self._pending_observatory_messages.append(
            {
                "message_type": "character_agent_debug_snapshot",
                "payload": state.model_dump(exclude_none=True),
            }
        )

    def _snapshot_focus_target(self, snapshot: CharacterPrivateWorldSnapshot) -> str:
        if snapshot.current_attention_targets:
            return str(snapshot.current_attention_targets[0])
        if snapshot.attention_targets:
            return str(snapshot.attention_targets[0])
        return ""

    def _participants_for_actor(self, actor_id: str, target_ref: str) -> list[str]:
        participants = [actor_id]
        if target_ref != "":
            participants.append(target_ref)
        return participants

    def _get_snapshot_for_observatory(self, actor_id: str, producer_ts: int) -> CharacterPrivateWorldSnapshot:
        snapshot = self.get_private_snapshot(actor_id)
        if snapshot is not None:
            return snapshot
        return CharacterPrivateWorldSnapshot(
            actor_id=actor_id,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            producer_ts=producer_ts,
            updated_at=producer_ts,
        )
