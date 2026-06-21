from pathlib import Path

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


class CharacterAgentRuntime:
    SUPPORTED_ACTORS = {"char_a", "char_b", "char_c"}
    AWAY_CONSERVATIVE_ALLOWED_COMMANDS = {"look_at", "observe", "speak"}
    _RECENT_HISTORY_LIMIT = 4
    DEFAULT_CONTROL_MODES = {
        "char_a": "agent_full_auto",
        "char_b": "agent_full_auto",
        "char_c": "player_priority_assisted",
    }

    def __init__(self, storage_root: str | Path | None = None) -> None:
        self._l1 = CharacterAgentL1Service()
        self._l2 = CharacterAgentL2Service()
        self._l3 = CharacterAgentL3Service()
        self._l4 = CharacterAgentL4Adapter()
        self._l4_executor = CharacterAgentL4Executor()
        self._control_modes = self.DEFAULT_CONTROL_MODES.copy()
        self._pending_suggestions: list[CharacterSuggestionPacket] = []
        self._session_store = CharacterAgentSessionStore(storage_root=storage_root)
        self._memory_store = CharacterAgentMemoryStore()
        self._rehydrate_memory_from_timeline()

    def ingest_character_perceived_event(self, event: CharacterPerceivedEvent) -> list[CharacterGoalCommand]:
        if event.actor_id not in self.SUPPORTED_ACTORS:
            return []
        self._record_character_perceived_event(event)
        self._record_relational_belief_from_perceived_event(event)
        snapshot = self._l1.apply_character_perceived_event(event)
        memory_bundle = self.get_memory_bundle(event.actor_id)
        working_memory_state = self.get_working_memory_state(event.actor_id, snapshot.model_dump())
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
        decision = self._l3.select_intent(
            interpretation,
            snapshot=snapshot.model_dump(),
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
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
        if actor_id not in self.SUPPORTED_ACTORS:
            raise ValueError(f"unsupported actor_id: {actor_id}")
        if not self.is_valid_control_mode(mode):
            raise ValueError(f"unsupported control mode: {mode}")
        self._control_modes[actor_id] = mode

    def ingest_self_body_perceived_event(self, event: SelfBodyPerceivedEvent) -> list[CharacterGoalCommand]:
        if event.actor_id not in self.SUPPORTED_ACTORS:
            return []
        self._record_self_body_event(event)
        snapshot = self._l1.apply_self_body_perceived_event(event)
        memory_bundle = self.get_memory_bundle(event.actor_id)
        working_memory_state = self.get_working_memory_state(event.actor_id, snapshot.model_dump())
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
        decision = self._l3.select_intent(
            interpretation,
            snapshot=snapshot.model_dump(),
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
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

    def ingest_siming_output(self, payload: dict[str, object]) -> list[CharacterGoalCommand]:
        actor_id = str(payload.get("target_actor_id", "") or "")
        if actor_id not in self.SUPPORTED_ACTORS:
            return []
        self._record_siming_event(payload)
        snapshot = self._l1.apply_siming_output(payload)
        memory_bundle = self.get_memory_bundle(actor_id)
        working_memory_state = self.get_working_memory_state(actor_id, snapshot.model_dump())
        reasoning_request = self._gateway_reasoning_request_for_siming(actor_id, snapshot, payload, memory_bundle, working_memory_state)
        self._record_reasoning_request(actor_id, int(payload.get("producer_ts", 0) or 0), reasoning_request)
        interpretation = self._l2.interpret_siming_output(
            snapshot,
            payload,
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(actor_id),
            working_memory_state=working_memory_state,
        )
        self._record_interpretation_event(actor_id, int(payload.get("producer_ts", 0) or 0), interpretation)
        decision = self._l3.select_intent(
            interpretation,
            snapshot=snapshot.model_dump(),
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(actor_id),
            working_memory_state=working_memory_state,
        )
        if self.get_control_mode(actor_id) == "player_priority_assisted":
            self._pending_suggestions.append(self._planner_suggestion_packet(
                actor_id=actor_id,
                producer_ts=int(payload.get("producer_ts", 0) or 0),
                interpretation=interpretation,
                working_memory_state=working_memory_state,
            ))
            return []
        execution_plan = self._record_execution_plan(
            actor_id,
            int(payload.get("producer_ts", 0) or 0),
            snapshot,
            interpretation,
            decision,
        )
        return self.filter_commands_for_actor(
            actor_id,
            self._l4.build_commands_from_execution_plan(execution_plan),
        )

    def supports_actor(self, actor_id: str) -> bool:
        return actor_id in self.SUPPORTED_ACTORS

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
        self.record_execution_request(
            actor_id=actor_id,
            producer_ts=producer_ts,
            payload=plan,
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
                self.percept_channel = "siming"
                self.producer_ts = int(payload.get("producer_ts", 0) or 0)
                self.room_id = str(payload.get("room_id", "") or "")
                self.scene_id = str(payload.get("scene_id", "") or "")
                self.zone_id = str(payload.get("zone_id", "") or "")
                self.perceived_summary = str(payload.get("presentation_hint", "") or "siming_catalyst")
                self.source_candidate_event_id = str(payload.get("causation_id", "") or f"siming:{self.producer_ts}")
                self.clarity_score = 1.0
                self.certainty_score = 1.0

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
                }

        return self._l2.prepare_reasoning_request(
            snapshot=snapshot,
            event=_SimingEvent(actor_id, payload),
            memory_bundle=memory_bundle,
            control_mode=self.get_control_mode(actor_id),
            working_memory_state=working_memory_state,
        )

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
        return suggestion_packet

    def _append_recent_entry(self, entries: list[str], value: str) -> list[str]:
        if value == "":
            return entries
        updated = list(entries)
        updated.append(value)
        return updated[-self._RECENT_HISTORY_LIMIT :]

    def _rehydrate_memory_from_timeline(self) -> None:
        for actor_id, events in self._session_store.list_all_events().items():
            for event in events:
                if isinstance(event, dict):
                    self._memory_store.write_event(event)
