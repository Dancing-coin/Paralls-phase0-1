from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.goal_runtime import CharacterActiveGoalFrame
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.models.goal_runtime import CharacterGoalStateRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
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
from app.character_agent.storage.dynamic_state_store import CharacterDynamicStateStore
from app.character_agent.storage.goal_state_store import CharacterGoalStateStore
from app.services.character_agent_debug_projection import CharacterAgentDebugProjection
from app.models.siming_character_bridge import SimingCharacterCompatibilityInput
from app.world_runtime.continuity import RuntimeContinuityState
from app.world_runtime.scheduling import (
    RuntimeCadencePolicy,
    RuntimePopulationPolicy,
    RuntimeWakeUpCandidate,
    select_schedulable_actor_ids,
)


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
        self._cadence_policy = RuntimeCadencePolicy(
            perception_interval_ms=200,
            cognition_interval_ms=500,
            degraded_mode=False,
        )
        self._population_policy = RuntimePopulationPolicy(
            max_active_actors_per_tick=4,
            wake_up_batch_size=2,
            degraded_population_threshold=6,
            prioritize_continuity_recovery=True,
        )
        self._last_perception_tick_ms: dict[str, int] = {}
        self._last_cognition_tick_ms: dict[str, int] = {}
        self._last_social_request_tick_ms: dict[tuple[str, str, str], int] = {}
        self._continuity_state: dict[str, RuntimeContinuityState] = {}
        self._wake_up_signals: dict[str, dict[str, object]] = {}
        self._scheduling_round_id = 0
        self._scheduling_round_started_at = 0
        self._last_scheduling_tick_ts = 0
        self._last_emitted_scheduling_round_id = 0
        self._session_store = CharacterAgentSessionStore(storage_root=storage_root)
        self._memory_store = CharacterAgentMemoryStore()
        self._dynamic_state_store = CharacterDynamicStateStore()
        self._goal_state_store = CharacterGoalStateStore()
        self._rehydrate_memory_from_timeline()

    def ingest_character_perceived_event(self, event: CharacterPerceivedEvent) -> list[CharacterGoalCommand]:
        if not self.supports_actor(event.actor_id):
            return []
        if self._should_defer_perception(event.actor_id, event.producer_ts):
            snapshot = self._get_snapshot_for_observatory(event.actor_id, event.producer_ts)
            self._queue_observatory_stage_event(
                actor_id=event.actor_id,
                producer_ts=event.producer_ts,
                stage="perception_deferred",
                summary="degraded cadence defers perception refresh",
                focus_target=self._snapshot_focus_target(snapshot),
                intent_label="degraded_mode",
                participants=self._participants_for_actor(event.actor_id, self._snapshot_focus_target(snapshot)),
                detail={
                    "perception_interval_ms": self._cadence_policy.perception_interval_ms,
                    "degraded_mode": self._cadence_policy.degraded_mode,
                },
            )
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
        memory_record_bundle = self.get_memory_record_bundle(event.actor_id)
        working_memory_state = self.get_working_memory_state_record(event.actor_id, snapshot.model_dump())
        self._queue_observatory_snapshot(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            memory_bundle=memory_record_bundle,
        )
        if self._should_defer_cognition(event.actor_id, event.producer_ts):
            self._queue_observatory_stage_event(
                actor_id=event.actor_id,
                producer_ts=event.producer_ts,
                stage="cognition_deferred",
                summary="degraded cadence defers cognition refresh",
                focus_target=self._snapshot_focus_target(snapshot),
                intent_label="degraded_mode",
                participants=self._participants_for_actor(event.actor_id, self._snapshot_focus_target(snapshot)),
                detail={
                    "cognition_interval_ms": self._cadence_policy.cognition_interval_ms,
                    "degraded_mode": self._cadence_policy.degraded_mode,
                },
            )
            return []
        reasoning_request = self._l2.prepare_reasoning_request(
            snapshot=snapshot,
            event=event,
            memory_bundle=memory_record_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._record_reasoning_request(event.actor_id, event.producer_ts, reasoning_request)
        interpretation = self._l2.interpret_perceived_event(
            snapshot,
            event,
            memory_bundle=memory_record_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._apply_cognition_update(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            interpretation=interpretation,
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
            memory_bundle=memory_record_bundle,
        )
        decision = self._l3.select_intent(
            interpretation,
            snapshot=snapshot.model_dump(),
            profile=self._profile_payload(event.actor_id),
            memory_bundle=memory_record_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._record_goal_state_event(event.actor_id, event.producer_ts, decision)
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
            memory_bundle=memory_record_bundle,
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
        if self._should_defer_perception(event.actor_id, event.producer_ts):
            snapshot = self._get_snapshot_for_observatory(event.actor_id, event.producer_ts)
            self._queue_observatory_stage_event(
                actor_id=event.actor_id,
                producer_ts=event.producer_ts,
                stage="perception_deferred",
                summary="degraded cadence defers perception refresh",
                focus_target=self._snapshot_focus_target(snapshot),
                intent_label="degraded_mode",
                participants=self._participants_for_actor(event.actor_id, self._snapshot_focus_target(snapshot)),
                detail={
                    "perception_interval_ms": self._cadence_policy.perception_interval_ms,
                    "degraded_mode": self._cadence_policy.degraded_mode,
                },
            )
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
        memory_record_bundle = self.get_memory_record_bundle(event.actor_id)
        working_memory_state = self.get_working_memory_state_record(event.actor_id, snapshot.model_dump())
        self._queue_observatory_snapshot(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            memory_bundle=memory_record_bundle,
        )
        if self._should_defer_cognition(event.actor_id, event.producer_ts):
            self._queue_observatory_stage_event(
                actor_id=event.actor_id,
                producer_ts=event.producer_ts,
                stage="cognition_deferred",
                summary="degraded cadence defers cognition refresh",
                focus_target=self._snapshot_focus_target(snapshot),
                intent_label="degraded_mode",
                participants=self._participants_for_actor(event.actor_id, self._snapshot_focus_target(snapshot)),
                detail={
                    "cognition_interval_ms": self._cadence_policy.cognition_interval_ms,
                    "degraded_mode": self._cadence_policy.degraded_mode,
                },
            )
            return []
        reasoning_request = self._l2.prepare_reasoning_request(
            snapshot=snapshot,
            event=event,
            memory_bundle=memory_record_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._record_reasoning_request(event.actor_id, event.producer_ts, reasoning_request)
        interpretation = self._l2.interpret_self_body_event(
            snapshot,
            event,
            memory_bundle=memory_record_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._apply_cognition_update(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            interpretation=interpretation,
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
            memory_bundle=memory_record_bundle,
        )
        decision = self._l3.select_intent(
            interpretation,
            snapshot=snapshot.model_dump(),
            profile=self._profile_payload(event.actor_id),
            memory_bundle=memory_record_bundle,
            control_mode=self.get_control_mode(event.actor_id),
            working_memory_state=working_memory_state,
        )
        self._record_goal_state_event(event.actor_id, event.producer_ts, decision)
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
        if self._is_wake_up_input(normalized_payload):
            self._wake_up_signals[actor_id] = {
                "wake_up_requested": True,
                "salience": float(normalized_payload.get("salience_boost", 0.0) or 0.0),
                "producer_ts": int(normalized_payload.get("producer_ts", 0) or 0),
            }
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
        memory_record_bundle = self.get_memory_record_bundle(actor_id)
        working_memory_state = self.get_working_memory_state_record(actor_id, snapshot.model_dump())
        reasoning_request = self._gateway_reasoning_request_for_siming(
            actor_id,
            snapshot,
            normalized_payload,
            memory_record_bundle,
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
            memory_bundle=memory_record_bundle,
        )
        producer_ts = int(normalized_payload.get("producer_ts", 0) or 0)
        wake_up_input = self._is_wake_up_input(normalized_payload)
        if self._should_defer_cognition(actor_id, producer_ts) and not wake_up_input:
            self._queue_observatory_stage_event(
                actor_id=actor_id,
                producer_ts=producer_ts,
                stage="cognition_deferred",
                summary="degraded cadence defers cognition refresh",
                focus_target=self._snapshot_focus_target(snapshot),
                intent_label="degraded_mode",
                participants=self._participants_for_actor(actor_id, self._snapshot_focus_target(snapshot)),
                detail={
                    "cognition_interval_ms": self._cadence_policy.cognition_interval_ms,
                    "degraded_mode": self._cadence_policy.degraded_mode,
                },
            )
            return []
        if wake_up_input:
            self._last_cognition_tick_ms[actor_id] = producer_ts
            self._queue_observatory_stage_event(
                actor_id=actor_id,
                producer_ts=producer_ts,
                stage="wake_up",
                summary="high-salience siming input wakes cognition inside degraded cadence",
                focus_target=self._snapshot_focus_target(snapshot),
                intent_label="high_salience_siming",
                participants=self._participants_for_actor(actor_id, self._snapshot_focus_target(snapshot)),
                detail={
                    "salience_boost": normalized_payload.get("salience_boost"),
                    "reason_scope": str(normalized_payload.get("reason_scope", "") or ""),
                    "pressure_hint": str(normalized_payload.get("pressure_hint", "") or ""),
                },
            )
        interpretation = self._l2.interpret_siming_output(
            snapshot,
            normalized_payload,
            memory_bundle=memory_record_bundle,
            control_mode=self.get_control_mode(actor_id),
            working_memory_state=working_memory_state,
        )
        self._apply_cognition_update(
            actor_id=actor_id,
            producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
            interpretation=interpretation,
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
            memory_bundle=memory_record_bundle,
        )
        decision = self._l3.select_intent(
            interpretation,
            snapshot=snapshot.model_dump(),
            profile=self._profile_payload(actor_id),
            memory_bundle=memory_record_bundle,
            control_mode=self.get_control_mode(actor_id),
            working_memory_state=working_memory_state,
        )
        self._record_goal_state_event(actor_id, int(normalized_payload.get("producer_ts", 0) or 0), decision)
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
            memory_bundle=memory_record_bundle,
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

    def get_memory_record_bundle(self, actor_id: str) -> CharacterMemoryRecordBundle:
        return self._memory_store.retrieval_record_bundle(actor_id)

    def get_working_memory_state(self, actor_id: str, private_snapshot: dict[str, object] | None = None) -> dict[str, object]:
        return self.get_working_memory_state_record(
            actor_id,
            private_snapshot=private_snapshot,
        ).model_dump()

    def get_working_memory_state_record(
        self,
        actor_id: str,
        private_snapshot: dict[str, object] | None = None,
    ):
        return self._memory_store.working_memory_state(
            actor_id,
            private_snapshot=private_snapshot,
            dynamic_state=self.get_dynamic_state_record(actor_id),
        )

    def get_dynamic_state(self, actor_id: str) -> dict[str, object]:
        return self._dynamic_state_store.read(actor_id)

    def get_dynamic_state_record(self, actor_id: str):
        return self._dynamic_state_store.read_record(actor_id)

    def get_goal_state(self, actor_id: str) -> dict[str, object]:
        return self._goal_state_store.read(actor_id)

    def get_goal_state_record(self, actor_id: str) -> CharacterGoalStateRecord | None:
        return self._goal_state_store.read_record(actor_id)

    def get_goal_state_history(self, actor_id: str) -> list[dict[str, object]]:
        return self._goal_state_store.history(actor_id)

    def get_goal_state_history_records(self, actor_id: str) -> list[CharacterGoalStateRecord]:
        return self._goal_state_store.history_records(actor_id)

    def get_runtime_cadence_policy(self) -> dict[str, object]:
        return self._cadence_policy.model_dump()

    def set_runtime_cadence_policy(
        self,
        *,
        perception_interval_ms: int | None = None,
        cognition_interval_ms: int | None = None,
        degraded_mode: bool | None = None,
    ) -> None:
        self._cadence_policy = RuntimeCadencePolicy(
            perception_interval_ms=(
                perception_interval_ms
                if perception_interval_ms is not None
                else self._cadence_policy.perception_interval_ms
            ),
            cognition_interval_ms=(
                cognition_interval_ms
                if cognition_interval_ms is not None
                else self._cadence_policy.cognition_interval_ms
            ),
            degraded_mode=(
                degraded_mode
                if degraded_mode is not None
                else self._cadence_policy.degraded_mode
            ),
        )

    def get_runtime_continuity_state(self, actor_id: str) -> dict[str, object]:
        return self._continuity_state_for(actor_id).model_dump()

    def get_runtime_population_policy(self) -> dict[str, object]:
        return self._population_policy.model_dump()

    def set_runtime_population_policy(
        self,
        *,
        max_active_actors_per_tick: int | None = None,
        wake_up_batch_size: int | None = None,
        degraded_population_threshold: int | None = None,
        prioritize_continuity_recovery: bool | None = None,
    ) -> None:
        self._population_policy = RuntimePopulationPolicy(
            max_active_actors_per_tick=(
                max_active_actors_per_tick
                if max_active_actors_per_tick is not None
                else self._population_policy.max_active_actors_per_tick
            ),
            wake_up_batch_size=(
                wake_up_batch_size
                if wake_up_batch_size is not None
                else self._population_policy.wake_up_batch_size
            ),
            degraded_population_threshold=(
                degraded_population_threshold
                if degraded_population_threshold is not None
                else self._population_policy.degraded_population_threshold
            ),
            prioritize_continuity_recovery=(
                prioritize_continuity_recovery
                if prioritize_continuity_recovery is not None
                else self._population_policy.prioritize_continuity_recovery
            ),
        )

    def get_schedulable_actor_ids(self) -> list[str]:
        return select_schedulable_actor_ids(
            candidates=self._runtime_wake_up_candidates(),
            policy=self._population_policy,
            actor_population=len(self._supported_actor_ids),
        )

    def get_runtime_scheduling_state(self) -> dict[str, object]:
        actor_population = len(self._supported_actor_ids)
        candidates = self._runtime_wake_up_candidates()
        active_actor_ids = select_schedulable_actor_ids(
            candidates=candidates,
            policy=self._population_policy,
            actor_population=actor_population,
        )
        degraded_population = actor_population >= self._population_policy.degraded_population_threshold
        active_limit = (
            self._population_policy.wake_up_batch_size
            if degraded_population
            else self._population_policy.max_active_actors_per_tick
        )
        per_actor: dict[str, dict[str, object]] = {}
        active_actor_reason_map: dict[str, list[str]] = {}
        for candidate in candidates:
            selection_reason_tags = self._scheduling_reason_tags(
                candidate=candidate,
                active_actor_ids=active_actor_ids,
            )
            per_actor[candidate.actor_id] = {
                "actor_selected": candidate.actor_id in active_actor_ids,
                "wake_up_requested": candidate.wake_up_requested,
                "continuity_priority": candidate.continuity_priority,
                "salience": candidate.salience,
                "last_active_ts": candidate.last_active_ts,
                "selection_reason_tags": selection_reason_tags,
            }
            if candidate.actor_id in active_actor_ids:
                active_actor_reason_map[candidate.actor_id] = selection_reason_tags
        round_reason_tags = self._round_reason_tags(
            active_actor_ids=active_actor_ids,
            active_actor_reason_map=active_actor_reason_map,
        )
        lead_actor_id = active_actor_ids[0] if active_actor_ids else ""
        return {
            "round_id": self._scheduling_round_id,
            "round_started_at": self._scheduling_round_started_at,
            "actor_population": actor_population,
            "active_limit": active_limit,
            "degraded_population": degraded_population,
            "active_actor_ids": active_actor_ids,
            "lead_actor_id": lead_actor_id,
            "round_reason_tags": round_reason_tags,
            "round_summary": self._round_summary(
                round_id=self._scheduling_round_id,
                active_actor_ids=active_actor_ids,
                round_reason_tags=round_reason_tags,
            ),
            "active_actor_reason_map": active_actor_reason_map,
            "per_actor": per_actor,
        }

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
        request = self._primary_requested_action(payload)
        request_type = str(request.get("request_type", "") or "")
        target_actor_id = str(request.get("target_actor_id", "") or "")
        if self._should_defer_social_request(actor_id, request_type, target_actor_id, producer_ts):
            snapshot = self._get_snapshot_for_observatory(actor_id, producer_ts)
            self._queue_observatory_stage_event(
                actor_id=actor_id,
                producer_ts=producer_ts,
                stage="cooldown_deferred",
                summary="degraded cooldown defers repeated social-spatial request",
                focus_target=self._snapshot_focus_target(snapshot),
                intent_label="degraded_mode",
                participants=self._participants_for_actor(actor_id, target_actor_id),
                detail={
                    "request_type": request_type,
                    "target_actor_id": target_actor_id,
                    "cooldown_window_ms": self._cadence_policy.cognition_interval_ms,
                },
            )
            return
        continuity = self._continuity_state_for(actor_id)
        previous_target = continuity.ongoing_contact_target
        previous_transition = continuity.last_transition_kind
        continuity.interrupted_action = request_type
        continuity.last_transition_kind = "execution_requested"
        if (
            request_type in {"approach", "follow_target"}
            and target_actor_id != ""
            and previous_transition in {"accepted", "rejected"}
        ):
            continuity.last_transition_kind = "recovering"
        if target_actor_id != "":
            continuity.ongoing_contact_target = target_actor_id
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_agent_execution_request",
            producer_ts=producer_ts,
            payload=payload,
        )
        self._memory_store.write_event(stored)
        self._queue_observatory_snapshot(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=self._get_snapshot_for_observatory(actor_id, producer_ts),
            memory_bundle=self.get_memory_bundle(actor_id),
        )

    def record_settlement_result(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        payload: dict[str, object],
    ) -> None:
        continuity = self._continuity_state_for(actor_id)
        settlement_status = str(payload.get("settlement_status", "") or "")
        action_profile = str(payload.get("action_profile", "") or "")
        continuity.last_transition_kind = settlement_status or str(payload.get("result_type", "") or "")
        if settlement_status in {"accepted", "rejected", "applied"}:
            continuity.interrupted_action = ""
        target_actor_id = str(payload.get("target_actor_id", "") or "")
        if target_actor_id != "":
            continuity.ongoing_contact_target = target_actor_id
        if settlement_status in {"accepted", "rejected"} and action_profile in {"break_contact", "withdraw"}:
            continuity.ongoing_contact_target = ""
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

    def _record_goal_state_event(
        self,
        actor_id: str,
        producer_ts: int,
        decision: CharacterIntentDecision,
    ) -> None:
        previous_goal_state = self._goal_state_store.read(actor_id)
        active_goal_frame = decision.active_goal_frame or self._decision_goal_frame(decision)
        goal_state = active_goal_frame.model_dump()
        changed_fields = [
            key
            for key, value in goal_state.items()
            if previous_goal_state.get(key) != value
        ]
        transition_kind = self._goal_transition_kind(previous_goal_state, goal_state)
        transition_reason_tags = self._goal_transition_reason_tags(
            changed_fields,
            transition_kind,
            previous_goal_state=previous_goal_state,
            goal_state=goal_state,
        )
        event_payload = {
            **goal_state,
            "goal_changed": bool(changed_fields),
            "changed_fields": changed_fields,
            "transition_kind": transition_kind,
            "transition_reason_tags": transition_reason_tags,
        }
        self._goal_state_store.write(
            actor_id,
            CharacterGoalStateRecord(
                actor_id=actor_id,
                transition_kind=transition_kind,
                transition_reason_tags=transition_reason_tags,
                **goal_state,
            ),
        )
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="goal_state_event",
            producer_ts=producer_ts,
            payload=event_payload,
        )
        self._memory_store.write_event(stored)

    def _goal_transition_kind(
        self,
        previous_goal_state: dict[str, object],
        goal_state: dict[str, object],
    ) -> str:
        if not previous_goal_state:
            return "initial"
        previous_primary = str(previous_goal_state.get("primary_goal", "") or "")
        current_primary = str(goal_state.get("primary_goal", "") or "")
        if previous_primary != current_primary:
            return "shifted"
        previous_strategy = str(previous_goal_state.get("mid_term_strategy", "") or "")
        current_strategy = str(goal_state.get("mid_term_strategy", "") or "")
        strategy_changed = previous_strategy != current_strategy
        previous_blockers = previous_goal_state.get("blockers")
        current_blockers = goal_state.get("blockers")
        previous_has_blockers = isinstance(previous_blockers, list) and bool(previous_blockers)
        current_has_blockers = isinstance(current_blockers, list) and bool(current_blockers)
        if strategy_changed and current_has_blockers:
            return "repairing"
        if strategy_changed and previous_has_blockers and not current_has_blockers:
            return "recovering"
        supporting_changed = previous_goal_state.get("supporting_goals") != goal_state.get("supporting_goals")
        blockers_changed = previous_goal_state.get("blockers") != goal_state.get("blockers")
        sources_changed = previous_goal_state.get("goal_sources") != goal_state.get("goal_sources")
        urgency_rank = {"low": 0, "medium": 1, "high": 2}
        previous_urgency = urgency_rank.get(str(previous_goal_state.get("urgency", "low") or "low"), 0)
        current_urgency = urgency_rank.get(str(goal_state.get("urgency", "low") or "low"), 0)
        if current_urgency > previous_urgency:
            return "escalated"
        if current_urgency < previous_urgency:
            return "deescalated"
        if supporting_changed or blockers_changed or sources_changed:
            return "reorganized"
        return "maintained"

    def _goal_transition_reason_tags(
        self,
        changed_fields: list[str],
        transition_kind: str,
        *,
        previous_goal_state: dict[str, object] | None = None,
        goal_state: dict[str, object] | None = None,
    ) -> list[str]:
        tags: list[str] = []
        if "primary_goal" in changed_fields:
            tags.append("primary_goal_changed")
        if "supporting_goals" in changed_fields:
            tags.append("supporting_goals_changed")
        if "blockers" in changed_fields:
            tags.append("blockers_changed")
        if "goal_sources" in changed_fields:
            tags.append("goal_sources_changed")
        if "mid_term_strategy" in changed_fields:
            if transition_kind == "repairing":
                tags.append("strategy_blocked")
            elif transition_kind == "recovering":
                tags.append("strategy_recovered")
            else:
                tags.append("strategy_shifted")
        if "urgency" in changed_fields:
            if transition_kind == "escalated":
                tags.append("urgency_raised")
            elif transition_kind == "deescalated":
                tags.append("urgency_lowered")
            else:
                tags.append("urgency_changed")
        previous_sources = previous_goal_state.get("goal_sources", []) if isinstance(previous_goal_state, dict) else []
        current_sources = goal_state.get("goal_sources", []) if isinstance(goal_state, dict) else []
        if "goal_sources" in changed_fields:
            if "l2_goal_hint:social_signal" in current_sources and "l2_goal_hint:social_signal" not in previous_sources:
                tags.append("social_signal_reappraisal")
            if "knowledge_state" in previous_sources and "knowledge_state" not in current_sources:
                tags.append("knowledge_state_reappraisal")
        return tags

    def _apply_cognition_update(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        interpretation: CharacterInterpretation,
    ) -> None:
        for index, delta in enumerate(interpretation.belief_deltas, start=1):
            if isinstance(delta, CharacterBeliefDelta):
                proposition_key = delta.proposition_key
                proposition = delta.proposition or proposition_key
                state = delta.state
                confidence = delta.confidence
            else:
                proposition_key = str(delta.get("proposition_key", "") or "")
                proposition = str(delta.get("proposition", "") or proposition_key)
                state = str(delta.get("state", "suspected") or "suspected")
                confidence = float(delta.get("confidence", 0.0) or 0.0)
            if proposition_key == "":
                continue
            stored = self._session_store.append_event(
                actor_id=actor_id,
                event_type="knowledge_belief_event",
                producer_ts=producer_ts,
                payload={
                    "proposition_key": proposition_key,
                    "proposition": proposition,
                    "state": state,
                    "confidence": confidence,
                    "event_index": index,
                },
            )
            self._memory_store.write_event(stored)
        for index, delta in enumerate(interpretation.social_deltas, start=1):
            if isinstance(delta, CharacterSocialDelta):
                entity_id = delta.entity_id
                trust_baseline = delta.trust_baseline
                suspicion_baseline = delta.suspicion_baseline
                intimacy = delta.intimacy
                dependency = delta.dependency
                unresolved_tension = delta.unresolved_tension
                shared_secret_refs = list(delta.shared_secret_refs)
            else:
                entity_id = str(delta.get("entity_id", "") or "")
                trust_baseline = float(delta.get("trust_baseline", 0.5) or 0.5)
                suspicion_baseline = float(delta.get("suspicion_baseline", 0.0) or 0.0)
                intimacy = float(delta.get("intimacy", 0.0) or 0.0)
                dependency = float(delta.get("dependency", 0.0) or 0.0)
                unresolved_tension = float(delta.get("unresolved_tension", 0.0) or 0.0)
                shared_secret_refs = list(delta.get("shared_secret_refs", [])) if isinstance(delta.get("shared_secret_refs", []), list) else []
            if entity_id == "":
                continue
            stored = self._session_store.append_event(
                actor_id=actor_id,
                event_type="social_cognition_event",
                producer_ts=producer_ts,
                payload={
                    "entity_id": entity_id,
                    "trust_baseline": trust_baseline,
                    "suspicion_baseline": suspicion_baseline,
                    "intimacy": intimacy,
                    "dependency": dependency,
                    "unresolved_tension": unresolved_tension,
                    "shared_secret_refs": shared_secret_refs,
                    "event_index": index,
                },
            )
            self._memory_store.write_event(stored)
        for index, delta in enumerate(interpretation.higher_order_deltas, start=1):
            if isinstance(delta, CharacterHigherOrderDelta):
                subject_actor_id = delta.subject_actor_id
                proposition_key = delta.proposition_key
                meta_belief = delta.meta_belief
                confidence = delta.confidence
            else:
                subject_actor_id = str(delta.get("subject_actor_id", "") or "")
                proposition_key = str(delta.get("proposition_key", "") or "")
                meta_belief = str(delta.get("meta_belief", "") or "")
                confidence = float(delta.get("confidence", 0.0) or 0.0)
            if subject_actor_id == "" or proposition_key == "" or meta_belief == "":
                continue
            stored = self._session_store.append_event(
                actor_id=actor_id,
                event_type="higher_order_belief_event",
                producer_ts=producer_ts,
                payload={
                    "subject_actor_id": subject_actor_id,
                    "proposition_key": proposition_key,
                    "meta_belief": meta_belief,
                    "confidence": confidence,
                    "event_index": index,
                },
            )
            self._memory_store.write_event(stored)
        delta_payload = interpretation.dynamic_state_delta.as_mapping()
        if delta_payload:
            updated_state = self._dynamic_state_store.merge_delta(actor_id, delta_payload)
            stored = self._session_store.append_event(
                actor_id=actor_id,
                event_type="dynamic_state_event",
                producer_ts=producer_ts,
                payload=updated_state,
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

    def _continuity_state_for(self, actor_id: str) -> RuntimeContinuityState:
        if actor_id not in self._continuity_state:
            self._continuity_state[actor_id] = RuntimeContinuityState(actor_id=actor_id)
        return self._continuity_state[actor_id]

    def _primary_requested_action(self, payload: dict[str, object]) -> dict[str, object]:
        bundle = payload.get("action_request_bundle", {})
        if not isinstance(bundle, dict):
            return {}
        requested_actions = bundle.get("requested_actions", [])
        if not isinstance(requested_actions, list) or not requested_actions:
            return {}
        first = requested_actions[0]
        if not isinstance(first, dict):
            return {}
        return first

    def _gateway_reasoning_request_for_siming(
        self,
        actor_id: str,
        snapshot: object,
        payload: dict[str, object],
        memory_bundle: CharacterMemoryRecordBundle,
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
            profile=self._profile_payload(actor_id),
            memory_bundle=self.get_memory_record_bundle(actor_id),
            working_memory_state=working_memory_state or {},
        )
        latest_goal_state = self._latest_goal_state_payload(actor_id)
        packet["actor_id"] = actor_id
        packet["producer_ts"] = producer_ts
        packet["causation_id"] = f"character_suggestion:{producer_ts}:{actor_id}"
        packet["correlation_id"] = f"character_suggestion:{producer_ts}:{actor_id}"
        packet["transition_kind"] = str(latest_goal_state.get("transition_kind", "") or "")
        packet["transition_reason_tags"] = list(latest_goal_state.get("transition_reason_tags", [])) if isinstance(latest_goal_state.get("transition_reason_tags", []), list) else []
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

    def _profile_payload(self, actor_id: str) -> dict[str, object]:
        return self._profile_registry.get(actor_id).model_dump()

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
        self._refresh_scheduling_round(producer_ts)
        context = self._observatory_context(actor_id)
        self._queue_scheduling_round_event_if_needed(actor_id=actor_id, snapshot=snapshot, producer_ts=producer_ts)
        scheduling_evidence = self._scheduling_evidence(actor_id)
        if scheduling_evidence["actor_selected"]:
            self._queue_observatory_stage_event(
                actor_id=actor_id,
                producer_ts=producer_ts,
                stage="scheduling_state",
                summary="actor selected for active runtime set",
                focus_target=self._snapshot_focus_target(snapshot),
                intent_label="degraded_population" if scheduling_evidence["degraded_population"] else "steady_population",
                participants=self._participants_for_actor(actor_id, self._snapshot_focus_target(snapshot)),
                detail=scheduling_evidence,
            )
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
            cadence_summary=self._observatory_cadence_summary(),
            continuity_summary=self._observatory_continuity_summary(actor_id),
            scheduling_summary=self._observatory_scheduling_summary(),
            dynamic_state_summary=self._observatory_dynamic_state_summary(actor_id),
            dynamic_state=self.get_dynamic_state_record(actor_id),
            goal_state=self._latest_goal_state_payload(actor_id),
        )
        self._pending_observatory_messages.append(
            {
                "message_type": "character_agent_debug_snapshot",
                "payload": state.model_dump(exclude_none=True),
            }
        )

    def _queue_scheduling_round_event_if_needed(
        self,
        *,
        actor_id: str,
        snapshot: CharacterPrivateWorldSnapshot,
        producer_ts: int,
    ) -> None:
        scheduling_state = self.get_runtime_scheduling_state()
        round_id = int(scheduling_state.get("round_id", 0) or 0)
        if round_id <= 0 or round_id == self._last_emitted_scheduling_round_id:
            return
        active_actor_ids = list(scheduling_state.get("active_actor_ids", []))
        if not active_actor_ids:
            return
        lead_actor_id = str(scheduling_state.get("lead_actor_id", "") or actor_id)
        self._queue_observatory_stage_event(
            actor_id=lead_actor_id,
            producer_ts=producer_ts,
            stage="scheduling_round_state",
            summary=str(scheduling_state.get("round_summary", "") or ""),
            focus_target=self._snapshot_focus_target(snapshot),
            intent_label="degraded_population" if bool(scheduling_state.get("degraded_population", False)) else "steady_population",
            participants=active_actor_ids,
            detail=scheduling_state,
        )
        self._last_emitted_scheduling_round_id = round_id

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

    def _observatory_dynamic_state_summary(self, actor_id: str) -> str:
        dynamic_state = self.get_dynamic_state(actor_id)
        if not isinstance(dynamic_state, dict) or not dynamic_state:
            return ""
        ordered_keys = [
            "vigilance_level",
            "distraction_level",
            "stress_load",
            "social_pressure",
            "masking_pressure",
        ]
        parts: list[str] = []
        for key in ordered_keys:
            if key in dynamic_state:
                parts.append(f"{key}={dynamic_state[key]}")
        for key, value in dynamic_state.items():
            if key in ordered_keys:
                continue
            parts.append(f"{key}={value}")
        return "|".join(parts)

    def _observatory_cadence_summary(self) -> str:
        return (
            f"perception={self._cadence_policy.perception_interval_ms}"
            f"|cognition={self._cadence_policy.cognition_interval_ms}"
            f"|degraded={self._cadence_policy.degraded_mode}"
        )

    def _observatory_continuity_summary(self, actor_id: str) -> str:
        continuity = self._continuity_state_for(actor_id)
        return (
            f"contact={continuity.ongoing_contact_target}"
            f"|interrupted={continuity.interrupted_action}"
            f"|transition={continuity.last_transition_kind}"
        )

    def _observatory_scheduling_summary(self) -> str:
        scheduling_evidence = self._scheduling_evidence("")
        return (
            f"population={scheduling_evidence['actor_population']}"
            f"|limit={scheduling_evidence['active_limit']}"
            f"|degraded={scheduling_evidence['degraded_population']}"
            f"|active={','.join(scheduling_evidence['active_actor_ids'])}"
        )

    def _latest_goal_state_payload(self, actor_id: str) -> dict[str, object]:
        record = self.get_goal_state_record(actor_id)
        if record is not None:
            return record.model_dump()
        timeline = self.get_session_timeline(actor_id)
        for entry in reversed(timeline):
            if str(entry.get("event_type", "") or "") == "goal_state_event":
                payload = entry.get("payload", {})
                if isinstance(payload, dict):
                    return dict(payload)
        return {}

    def _should_defer_cognition(self, actor_id: str, producer_ts: int) -> bool:
        if not self._cadence_policy.degraded_mode:
            self._last_cognition_tick_ms[actor_id] = producer_ts
            return False
        previous_tick = self._last_cognition_tick_ms.get(actor_id)
        if previous_tick is None:
            self._last_cognition_tick_ms[actor_id] = producer_ts
            return False
        if producer_ts - previous_tick < self._cadence_policy.cognition_interval_ms:
            return True
        self._last_cognition_tick_ms[actor_id] = producer_ts
        return False

    def _should_defer_perception(self, actor_id: str, producer_ts: int) -> bool:
        if not self._cadence_policy.degraded_mode:
            self._last_perception_tick_ms[actor_id] = producer_ts
            return False
        previous_tick = self._last_perception_tick_ms.get(actor_id)
        if previous_tick is None:
            self._last_perception_tick_ms[actor_id] = producer_ts
            return False
        if producer_ts - previous_tick < self._cadence_policy.perception_interval_ms:
            return True
        self._last_perception_tick_ms[actor_id] = producer_ts
        return False

    def _should_defer_social_request(
        self,
        actor_id: str,
        request_type: str,
        target_actor_id: str,
        producer_ts: int,
    ) -> bool:
        if not self._cadence_policy.degraded_mode:
            if request_type in {"approach", "follow_target", "seek_private_distance", "withdraw", "break_contact"} and target_actor_id != "":
                self._last_social_request_tick_ms[(actor_id, request_type, target_actor_id)] = producer_ts
            return False
        if request_type not in {"approach", "follow_target", "seek_private_distance", "withdraw", "break_contact"}:
            return False
        if target_actor_id == "":
            return False
        key = (actor_id, request_type, target_actor_id)
        previous_tick = self._last_social_request_tick_ms.get(key)
        if previous_tick is None:
            self._last_social_request_tick_ms[key] = producer_ts
            return False
        if producer_ts - previous_tick < self._cadence_policy.cognition_interval_ms:
            return True
        self._last_social_request_tick_ms[key] = producer_ts
        return False

    def _is_wake_up_input(self, payload: dict[str, object]) -> bool:
        salience_boost = payload.get("salience_boost")
        if not isinstance(salience_boost, int | float):
            return False
        return float(salience_boost) >= 0.9

    def _runtime_wake_up_candidates(self) -> list[RuntimeWakeUpCandidate]:
        candidates: list[RuntimeWakeUpCandidate] = []
        for actor_id in sorted(self._supported_actor_ids):
            continuity = self._continuity_state.get(actor_id)
            signal = self._wake_up_signals.get(actor_id, {})
            candidates.append(
                RuntimeWakeUpCandidate(
                    actor_id=actor_id,
                    wake_up_requested=bool(signal.get("wake_up_requested", False)),
                    continuity_priority=self._continuity_priority(continuity),
                    salience=float(signal.get("salience", 0.0) or 0.0),
                    last_active_ts=self._last_activity_ts(actor_id, continuity, signal),
                )
            )
        return candidates

    def _scheduling_evidence(self, actor_id: str) -> dict[str, object]:
        actor_population = len(self._supported_actor_ids)
        degraded_population = actor_population >= self._population_policy.degraded_population_threshold
        active_limit = (
            self._population_policy.wake_up_batch_size
            if degraded_population
            else self._population_policy.max_active_actors_per_tick
        )
        candidates = self._runtime_wake_up_candidates()
        active_actor_ids = select_schedulable_actor_ids(
            candidates=candidates,
            policy=self._population_policy,
            actor_population=actor_population,
        )
        candidate = next((item for item in candidates if item.actor_id == actor_id), None)
        selection_reason_tags = (
            self._scheduling_reason_tags(candidate=candidate, active_actor_ids=active_actor_ids)
            if candidate is not None
            else []
        )
        return {
            "round_id": self._scheduling_round_id,
            "round_started_at": self._scheduling_round_started_at,
            "actor_population": actor_population,
            "active_limit": active_limit,
            "degraded_population": degraded_population,
            "active_actor_ids": active_actor_ids,
            "actor_selected": actor_id in active_actor_ids if actor_id != "" else False,
            "wake_up_requested": candidate.wake_up_requested if candidate is not None else False,
            "continuity_priority": candidate.continuity_priority if candidate is not None else 0,
            "salience": candidate.salience if candidate is not None else 0.0,
            "last_active_ts": candidate.last_active_ts if candidate is not None else 0,
            "selection_reason_tags": selection_reason_tags,
        }

    def _refresh_scheduling_round(self, producer_ts: int) -> None:
        if producer_ts <= 0:
            return
        if producer_ts == self._last_scheduling_tick_ts:
            return
        self._scheduling_round_id += 1
        self._scheduling_round_started_at = producer_ts
        self._last_scheduling_tick_ts = producer_ts

    def _scheduling_reason_tags(
        self,
        *,
        candidate: RuntimeWakeUpCandidate | None,
        active_actor_ids: list[str],
    ) -> list[str]:
        if candidate is None or candidate.actor_id not in active_actor_ids:
            return []
        tags: list[str] = []
        if candidate.continuity_priority >= 3:
            tags.append("continuity_recovery")
        elif candidate.continuity_priority > 0:
            tags.append("continuity_priority")
        if candidate.wake_up_requested:
            tags.append("wake_up_signal")
        if candidate.salience > 0.0:
            tags.append("salience_priority")
        return tags

    def _round_reason_tags(
        self,
        *,
        active_actor_ids: list[str],
        active_actor_reason_map: dict[str, list[str]],
    ) -> list[str]:
        ordered: list[str] = []
        for actor_id in active_actor_ids:
            for tag in active_actor_reason_map[actor_id]:
                if tag not in ordered:
                    ordered.append(tag)
        return ordered

    def _round_summary(
        self,
        *,
        round_id: int,
        active_actor_ids: list[str],
        round_reason_tags: list[str],
    ) -> str:
        if not active_actor_ids:
            return f"round {round_id} selects nobody"
        actor_list = ", ".join(active_actor_ids)
        reason_list = ", ".join(round_reason_tags) if round_reason_tags else "baseline_priority"
        return f"round {round_id} selects {actor_list} because {reason_list}"

    def _continuity_priority(self, continuity: RuntimeContinuityState | None) -> int:
        if continuity is None:
            return 0
        if continuity.last_transition_kind == "recovering":
            return 3
        if continuity.last_transition_kind == "execution_requested":
            return 2
        if continuity.last_transition_kind in {"accepted", "applied"}:
            return 1
        return 0

    def _last_activity_ts(
        self,
        actor_id: str,
        continuity: RuntimeContinuityState | None,
        signal: dict[str, object],
    ) -> int:
        timestamps = [
            int(self._last_cognition_tick_ms.get(actor_id, 0) or 0),
            int(self._last_perception_tick_ms.get(actor_id, 0) or 0),
            int(signal.get("producer_ts", 0) or 0),
        ]
        if continuity is not None and continuity.interrupted_action != "" and continuity.ongoing_contact_target != "":
            timestamps.append(
                int(
                    self._last_social_request_tick_ms.get(
                        (actor_id, continuity.interrupted_action, continuity.ongoing_contact_target),
                        0,
                    )
                    or 0
                )
            )
        return max(timestamps)

    def _decision_goal_frame(self, decision: CharacterIntentDecision) -> CharacterActiveGoalFrame:
        return CharacterActiveGoalFrame(
            primary_goal=decision.primary_goal,
            long_term_goal=decision.long_term_goal,
            mid_term_strategy=decision.mid_term_strategy,
            immediate_goal=decision.immediate_goal,
            supporting_goals=list(decision.supporting_goals),
            blockers=list(decision.blockers),
            goal_sources=list(decision.goal_sources),
            urgency=decision.urgency,
        )
