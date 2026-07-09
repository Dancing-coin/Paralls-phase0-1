from pathlib import Path

from app.character_agent.logic.affect_engine import AffectEngine
from app.character_agent.logic.drift_accumulator import DriftAccumulator
from app.character_agent.logic.drift_promotion_gate import DriftPromotionGate
from app.character_agent.logic.need_tension_engine import NeedTensionEngine
from app.character_agent.models.drift_candidate import DriftCandidateRecord
from app.character_agent.models.need_tension import NeedTensionState
from app.character_agent.profile.registry import CharacterProfileRegistry
from app.character_agent.profile.effective_profile import resolve_effective_profile
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.background_agenda import CharacterBackgroundAgendaEntry, CharacterBackgroundAgendaState
from app.character_agent.models.goal_runtime import CharacterActiveGoalFrame
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.models.goal_runtime import CharacterGoalStateRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.supervision import (
    CharacterBackgroundCognitionResult,
    CharacterBackgroundMode,
    CharacterSupervisionAuthorization,
    CharacterSupervisionConstraints,
    CharacterSupervisionRequest,
    CharacterSupervisionState,
    CharacterUnresolvedTension,
)
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
from app.character_agent.storage.need_tension_store import CharacterNeedTensionStore
from app.character_agent.storage.unresolved_tension_store import CharacterUnresolvedTensionStore
from app.services.character_agent_debug_projection import CharacterAgentDebugProjection
from app.models.siming_character_bridge import SimingCharacterCompatibilityInput
from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle
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
        self._last_background_tick_ms: dict[str, int] = {}
        self._last_social_request_tick_ms: dict[tuple[str, str, str], int] = {}
        self._continuity_state: dict[str, RuntimeContinuityState] = {}
        self._wake_up_signals: dict[str, dict[str, object]] = {}
        self._background_cognition_enabled = False
        self._background_modes = self._build_default_background_modes()
        self._supervision_states: dict[str, CharacterSupervisionState] = {}
        self._background_agenda_states: dict[str, CharacterBackgroundAgendaState] = {}
        self._scheduling_round_id = 0
        self._scheduling_round_started_at = 0
        self._last_scheduling_tick_ts = 0
        self._last_emitted_scheduling_round_id = 0
        self._session_store = CharacterAgentSessionStore(storage_root=storage_root)
        self._memory_store = CharacterAgentMemoryStore()
        self._dynamic_state_store = CharacterDynamicStateStore()
        self._need_tension_store = CharacterNeedTensionStore()
        self._goal_state_store = CharacterGoalStateStore()
        self._unresolved_tension_store = CharacterUnresolvedTensionStore()
        self._need_tension_engine = NeedTensionEngine()
        self._affect_engine = AffectEngine()
        self._drift_accumulator = DriftAccumulator()
        self._drift_promotion_gate = DriftPromotionGate()
        self._rehydrate_runtime_state_from_timeline()

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
        self._refresh_weak_supervision_state(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            reason_summary="weak supervision refreshed after perceived event",
        )
        if event.clarity_score < 0.85 or event.certainty_score < 0.85:
            self._remember_unresolved_tension(
                actor_id=event.actor_id,
                category="ambiguous_signal",
                summary=event.perceived_summary,
                target_ref=self._resolve_target_ref(
                    event.target_actor_id,
                    event.target_object_id,
                    event.target_environment_id,
                ),
                producer_ts=event.producer_ts,
                source_event_id=event.source_candidate_event_id,
                source_stage="character_perceived_event",
                priority=max(0.4, 1.0 - min(event.clarity_score, event.certainty_score)),
            )
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
        effective_profile = self._effective_profile_payload(event.actor_id)
        need_tension_event = self._need_tension_event_payload(event)
        need_delta = self._need_tension_engine.evaluate(
            effective_profile=effective_profile,
            event=need_tension_event,
        )
        need_tension_state = self._need_tension_store.merge_delta(
            event.actor_id,
            self._need_tension_delta_payload(need_delta),
        )
        dynamic_delta: dict[str, object] = dict(
            self._affect_engine.evaluate(
                effective_profile=effective_profile,
                need_delta=need_delta,
            ).get("dynamic_state_delta", {})
        )
        if dynamic_delta:
            self._dynamic_state_store.merge_delta(event.actor_id, dynamic_delta)
        memory_record_bundle = self.get_memory_record_bundle(event.actor_id)
        working_memory_state = self.get_working_memory_state_record(event.actor_id, snapshot.model_dump())
        self._queue_observatory_snapshot(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            memory_bundle=memory_record_bundle,
        )
        current_goal_state = self.get_goal_state(event.actor_id)
        goal_state_history = self.get_goal_state_history(event.actor_id)
        supervision_state = self.get_supervision_state(event.actor_id)
        unresolved_tensions = self.get_unresolved_tensions(event.actor_id)
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
            current_goal_state=current_goal_state,
            goal_state_history=goal_state_history,
            supervision_state=supervision_state,
            unresolved_tensions=unresolved_tensions,
            background_agenda_state=self.get_background_agenda_state(event.actor_id),
            effective_profile=effective_profile,
            need_tension_state=need_tension_state,
        )
        self._record_reasoning_request(event.actor_id, event.producer_ts, reasoning_request)
        interpretation = self._interpret_with_continuity_floor(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            control_mode=self.get_control_mode(event.actor_id),
            source_stage="character_perceived_event",
            run_model=lambda: self._l2.interpret_perceived_event(
                snapshot,
                event,
                memory_bundle=memory_record_bundle,
                control_mode=self.get_control_mode(event.actor_id),
                working_memory_state=working_memory_state,
                current_goal_state=current_goal_state,
                goal_state_history=goal_state_history,
                supervision_state=supervision_state,
                unresolved_tensions=unresolved_tensions,
                background_agenda_state=self.get_background_agenda_state(event.actor_id),
                effective_profile=effective_profile,
                need_tension_state=need_tension_state,
            ),
        )
        if interpretation.cognition_status == "model":
            self._apply_cognition_update(
                actor_id=event.actor_id,
                producer_ts=event.producer_ts,
                interpretation=interpretation,
            )
            self._observe_and_record_drift_promotion(
                actor_id=event.actor_id,
                producer_ts=event.producer_ts,
                effective_profile=effective_profile,
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
        decision = self._select_intent_with_continuity_floor(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            interpretation=interpretation,
            control_mode=self.get_control_mode(event.actor_id),
            source_stage="character_perceived_event",
            run_model=lambda: self._l3.select_intent(
                interpretation,
                snapshot=snapshot.model_dump(),
                profile=self._profile_payload(event.actor_id),
                memory_bundle=memory_record_bundle,
                control_mode=self.get_control_mode(event.actor_id),
                working_memory_state=working_memory_state,
                current_goal_state=current_goal_state,
                goal_state_history=goal_state_history,
                supervision_state=supervision_state,
                unresolved_tensions=unresolved_tensions,
                background_agenda_state=self.get_background_agenda_state(event.actor_id),
            ),
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
            packet = (
                self._continuity_floor_suggestion_packet(
                    actor_id=event.actor_id,
                    producer_ts=event.producer_ts,
                    interpretation=interpretation,
                    decision=decision,
                )
                if decision.planning_status == "continuity_floor"
                else self._planner_suggestion_packet(
                    actor_id=event.actor_id,
                    producer_ts=event.producer_ts,
                    interpretation=interpretation,
                    working_memory_state=working_memory_state,
                )
            )
            self._pending_suggestions.append(packet)
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

    def is_valid_background_mode(self, mode: str) -> bool:
        return mode in {"off", "passive", "active", "quiet"}

    def get_background_cognition_enabled(self) -> bool:
        return self._background_cognition_enabled

    def set_background_cognition_enabled(self, enabled: bool) -> None:
        self._background_cognition_enabled = bool(enabled)

    def get_background_mode(self, actor_id: str) -> CharacterBackgroundMode:
        return self._background_modes.get(actor_id, "passive")

    def set_background_mode(self, actor_id: str, mode: CharacterBackgroundMode) -> None:
        if not self.supports_actor(actor_id):
            raise ValueError(f"unsupported actor_id: {actor_id}")
        if not self.is_valid_background_mode(mode):
            raise ValueError(f"unsupported background mode: {mode}")
        self._background_modes[actor_id] = mode

    def get_supervision_state(self, actor_id: str) -> dict[str, object]:
        return self._supervision_state_for(actor_id).model_dump()

    def get_supervision_state_record(self, actor_id: str) -> CharacterSupervisionState:
        return self._supervision_state_for(actor_id).model_copy(deep=True)

    def request_supervision_upgrade(
        self,
        *,
        actor_id: str,
        requested_level: str,
        reason_code: str,
        reason_summary: str,
        requested_constraints: dict[str, object] | CharacterSupervisionConstraints | None = None,
        requested_duration_ms: int = 0,
        producer_ts: int = 0,
    ) -> CharacterSupervisionRequest:
        if requested_level not in {"medium", "strong"}:
            raise ValueError(f"unsupported requested supervision level: {requested_level}")
        request = CharacterSupervisionRequest(
            request_id=f"supervision_request:{actor_id}:{producer_ts}:{requested_level}",
            actor_id=actor_id,
            requested_level=requested_level,
            reason_code=reason_code,
            reason_summary=reason_summary,
            requested_constraints=self._constraints_model(requested_constraints),
            requested_duration_ms=requested_duration_ms,
            producer_ts=producer_ts,
            causation_id=f"supervision_request:{actor_id}:{producer_ts}",
            correlation_id=f"supervision_request:{actor_id}:{producer_ts}",
        )
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_supervision_request",
            producer_ts=producer_ts,
            payload=request.model_dump(),
        )
        self._memory_store.write_event(stored)
        return request

    def apply_supervision_authorization(
        self,
        authorization: dict[str, object] | CharacterSupervisionAuthorization,
    ) -> CharacterSupervisionState:
        record = self._authorization_model(authorization)
        state = CharacterSupervisionState(
            actor_id=record.actor_id,
            current_level=record.approved_level,
            source="strategy_authorized" if record.approved_by == "strategy_service" else "gm_override",
            active_constraints=record.constraints,
            entered_at_ts=record.effective_from_ts,
            expires_at_ts=record.expires_at_ts,
            last_refresh_ts=record.producer_ts or record.effective_from_ts,
            last_reason_summary=record.approval_reason,
        )
        self._supervision_states[record.actor_id] = state
        if self.supports_actor(record.actor_id):
            self._background_modes[record.actor_id] = state.active_constraints.background_mode
        stored = self._session_store.append_event(
            actor_id=record.actor_id,
            event_type="character_supervision_authorization",
            producer_ts=record.producer_ts or record.effective_from_ts,
            payload=record.model_dump(),
        )
        self._memory_store.write_event(stored)
        return state.model_copy(deep=True)

    def clear_supervision_authorization(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        reason: str,
    ) -> CharacterSupervisionState:
        state = self._supervision_state_for(actor_id)
        if state.current_level == "weak" and state.source == "siming_weak_default":
            return state.model_copy(deep=True)
        refreshed = CharacterSupervisionState(
            actor_id=actor_id,
            current_level="weak",
            source="siming_weak_default",
            active_constraints=self._weak_supervision_constraints_for(actor_id, producer_ts),
            entered_at_ts=producer_ts,
            expires_at_ts=0,
            last_refresh_ts=producer_ts,
            last_reason_summary=reason,
        )
        self._supervision_states[actor_id] = refreshed
        if self.supports_actor(actor_id):
            self._background_modes[actor_id] = refreshed.active_constraints.background_mode
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_supervision_cleared",
            producer_ts=producer_ts,
            payload=refreshed.model_dump(),
        )
        self._memory_store.write_event(stored)
        return refreshed.model_copy(deep=True)

    def get_unresolved_tensions(self, actor_id: str) -> list[dict[str, object]]:
        return self._unresolved_tension_store.recall(actor_id)

    def get_background_agenda_state(self, actor_id: str) -> dict[str, object]:
        state = self._background_agenda_states.get(actor_id)
        return state.model_dump() if state is not None else {}

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
        self._refresh_weak_supervision_state(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            reason_summary="weak supervision refreshed after self-body event",
        )
        self._remember_unresolved_tension(
            actor_id=event.actor_id,
            category="body_strain",
            summary=event.perceived_summary,
            target_ref="self",
            producer_ts=event.producer_ts,
            source_event_id=event.source_body_result_id,
            source_stage="self_body_perceived_event",
            priority=0.7,
        )
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
        current_goal_state = self.get_goal_state(event.actor_id)
        goal_state_history = self.get_goal_state_history(event.actor_id)
        supervision_state = self.get_supervision_state(event.actor_id)
        unresolved_tensions = self.get_unresolved_tensions(event.actor_id)
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
            current_goal_state=current_goal_state,
            goal_state_history=goal_state_history,
            supervision_state=supervision_state,
            unresolved_tensions=unresolved_tensions,
            background_agenda_state=self.get_background_agenda_state(event.actor_id),
        )
        self._record_reasoning_request(event.actor_id, event.producer_ts, reasoning_request)
        interpretation = self._interpret_with_continuity_floor(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            control_mode=self.get_control_mode(event.actor_id),
            source_stage="self_body_perceived_event",
            run_model=lambda: self._l2.interpret_self_body_event(
                snapshot,
                event,
                memory_bundle=memory_record_bundle,
                control_mode=self.get_control_mode(event.actor_id),
                working_memory_state=working_memory_state,
                current_goal_state=current_goal_state,
                goal_state_history=goal_state_history,
                supervision_state=supervision_state,
                unresolved_tensions=unresolved_tensions,
                background_agenda_state=self.get_background_agenda_state(event.actor_id),
            ),
        )
        if interpretation.cognition_status == "model":
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
        decision = self._select_intent_with_continuity_floor(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            interpretation=interpretation,
            control_mode=self.get_control_mode(event.actor_id),
            source_stage="self_body_perceived_event",
            run_model=lambda: self._l3.select_intent(
                interpretation,
                snapshot=snapshot.model_dump(),
                profile=self._profile_payload(event.actor_id),
                memory_bundle=memory_record_bundle,
                control_mode=self.get_control_mode(event.actor_id),
                working_memory_state=working_memory_state,
                current_goal_state=current_goal_state,
                goal_state_history=goal_state_history,
                supervision_state=supervision_state,
                unresolved_tensions=unresolved_tensions,
                background_agenda_state=self.get_background_agenda_state(event.actor_id),
            ),
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
            packet = (
                self._continuity_floor_suggestion_packet(
                    actor_id=event.actor_id,
                    producer_ts=event.producer_ts,
                    interpretation=interpretation,
                    decision=decision,
                )
                if decision.planning_status == "continuity_floor"
                else self._planner_suggestion_packet(
                    actor_id=event.actor_id,
                    producer_ts=event.producer_ts,
                    interpretation=interpretation,
                    working_memory_state=working_memory_state,
                )
            )
            self._pending_suggestions.append(packet)
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
        self._refresh_weak_supervision_from_siming(
            actor_id=actor_id,
            payload=normalized_payload,
            producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
        )
        pressure_hint = str(normalized_payload.get("pressure_hint", "") or "").strip()
        if pressure_hint != "":
            self._remember_unresolved_tension(
                actor_id=actor_id,
                category="siming_pressure",
                summary=pressure_hint,
                target_ref=str(normalized_payload.get("target_environment_id", "") or normalized_payload.get("target_object_id", "") or normalized_payload.get("target_actor_id", "") or ""),
                producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
                source_event_id=str(normalized_payload.get("message_id", "") or ""),
                source_stage="siming_output_event",
                priority=0.8,
            )
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
        memory_record_bundle = self.get_memory_record_bundle(actor_id)
        working_memory_state = self.get_working_memory_state_record(actor_id, snapshot.model_dump())
        current_goal_state = self.get_goal_state(actor_id)
        goal_state_history = self.get_goal_state_history(actor_id)
        supervision_state = self.get_supervision_state(actor_id)
        unresolved_tensions = self.get_unresolved_tensions(actor_id)
        reasoning_request = self._gateway_reasoning_request_for_siming(
            actor_id,
            snapshot,
            normalized_payload,
            memory_record_bundle,
            working_memory_state,
            current_goal_state,
            goal_state_history,
            supervision_state,
            unresolved_tensions,
            self.get_background_agenda_state(actor_id),
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
        interpretation = self._interpret_with_continuity_floor(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            control_mode=self.get_control_mode(actor_id),
            source_stage="siming_output_event",
            run_model=lambda: self._l2.interpret_siming_output(
                snapshot,
                normalized_payload,
                memory_bundle=memory_record_bundle,
                control_mode=self.get_control_mode(actor_id),
                working_memory_state=working_memory_state,
                current_goal_state=current_goal_state,
                goal_state_history=goal_state_history,
                supervision_state=supervision_state,
                unresolved_tensions=unresolved_tensions,
                background_agenda_state=self.get_background_agenda_state(actor_id),
            ),
        )
        if interpretation.cognition_status == "model":
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
        decision = self._select_intent_with_continuity_floor(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            interpretation=interpretation,
            control_mode=self.get_control_mode(actor_id),
            source_stage="siming_output_event",
            run_model=lambda: self._l3.select_intent(
                interpretation,
                snapshot=snapshot.model_dump(),
                profile=self._profile_payload(actor_id),
                memory_bundle=memory_record_bundle,
                control_mode=self.get_control_mode(actor_id),
                working_memory_state=working_memory_state,
                current_goal_state=current_goal_state,
                goal_state_history=goal_state_history,
                supervision_state=supervision_state,
                unresolved_tensions=unresolved_tensions,
                background_agenda_state=self.get_background_agenda_state(actor_id),
            ),
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
            packet = (
                self._continuity_floor_suggestion_packet(
                    actor_id=actor_id,
                    producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
                    interpretation=interpretation,
                    decision=decision,
                )
                if decision.planning_status == "continuity_floor"
                else self._planner_suggestion_packet(
                    actor_id=actor_id,
                    producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
                    interpretation=interpretation,
                    working_memory_state=working_memory_state,
                )
            )
            self._pending_suggestions.append(packet)
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

    def ingest_canonical_percept_bundle(self, bundle: CanonicalPerceptBundle) -> CharacterPrivateWorldSnapshot:
        if not self.supports_actor(bundle.subject_id):
            raise ValueError(f"unsupported actor_id: {bundle.subject_id}")
        snapshot = self._l1.apply_canonical_percept_bundle(bundle)
        stored = self._session_store.append_event(
            actor_id=bundle.subject_id,
            event_type="canonical_percept_bundle",
            producer_ts=snapshot.producer_ts,
            payload=bundle.model_dump(),
        )
        self._memory_store.write_event(stored)
        self._queue_observatory_stage_event(
            actor_id=bundle.subject_id,
            producer_ts=snapshot.producer_ts,
            stage="canonical_percept_bundle_consumed",
            summary="L1 world fact bundle consumed into private snapshot",
            focus_target=self._snapshot_focus_target(snapshot),
            intent_label="l1_world_fact",
            participants=self._participants_for_actor(bundle.subject_id, self._snapshot_focus_target(snapshot)),
            detail=bundle.model_dump(),
        )
        self._queue_observatory_snapshot(
            actor_id=bundle.subject_id,
            producer_ts=snapshot.producer_ts,
            snapshot=snapshot,
            memory_bundle=self.get_memory_bundle(bundle.subject_id),
        )
        return snapshot

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

    def get_need_tension_state(self, actor_id: str) -> dict[str, object]:
        return self._need_tension_store.read(actor_id)

    def get_need_tension_state_record(self, actor_id: str) -> NeedTensionState:
        return self._need_tension_store.read_record(actor_id)

    def get_goal_state(self, actor_id: str) -> dict[str, object]:
        return self._goal_state_store.read(actor_id)

    def get_goal_state_record(self, actor_id: str) -> CharacterGoalStateRecord | None:
        return self._goal_state_store.read_record(actor_id)

    def get_goal_state_history(self, actor_id: str) -> list[dict[str, object]]:
        return self._goal_state_store.history(actor_id)

    def get_goal_state_history_records(self, actor_id: str) -> list[CharacterGoalStateRecord]:
        return self._goal_state_store.history_records(actor_id)

    def run_background_cognition_tick(
        self,
        *,
        actor_id: str,
        producer_ts: int,
    ) -> CharacterBackgroundCognitionResult:
        if not self.supports_actor(actor_id):
            return CharacterBackgroundCognitionResult(
                actor_id=actor_id,
                ran=False,
                producer_ts=producer_ts,
                reason="unsupported_actor",
            )
        supervision_state = self._supervision_state_for(actor_id)
        background_mode = self.get_background_mode(actor_id)
        if not self._background_cognition_enabled:
            return CharacterBackgroundCognitionResult(
                actor_id=actor_id,
                ran=False,
                producer_ts=producer_ts,
                reason="background_disabled",
                current_level=supervision_state.current_level,
            )
        if background_mode == "off":
            return CharacterBackgroundCognitionResult(
                actor_id=actor_id,
                ran=False,
                producer_ts=producer_ts,
                reason="actor_background_off",
                current_level=supervision_state.current_level,
            )
        if not supervision_state.active_constraints.allow_background_loop:
            return CharacterBackgroundCognitionResult(
                actor_id=actor_id,
                ran=False,
                producer_ts=producer_ts,
                reason="supervision_blocked_background_loop",
                current_level=supervision_state.current_level,
            )
        if not self._background_tick_due(actor_id=actor_id, producer_ts=producer_ts):
            return CharacterBackgroundCognitionResult(
                actor_id=actor_id,
                ran=False,
                producer_ts=producer_ts,
                reason="tick_not_due",
                current_level=supervision_state.current_level,
            )
        snapshot = self.get_private_snapshot(actor_id)
        if snapshot is None:
            return CharacterBackgroundCognitionResult(
                actor_id=actor_id,
                ran=False,
                producer_ts=producer_ts,
                reason="missing_snapshot",
                current_level=supervision_state.current_level,
            )
        memory_record_bundle = self.get_memory_record_bundle(actor_id)
        working_memory_state = self.get_working_memory_state_record(actor_id, snapshot.model_dump())
        current_goal_state = self.get_goal_state(actor_id)
        goal_state_history = self.get_goal_state_history(actor_id)
        unresolved_tensions = self.get_unresolved_tensions(actor_id)
        background_agenda_state = self.get_background_agenda_state(actor_id)
        background_payload = self._background_reappraisal_payload(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            current_goal_state=current_goal_state,
            unresolved_tensions=unresolved_tensions,
            supervision_state=supervision_state.model_dump(),
        )
        reasoning_request = self._l2.prepare_reasoning_request(
            snapshot=snapshot,
            event=self._runtime_payload_event(actor_id, background_payload),
            memory_bundle=memory_record_bundle,
            control_mode=self.get_control_mode(actor_id),
            working_memory_state=working_memory_state,
            current_goal_state=current_goal_state,
            goal_state_history=goal_state_history,
            supervision_state=supervision_state.model_dump(),
            unresolved_tensions=unresolved_tensions,
            background_agenda_state=background_agenda_state,
        )
        self._record_reasoning_request(actor_id, producer_ts, reasoning_request)
        interpretation = self._interpret_with_continuity_floor(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            control_mode=self.get_control_mode(actor_id),
            source_stage="background_cognition_tick",
            run_model=lambda: self._l2.interpret_background_state(
                snapshot,
                background_payload,
                memory_bundle=memory_record_bundle,
                control_mode=self.get_control_mode(actor_id),
                working_memory_state=working_memory_state,
                current_goal_state=current_goal_state,
                goal_state_history=goal_state_history,
                supervision_state=supervision_state.model_dump(),
                unresolved_tensions=unresolved_tensions,
                background_agenda_state=background_agenda_state,
            ),
        )
        if interpretation.cognition_status == "model":
            self._apply_cognition_update(
                actor_id=actor_id,
                producer_ts=producer_ts,
                interpretation=interpretation,
            )
        self._record_interpretation_event(actor_id, producer_ts, interpretation)
        decision = self._select_intent_with_continuity_floor(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            interpretation=interpretation,
            control_mode=self.get_control_mode(actor_id),
            source_stage="background_cognition_tick",
            run_model=lambda: self._l3.select_intent(
                interpretation,
                snapshot=snapshot.model_dump(),
                profile=self._profile_payload(actor_id),
                memory_bundle=memory_record_bundle,
                control_mode=self.get_control_mode(actor_id),
                working_memory_state=working_memory_state,
                current_goal_state=current_goal_state,
                goal_state_history=goal_state_history,
                supervision_state=supervision_state.model_dump(),
                unresolved_tensions=unresolved_tensions,
                background_agenda_state=background_agenda_state,
            ),
        )
        self._record_goal_state_event(actor_id, producer_ts, decision)
        self._last_background_tick_ms[actor_id] = producer_ts
        agenda_state = self._build_background_agenda_state(
            actor_id=actor_id,
            producer_ts=producer_ts,
            interpretation=interpretation,
            decision=decision,
            supervision_state=supervision_state.model_dump(),
            unresolved_tensions=unresolved_tensions,
        )
        self._background_agenda_states[actor_id] = agenda_state
        self._record_background_cognition_event(
            actor_id=actor_id,
            producer_ts=producer_ts,
            background_payload=background_payload,
            interpretation=interpretation,
            decision=decision,
            supervision_state=supervision_state.model_dump(),
            unresolved_tensions=unresolved_tensions,
            agenda_state=agenda_state,
        )
        self._queue_observatory_stage_event(
            actor_id=actor_id,
            producer_ts=producer_ts,
            stage="background_cognition_tick",
            summary=interpretation.interpreted_summary,
            focus_target=str(interpretation.attention_target or self._snapshot_focus_target(snapshot)),
            intent_label=decision.selected_intent,
            participants=self._participants_for_actor(actor_id, str(interpretation.attention_target or self._snapshot_focus_target(snapshot))),
            detail={
                "background_mode": background_mode,
                "supervision_state": supervision_state.model_dump(),
                "background_payload": background_payload,
                "interpretation": interpretation.model_dump(),
                "decision": decision.model_dump(),
                "background_agenda_state": agenda_state.model_dump(),
            },
        )
        self._queue_observatory_snapshot(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            memory_bundle=memory_record_bundle,
        )
        return CharacterBackgroundCognitionResult(
            actor_id=actor_id,
            ran=True,
            producer_ts=producer_ts,
            reason="background_tick_completed",
            interpretation_summary=interpretation.interpreted_summary,
            selected_intent=decision.selected_intent,
            current_level=supervision_state.current_level,
        )

    def run_background_cognition_ticks(self, producer_ts: int) -> list[CharacterBackgroundCognitionResult]:
        return [
            self.run_background_cognition_tick(actor_id=actor_id, producer_ts=producer_ts)
            for actor_id in sorted(self._supported_actor_ids)
            if self.get_background_mode(actor_id) in {"active", "quiet"}
        ]

    def run_scheduled_background_cognition_ticks(self, producer_ts: int) -> list[CharacterBackgroundCognitionResult]:
        return [
            self.run_background_cognition_tick(actor_id=actor_id, producer_ts=producer_ts)
            for actor_id in self.get_schedulable_actor_ids()
            if self.get_background_mode(actor_id) in {"active", "quiet"}
        ]

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
        self._refresh_weak_supervision_state(
            actor_id=actor_id,
            producer_ts=producer_ts,
            reason_summary="weak supervision refreshed after settlement result",
        )
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
                constraint_summary = str(payload.get("constraint_summary", "") or "")
                snapshot.recent_constraint_results = self._append_recent_entry(
                    snapshot.recent_constraint_results,
                    constraint_summary,
                )
                self._remember_unresolved_tension(
                    actor_id=actor_id,
                    category="constraint_result",
                    summary=constraint_summary or result_type or "constraint_result",
                    target_ref=str(payload.get("target_actor_id", "") or payload.get("target_object_id", "") or payload.get("target_environment_id", "") or ""),
                    producer_ts=producer_ts,
                    source_event_id=str(payload.get("result_id", "") or ""),
                    source_stage="settlement_result",
                    priority=0.85,
                )
            else:
                change_summary = str(payload.get("change_summary", "") or result_type or "world_result")
                snapshot.recent_world_changes = self._append_recent_entry(
                    snapshot.recent_world_changes,
                    change_summary,
                )
                self._remember_unresolved_tension(
                    actor_id=actor_id,
                    category="world_outcome",
                    summary=change_summary,
                    target_ref=str(payload.get("target_actor_id", "") or payload.get("target_object_id", "") or payload.get("target_environment_id", "") or ""),
                    producer_ts=producer_ts,
                    source_event_id=str(payload.get("result_id", "") or ""),
                    source_stage="settlement_result",
                    priority=0.55,
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
        self._refresh_weak_supervision_state(
            actor_id=actor_id,
            producer_ts=producer_ts,
            reason_summary="weak supervision refreshed after dialogue response",
        )
        snapshot = self._l1.get_snapshot(actor_id)
        if snapshot is not None:
            dialogue_summary = str(payload.get("content", "") or payload.get("summary", "") or "").strip()
            snapshot.recent_world_changes = self._append_recent_entry(
                snapshot.recent_world_changes,
                "dialogue_response:%s" % dialogue_summary if dialogue_summary != "" else "dialogue_response",
            )
            if dialogue_summary != "":
                self._remember_unresolved_tension(
                    actor_id=actor_id,
                    category="dialogue_aftereffect",
                    summary=dialogue_summary,
                    target_ref=str(payload.get("target_actor_id", "") or ""),
                    producer_ts=producer_ts,
                    source_event_id=str(payload.get("response_id", "") or ""),
                    source_stage="dialogue_response",
                    priority=0.45,
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

    def _interpret_with_continuity_floor(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        snapshot: CharacterPrivateWorldSnapshot,
        control_mode: str,
        source_stage: str,
        run_model,
    ) -> CharacterInterpretation:
        try:
            return run_model()
        except Exception as exc:
            interpretation = self._continuity_floor_interpretation(
                actor_id=actor_id,
                snapshot=snapshot,
                control_mode=control_mode,
                error=exc,
            )
            self._queue_observatory_stage_event(
                actor_id=actor_id,
                producer_ts=producer_ts,
                stage="cognition_unavailable",
                summary=interpretation.interpreted_summary,
                focus_target=self._snapshot_focus_target(snapshot),
                intent_label="continuity_floor",
                participants=self._participants_for_actor(actor_id, self._snapshot_focus_target(snapshot)),
                detail={
                    "source_stage": source_stage,
                    "error": str(exc),
                    "cognition_status": interpretation.cognition_status,
                    "fallback_mode": interpretation.fallback_mode,
                },
            )
            return interpretation

    def _select_intent_with_continuity_floor(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        control_mode: str,
        source_stage: str,
        run_model,
    ) -> CharacterIntentDecision:
        try:
            return run_model()
        except Exception as exc:
            decision = self._continuity_floor_decision(
                actor_id=actor_id,
                snapshot=snapshot,
                interpretation=interpretation,
                control_mode=control_mode,
                error=exc,
            )
            self._queue_observatory_stage_event(
                actor_id=actor_id,
                producer_ts=producer_ts,
                stage="planning_unavailable",
                summary=decision.rationale,
                focus_target=str(interpretation.attention_target or self._snapshot_focus_target(snapshot)),
                intent_label="continuity_floor",
                participants=self._participants_for_actor(actor_id, str(interpretation.attention_target or self._snapshot_focus_target(snapshot))),
                detail={
                    "source_stage": source_stage,
                    "error": str(exc),
                    "planning_status": decision.planning_status,
                    "fallback_mode": decision.fallback_mode,
                    "selected_intent": decision.selected_intent,
                },
            )
            return decision

    def _continuity_floor_interpretation(
        self,
        *,
        actor_id: str,
        snapshot: CharacterPrivateWorldSnapshot,
        control_mode: str,
        error: Exception,
    ) -> CharacterInterpretation:
        risk_level = "medium" if self._continuity_floor_requires_guarding(snapshot) else "low"
        return CharacterInterpretation(
            actor_id=actor_id,
            interpreted_summary="model cognition unavailable; continuity floor active",
            interpretation_type="cognition_unavailable",
            salience_score=max(0.0, float(snapshot.attention_pressure or 0.0)),
            ambiguity_level="high",
            risk_level=risk_level,
            opportunity_level="low",
            attention_target=self._snapshot_focus_target(snapshot) or None,
            inner_prompt_candidate="continuity_floor",
            reasoning_trace_summary=f"continuity_floor:{control_mode}:{type(error).__name__}",
            cognition_status="continuity_floor",
            fallback_mode="continuity_floor",
        )

    def _continuity_floor_decision(
        self,
        *,
        actor_id: str,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        control_mode: str,
        error: Exception,
    ) -> CharacterIntentDecision:
        selected_intent = self._continuity_floor_intent(
            actor_id=actor_id,
            snapshot=snapshot,
            control_mode=control_mode,
        )
        active_goal_frame = self._continuity_floor_goal_frame(actor_id)
        return CharacterIntentDecision(
            actor_id=actor_id,
            selected_intent=selected_intent,
            persona_passed=False,
            logic_passed=False,
            gain_loss_passed=False,
            rationale=f"planning unavailable; continuity floor selects {selected_intent} ({type(error).__name__})",
            primary_goal=active_goal_frame.primary_goal,
            long_term_goal=active_goal_frame.long_term_goal,
            mid_term_strategy=active_goal_frame.mid_term_strategy,
            immediate_goal=active_goal_frame.immediate_goal,
            supporting_goals=list(active_goal_frame.supporting_goals),
            blockers=list(active_goal_frame.blockers),
            goal_sources=list(active_goal_frame.goal_sources),
            urgency=active_goal_frame.urgency,
            active_goal_frame=active_goal_frame,
            planning_status="continuity_floor",
            fallback_mode="continuity_floor",
        )

    def _continuity_floor_intent(
        self,
        *,
        actor_id: str,
        snapshot: CharacterPrivateWorldSnapshot,
        control_mode: str,
    ) -> str:
        if control_mode == "player_priority_assisted":
            return "stay_silent"
        if self._continuity_floor_requires_guarding(snapshot):
            continuity = self._continuity_state_for(actor_id)
            if continuity.ongoing_contact_target != "":
                return "withdraw"
            return "self_protect"
        return "observe"

    def _continuity_floor_requires_guarding(self, snapshot: CharacterPrivateWorldSnapshot) -> bool:
        return (
            bool(snapshot.body_state_hints)
            or bool(snapshot.recent_constraint_results)
            or snapshot.vigilance_level == "elevated"
            or snapshot.distraction_level == "elevated"
        )

    def _continuity_floor_goal_frame(self, actor_id: str) -> CharacterActiveGoalFrame:
        existing = self.get_goal_state_record(actor_id)
        if existing is not None:
            payload = existing.model_dump()
            payload.pop("actor_id", None)
            payload.pop("transition_kind", None)
            payload.pop("transition_reason_tags", None)
            return CharacterActiveGoalFrame(**payload)
        return CharacterActiveGoalFrame(
            primary_goal="preserve_continuity",
            long_term_goal="preserve_continuity",
            mid_term_strategy="hold_position",
            immediate_goal="preserve_continuity",
            supporting_goals=[],
            blockers=["model_unavailable"],
            goal_sources=["continuity_floor"],
            urgency="low",
            dominant_goal_id="goal_preserve_continuity",
            preserved_goal_ids=[],
            suppressed_goal_ids=[],
            goal_arbitration_summary="model-unavailable continuity floor keeps only a low-risk continuity goal active",
            goal_portfolio=[
                {
                    "goal_id": "goal_preserve_continuity",
                    "goal": "preserve_continuity",
                    "horizon": "long",
                    "status": "active",
                    "priority": 0.5,
                    "urgency": "low",
                    "source": "continuity_floor",
                    "blockers": ["model_unavailable"],
                    "supporting_evidence": ["continuity_floor"],
                }
            ],
        )

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

    def _observe_and_record_drift_promotion(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        effective_profile: dict[str, object],
        interpretation: CharacterInterpretation,
    ) -> None:
        candidate = self._drift_accumulator.observe(
            actor_id=actor_id,
            effective_profile=effective_profile,
            interpretation=interpretation,
            dynamic_state=self.get_dynamic_state_record(actor_id),
            need_tension_state=self.get_need_tension_state_record(actor_id),
        )
        if candidate is not None and self._drift_promotion_gate.should_promote(candidate):
            self._record_drift_promotion(actor_id, producer_ts, candidate)

    def _record_drift_promotion(
        self,
        actor_id: str,
        producer_ts: int,
        candidate: DriftCandidateRecord,
    ) -> None:
        for entry in self.get_session_timeline(actor_id):
            if entry.get("event_type") != "character_personality_drift_promotion_event":
                continue
            payload = entry.get("payload", {})
            if not isinstance(payload, dict):
                continue
            if (
                str(payload.get("key", "") or "") == candidate.key
                and str(payload.get("direction", "") or "") == candidate.direction
            ):
                return
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_personality_drift_promotion_event",
            producer_ts=producer_ts,
            payload=candidate.model_dump(),
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
        current_goal_state: dict[str, object],
        goal_state_history: list[dict[str, object]],
        supervision_state: dict[str, object],
        unresolved_tensions: list[dict[str, object]],
        background_agenda_state: dict[str, object],
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
            current_goal_state=current_goal_state,
            goal_state_history=goal_state_history,
            supervision_state=supervision_state,
            unresolved_tensions=unresolved_tensions,
            background_agenda_state=background_agenda_state,
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
            current_goal_state=self.get_goal_state(actor_id),
            goal_state_history=self.get_goal_state_history(actor_id),
            supervision_state=self.get_supervision_state(actor_id),
            unresolved_tensions=self.get_unresolved_tensions(actor_id),
            background_agenda_state=self.get_background_agenda_state(actor_id),
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

    def _continuity_floor_suggestion_packet(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> CharacterSuggestionPacket:
        latest_goal_state = self._latest_goal_state_payload(actor_id)
        recommended_intents = [decision.selected_intent] if decision.selected_intent != "" else ["stay_silent"]
        suggestion_packet = CharacterSuggestionPacket(
            actor_id=actor_id,
            control_mode="player_priority_assisted",
            producer_ts=producer_ts,
            causation_id=f"character_suggestion:{producer_ts}:{actor_id}",
            correlation_id=f"character_suggestion:{producer_ts}:{actor_id}",
            recommended_intents=recommended_intents,
            risk_notes=[interpretation.interpreted_summary],
            primary_goal=str(latest_goal_state.get("primary_goal", "") or decision.primary_goal),
            long_term_goal=str(latest_goal_state.get("long_term_goal", "") or decision.long_term_goal),
            mid_term_strategy=str(latest_goal_state.get("mid_term_strategy", "") or decision.mid_term_strategy or "hold_position"),
            supporting_goals=list(latest_goal_state.get("supporting_goals", [])) if isinstance(latest_goal_state.get("supporting_goals", []), list) else list(decision.supporting_goals),
            blockers=list(latest_goal_state.get("blockers", [])) if isinstance(latest_goal_state.get("blockers", []), list) else list(decision.blockers),
            goal_sources=list(latest_goal_state.get("goal_sources", [])) if isinstance(latest_goal_state.get("goal_sources", []), list) else list(decision.goal_sources),
            urgency=str(latest_goal_state.get("urgency", "low") or decision.urgency or "low"),
            transition_kind=str(latest_goal_state.get("transition_kind", "") or ""),
            transition_reason_tags=list(latest_goal_state.get("transition_reason_tags", [])) if isinstance(latest_goal_state.get("transition_reason_tags", []), list) else [],
            belief_cues=[],
            higher_order_cues=[],
            dynamic_pressure="continuity_floor",
            urge_vector="preserve_continuity",
            social_read="",
            why_this_now=decision.rationale,
            role_consistency_hint="model-unavailable continuity floor",
            reasoning_trace_summary=str(interpretation.reasoning_trace_summary or "continuity_floor"),
            planning_status="continuity_floor",
            fallback_mode="continuity_floor",
        )
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_agent_suggestion_packet",
            producer_ts=producer_ts,
            payload=suggestion_packet.model_dump(exclude_none=True),
        )
        self._memory_store.write_event(stored)
        self._set_observatory_context(
            actor_id,
            "decision_summary",
            suggestion_packet.why_this_now or (suggestion_packet.recommended_intents[0] if suggestion_packet.recommended_intents else ""),
        )
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

    def _build_default_background_modes(self) -> dict[str, CharacterBackgroundMode]:
        return {actor_id: "passive" for actor_id in self._supported_actor_ids}

    def _resolve_target_ref(self, target_actor_id: str, target_object_id: str, target_environment_id: str) -> str:
        return str(target_actor_id or target_object_id or target_environment_id or "")

    def _supervision_state_for(self, actor_id: str) -> CharacterSupervisionState:
        state = self._supervision_states.get(actor_id)
        if state is not None:
            return state
        default = CharacterSupervisionState(
            actor_id=actor_id,
            current_level="weak",
            source="siming_weak_default",
            active_constraints=self._weak_supervision_constraints_for(actor_id, 0),
            entered_at_ts=0,
            expires_at_ts=0,
            last_refresh_ts=0,
            last_reason_summary="default weak supervision",
        )
        self._supervision_states[actor_id] = default
        return default

    def _refresh_weak_supervision_state(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        reason_summary: str,
    ) -> CharacterSupervisionState:
        state = self._supervision_states.get(actor_id)
        if state is not None and state.current_level in {"medium", "strong"}:
            if state.expires_at_ts > 0 and producer_ts >= state.expires_at_ts:
                return self.clear_supervision_authorization(
                    actor_id=actor_id,
                    producer_ts=producer_ts,
                    reason="authorized supervision expired; weak supervision restored",
                )
            return state
        refreshed = CharacterSupervisionState(
            actor_id=actor_id,
            current_level="weak",
            source="siming_weak_default",
            active_constraints=self._weak_supervision_constraints_for(actor_id, producer_ts),
            entered_at_ts=state.entered_at_ts if state is not None else producer_ts,
            expires_at_ts=0,
            last_refresh_ts=producer_ts,
            last_reason_summary=reason_summary,
        )
        self._supervision_states[actor_id] = refreshed
        if self.supports_actor(actor_id):
            self._background_modes[actor_id] = refreshed.active_constraints.background_mode
        return refreshed

    def _refresh_weak_supervision_from_siming(
        self,
        *,
        actor_id: str,
        payload: dict[str, object],
        producer_ts: int,
    ) -> CharacterSupervisionState:
        current = self._supervision_states.get(actor_id)
        if current is not None and current.current_level in {"medium", "strong"}:
            return current
        constraints = self._weak_supervision_constraints_for(actor_id, producer_ts)
        pressure_hint = str(payload.get("pressure_hint", "") or "").strip()
        reason_scope = str(payload.get("reason_scope", "") or "").strip()
        if pressure_hint != "":
            constraints.pressure_theme = pressure_hint
            constraints.caution_bias = "high"
            constraints.constraint_tags = list(dict.fromkeys([*constraints.constraint_tags, "siming_pressure"]))
        if reason_scope != "":
            constraints.attention_theme = list(dict.fromkeys([*constraints.attention_theme, reason_scope]))
            constraints.constraint_tags = list(dict.fromkeys([*constraints.constraint_tags, "siming_reason_scope"]))
        constraints.supervision_reason_code = "siming_weak_supervision"
        constraints.supervision_reason_summary = "weak supervision refreshed from siming catalyst"
        state = CharacterSupervisionState(
            actor_id=actor_id,
            current_level="weak",
            source="siming_weak_default",
            active_constraints=constraints,
            entered_at_ts=current.entered_at_ts if current is not None else producer_ts,
            expires_at_ts=0,
            last_refresh_ts=producer_ts,
            last_reason_summary="weak supervision refreshed from siming catalyst",
        )
        self._supervision_states[actor_id] = state
        if self.supports_actor(actor_id):
            self._background_modes[actor_id] = state.active_constraints.background_mode
        return state

    def _weak_supervision_constraints_for(self, actor_id: str, producer_ts: int) -> CharacterSupervisionConstraints:
        snapshot = self.get_private_snapshot(actor_id)
        attention_theme: list[str] = []
        preferred_watch_targets: list[str] = []
        pressure_theme = ""
        caution_bias: str = "low"
        constraint_tags: list[str] = []
        if snapshot is not None:
            if snapshot.last_siming_catalyst:
                attention_theme.append("siming_catalyst")
            if snapshot.attention_targets:
                preferred_watch_targets.append(str(snapshot.attention_targets[0]))
            if snapshot.vigilance_level == "elevated":
                caution_bias = "medium"
                constraint_tags.append("elevated_vigilance")
            if snapshot.distraction_level == "elevated":
                pressure_theme = "uncertain_signal"
                constraint_tags.append("elevated_distraction")
        wake_signal = self._wake_up_signals.get(actor_id, {})
        if bool(wake_signal.get("wake_up_requested", False)):
            attention_theme.append("wake_up_signal")
            caution_bias = "medium" if caution_bias == "low" else caution_bias
            constraint_tags.append("wake_up_signal")
        mode = self.get_background_mode(actor_id)
        return CharacterSupervisionConstraints(
            allow_background_loop=mode != "off",
            background_mode=mode,
            min_tick_interval_ms=6000 if mode == "active" else 12000,
            max_tick_budget_tokens=400,
            max_consecutive_ticks=1,
            wake_up_threshold=0.9,
            attention_theme=attention_theme,
            preferred_watch_targets=preferred_watch_targets,
            pressure_theme=pressure_theme,
            caution_bias="high" if any(tag == "wake_up_signal" for tag in constraint_tags) else caution_bias,
            allow_proactive_initiation=mode == "active",
            allow_proactive_tendency_generation=mode == "active",
            constraint_summary="weak supervision maintains low-cost background cognition boundaries",
            constraint_tags=constraint_tags,
            supervision_reason_code="weak_supervision",
            supervision_reason_summary=f"weak supervision for {actor_id} at {producer_ts}",
        )

    def _constraints_model(
        self,
        value: dict[str, object] | CharacterSupervisionConstraints | None,
    ) -> CharacterSupervisionConstraints:
        if isinstance(value, CharacterSupervisionConstraints):
            return value
        if isinstance(value, dict):
            return CharacterSupervisionConstraints(**value)
        return CharacterSupervisionConstraints()

    def _authorization_model(
        self,
        value: dict[str, object] | CharacterSupervisionAuthorization,
    ) -> CharacterSupervisionAuthorization:
        if isinstance(value, CharacterSupervisionAuthorization):
            return value
        payload = dict(value)
        payload["constraints"] = self._constraints_model(payload.get("constraints", {}))
        return CharacterSupervisionAuthorization(**payload)

    def _background_tick_due(self, *, actor_id: str, producer_ts: int) -> bool:
        supervision_state = self._supervision_state_for(actor_id)
        interval = int(supervision_state.active_constraints.min_tick_interval_ms or 0)
        if interval <= 0:
            return True
        previous = self._last_background_tick_ms.get(actor_id)
        if previous is None:
            return True
        return producer_ts - previous >= interval

    def _background_reappraisal_payload(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        snapshot: CharacterPrivateWorldSnapshot,
        current_goal_state: dict[str, object],
        unresolved_tensions: list[dict[str, object]],
        supervision_state: dict[str, object],
    ) -> dict[str, object]:
        top_tension = unresolved_tensions[0] if unresolved_tensions else {}
        top_summary = str(top_tension.get("summary", "") or "")
        top_target_ref = str(top_tension.get("target_ref", "") or "")
        snapshot_mapping = snapshot.model_dump()
        perceived_summary = (
            top_summary
            or self._recent_constraint_summary(snapshot_mapping)
            or self._recent_world_change_summary(snapshot_mapping)
            or str(current_goal_state.get("primary_goal", "") or "")
            or "background_reappraisal"
        )
        return {
            "actor_id": actor_id,
            "event_type": "background_reappraisal",
            "producer_ts": producer_ts,
            "perceived_summary": perceived_summary,
            "source_candidate_event_id": f"background:{producer_ts}:{actor_id}",
            "target_actor_id": top_target_ref if top_target_ref.startswith("char_") else "",
            "target_object_id": top_target_ref if top_target_ref.startswith("obj_") else "",
            "target_environment_id": top_target_ref if top_target_ref.startswith("env_") else "",
            "background_mode": self.get_background_mode(actor_id),
            "supervision_level": str(supervision_state.get("current_level", "weak") or "weak"),
            "top_tension_id": str(top_tension.get("tension_id", "") or ""),
            "top_tension_category": str(top_tension.get("category", "") or ""),
        }

    def _recent_world_change_summary(self, snapshot: dict[str, object]) -> str:
        value = snapshot.get("recent_world_changes", [])
        if not isinstance(value, list) or not value:
            return ""
        return str(value[-1] or "")

    def _recent_constraint_summary(self, snapshot: dict[str, object]) -> str:
        value = snapshot.get("recent_constraint_results", [])
        if not isinstance(value, list) or not value:
            return ""
        return str(value[-1] or "")

    def _runtime_payload_event(self, actor_id: str, payload: dict[str, object]):
        class _PayloadEvent:
            def __init__(self, actor_id: str, payload: dict[str, object]) -> None:
                self.actor_id = actor_id
                self._payload = dict(payload)

            def model_dump(self) -> dict[str, object]:
                return dict(self._payload)

        return _PayloadEvent(actor_id, payload)

    def _record_background_cognition_event(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        background_payload: dict[str, object],
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
        supervision_state: dict[str, object],
        unresolved_tensions: list[dict[str, object]],
        agenda_state: CharacterBackgroundAgendaState,
    ) -> None:
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_background_cognition_event",
            producer_ts=producer_ts,
            payload={
                "background_payload": background_payload,
                "interpretation_summary": interpretation.interpreted_summary,
                "selected_intent": decision.selected_intent,
                "goal_primary": decision.primary_goal,
                "supervision_state": supervision_state,
                "unresolved_tension_count": len(unresolved_tensions),
                "background_agenda_state": agenda_state.model_dump(),
            },
        )
        self._memory_store.write_event(stored)

    def _build_background_agenda_state(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
        supervision_state: dict[str, object],
        unresolved_tensions: list[dict[str, object]],
    ) -> CharacterBackgroundAgendaState:
        watch_focus = str(interpretation.attention_target or "")
        latent_tendency = decision.selected_intent
        agenda_phase = str(supervision_state.get("active_constraints", {}).get("background_mode", "") or "passive")
        agenda_summary = decision.rationale or interpretation.interpreted_summary
        previous_state = self._background_agenda_states.get(actor_id)
        agenda_entries = self._background_agenda_entries(
            actor_id=actor_id,
            producer_ts=producer_ts,
            decision=decision,
            unresolved_tensions=unresolved_tensions,
            previous_state=previous_state,
        )
        dominant_agenda_id = agenda_entries[0].agenda_id if agenda_entries else ""
        return CharacterBackgroundAgendaState(
            actor_id=actor_id,
            latent_tendency=latent_tendency,
            watch_focus=watch_focus,
            agenda_summary=agenda_summary,
            agenda_phase=agenda_phase,
            supervision_level=str(supervision_state.get("current_level", "weak") or "weak"),
            dominant_agenda_id=dominant_agenda_id,
            agenda_entries=agenda_entries,
            updated_at=producer_ts,
        )

    def _background_agenda_entries(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        decision: CharacterIntentDecision,
        unresolved_tensions: list[dict[str, object]],
        previous_state: CharacterBackgroundAgendaState | None,
    ) -> list[CharacterBackgroundAgendaEntry]:
        previous_entries = {
            entry.agenda_id: entry
            for entry in (previous_state.agenda_entries if previous_state is not None else [])
        }
        entries: list[CharacterBackgroundAgendaEntry] = []

        dominant_goal_id = (
            decision.active_goal_frame.dominant_goal_id
            if decision.active_goal_frame is not None and decision.active_goal_frame.dominant_goal_id
            else f"agenda_goal:{decision.primary_goal or 'preserve_continuity'}"
        )
        dominant_goal_title = decision.primary_goal or "preserve_continuity"
        existing_goal_entry = previous_entries.get(dominant_goal_id)
        entries.append(
            CharacterBackgroundAgendaEntry(
                agenda_id=dominant_goal_id,
                agenda_kind="goal",
                title=dominant_goal_title,
                summary=decision.rationale,
                target_ref="",
                horizon="long" if decision.long_term_goal else "mid",
                status="active",
                priority=max(0.55, float(existing_goal_entry.priority) if existing_goal_entry is not None else 0.72),
                source="goal_state",
                last_reinforced_ts=producer_ts,
                last_progress_ts=producer_ts,
                blocked_count=len(decision.blockers),
            )
        )

        top_tension = unresolved_tensions[0] if unresolved_tensions else {}
        if top_tension:
            tension_id = str(top_tension.get("tension_id", "") or f"{actor_id}:tension")
            existing_tension_entry = previous_entries.get(tension_id)
            entries.append(
                CharacterBackgroundAgendaEntry(
                    agenda_id=tension_id,
                    agenda_kind="tension_watch",
                    title=str(top_tension.get("summary", "") or "watch unresolved tension"),
                    summary=str(top_tension.get("summary", "") or ""),
                    target_ref=str(top_tension.get("target_ref", "") or ""),
                    horizon="mid",
                    status=str(top_tension.get("status", "active") or "active"),
                    priority=max(0.45, float(existing_tension_entry.priority) if existing_tension_entry is not None else float(top_tension.get("priority", 0.64) or 0.64)),
                    source="unresolved_tension",
                    last_reinforced_ts=producer_ts,
                    last_progress_ts=producer_ts,
                    blocked_count=int(existing_tension_entry.blocked_count if existing_tension_entry is not None else 0),
                )
            )

        for agenda_id, entry in previous_entries.items():
            if agenda_id in {item.agenda_id for item in entries}:
                continue
            decayed_priority = max(0.15, round(float(entry.priority) * 0.9, 4))
            entries.append(
                entry.model_copy(
                    update={
                        "priority": decayed_priority,
                        "status": "dormant" if entry.status == "active" else entry.status,
                    }
                )
            )

        entries.sort(key=lambda item: float(item.priority), reverse=True)
        return entries[: self._RECENT_HISTORY_LIMIT]

    def _remember_unresolved_tension(
        self,
        *,
        actor_id: str,
        category: str,
        summary: str,
        target_ref: str,
        producer_ts: int,
        source_event_id: str,
        source_stage: str,
        priority: float,
    ) -> None:
        if summary == "":
            return
        tension_id = f"{actor_id}:{category}:{target_ref or 'general'}"
        existing = {
            item.tension_id: item
            for item in self._unresolved_tension_store.recall_records(actor_id)
        }.get(tension_id)
        record = CharacterUnresolvedTension(
            tension_id=tension_id,
            category=category,
            summary=summary,
            target_ref=target_ref or (existing.target_ref if existing is not None else ""),
            priority=max(
                0.0,
                min(1.0, max(priority, float(existing.priority) if existing is not None else priority)),
            ),
            status="active",
            source_event_id=source_event_id or (existing.source_event_id if existing is not None else ""),
            source_stage=source_stage or (existing.source_stage if existing is not None else ""),
            last_reinforced_ts=producer_ts,
        )
        self._unresolved_tension_store.upsert(actor_id, record)
        stored = self._session_store.append_event(
            actor_id=actor_id,
            event_type="character_unresolved_tension_event",
            producer_ts=producer_ts,
            payload=record.model_dump(),
        )
        self._memory_store.write_event(stored)

    def _build_default_control_modes(self) -> dict[str, str]:
        return {
            actor_id: self._profile_registry.get(actor_id).runtime_defaults.default_control_mode
            for actor_id in self._supported_actor_ids
        }

    def _profile_payload(self, actor_id: str) -> dict[str, object]:
        return self._profile_registry.get(actor_id).model_dump()

    def _effective_profile_payload(self, actor_id: str) -> dict[str, object]:
        return resolve_effective_profile(self._profile_payload(actor_id))

    def _need_tension_event_payload(self, event: CharacterPerceivedEvent) -> dict[str, object]:
        payload = event.model_dump()
        payload["event_tags"] = self._derived_need_tension_event_tags(event)
        return payload

    def _need_tension_delta_payload(self, need_delta) -> dict[str, object]:
        payload = need_delta.as_mapping()
        ranked_needs = self._ranked_need_pressures(payload)
        if ranked_needs:
            payload.setdefault("dominant_need", ranked_needs[0][0])
            if len(ranked_needs) > 1:
                payload.setdefault("secondary_need", ranked_needs[1][0])
            payload.setdefault("motivation_stack", [need_key for need_key, _ in ranked_needs])
        return payload

    def _derived_need_tension_event_tags(self, event: CharacterPerceivedEvent) -> list[str]:
        tag_sources = (
            event.perceived_summary,
            event.target_ref,
            event.target_environment_id,
            event.target_object_id,
            event.target_actor_id,
        )
        normalized = " ".join(str(value).lower() for value in tag_sources if str(value).strip() != "")
        tags: list[str] = []
        if "spatial_uncertainty" in normalized or "unstable doorway" in normalized:
            tags.append("spatial_uncertainty")
        if "public_dismissal" in normalized or "public dismissal" in normalized:
            tags.append("public_dismissal")
        return tags

    def _ranked_need_pressures(self, payload: dict[str, object]) -> list[tuple[str, float]]:
        need_pressures: list[tuple[str, float]] = []
        for need_key in (
            "physiological",
            "safety",
            "belonging",
            "esteem",
            "self_actualization",
        ):
            value = payload.get(f"{need_key}_pressure")
            if isinstance(value, bool) or not isinstance(value, int | float):
                continue
            if float(value) <= 0.0:
                continue
            need_pressures.append((need_key, float(value)))
        return sorted(need_pressures, key=lambda item: (-item[1], item[0]))

    def _rehydrate_runtime_state_from_timeline(self) -> None:
        for actor_id, events in self._session_store.list_all_events().items():
            for event in events:
                if isinstance(event, dict):
                    self._memory_store.write_event(event)
                event_type = str(event.get("event_type", "") or "") if isinstance(event, dict) else ""
                payload = event.get("payload", {}) if isinstance(event, dict) else {}
                if not isinstance(payload, dict):
                    continue
                if event_type == "goal_state_event":
                    self._goal_state_store.write(
                        actor_id,
                        CharacterGoalStateRecord(
                            actor_id=actor_id,
                            primary_goal=str(payload.get("primary_goal", "") or ""),
                            long_term_goal=str(payload.get("long_term_goal", "") or ""),
                            mid_term_strategy=str(payload.get("mid_term_strategy", "") or ""),
                            immediate_goal=str(payload.get("immediate_goal", "") or str(payload.get("primary_goal", "") or "")),
                            supporting_goals=list(payload.get("supporting_goals", [])) if isinstance(payload.get("supporting_goals", []), list) else [],
                            blockers=list(payload.get("blockers", [])) if isinstance(payload.get("blockers", []), list) else [],
                            goal_sources=list(payload.get("goal_sources", [])) if isinstance(payload.get("goal_sources", []), list) else [],
                            urgency=str(payload.get("urgency", "low") or "low"),
                            dominant_goal_id=str(payload.get("dominant_goal_id", "") or ""),
                            preserved_goal_ids=list(payload.get("preserved_goal_ids", [])) if isinstance(payload.get("preserved_goal_ids", []), list) else [],
                            suppressed_goal_ids=list(payload.get("suppressed_goal_ids", [])) if isinstance(payload.get("suppressed_goal_ids", []), list) else [],
                            goal_arbitration_summary=str(payload.get("goal_arbitration_summary", "") or ""),
                            goal_portfolio=list(payload.get("goal_portfolio", [])) if isinstance(payload.get("goal_portfolio", []), list) else [],
                            transition_kind=str(payload.get("transition_kind", "initial") or "initial"),
                            transition_reason_tags=list(payload.get("transition_reason_tags", [])) if isinstance(payload.get("transition_reason_tags", []), list) else [],
                        ),
                    )
                elif event_type == "dynamic_state_event":
                    self._dynamic_state_store.write(actor_id, payload)
                elif event_type == "character_unresolved_tension_event":
                    self._unresolved_tension_store.upsert(actor_id, payload)
                elif event_type == "character_supervision_authorization":
                    state = CharacterSupervisionState(
                        actor_id=actor_id,
                        current_level=str(payload.get("approved_level", "weak") or "weak"),
                        source="strategy_authorized" if str(payload.get("approved_by", "strategy_service") or "strategy_service") == "strategy_service" else "gm_override",
                        active_constraints=self._constraints_model(payload.get("constraints", {})),
                        entered_at_ts=int(payload.get("effective_from_ts", 0) or 0),
                        expires_at_ts=int(payload.get("expires_at_ts", 0) or 0),
                        last_refresh_ts=int(payload.get("producer_ts", 0) or 0),
                        last_reason_summary=str(payload.get("approval_reason", "") or ""),
                    )
                    self._supervision_states[actor_id] = state
                    if self.supports_actor(actor_id):
                        self._background_modes[actor_id] = state.active_constraints.background_mode
                elif event_type == "character_supervision_cleared":
                    state = CharacterSupervisionState(**payload)
                    self._supervision_states[actor_id] = state
                    if self.supports_actor(actor_id):
                        self._background_modes[actor_id] = state.active_constraints.background_mode
                elif event_type == "character_background_cognition_event":
                    agenda_payload = payload.get("background_agenda_state", {})
                    if isinstance(agenda_payload, dict) and agenda_payload:
                        self._background_agenda_states[actor_id] = CharacterBackgroundAgendaState(**agenda_payload)

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
