from copy import deepcopy
from collections import OrderedDict
from collections.abc import Generator
from dataclasses import asdict, dataclass, is_dataclass, replace
from time import monotonic
from uuid import uuid4
from pydantic import BaseModel
from app.character_agent.runtime.cognition_continuation import (
    CognitionAdvance, CognitionRequest, PendingCognitionTurn, PreparedCognitionJob,
)
import hashlib
import json
import math
import os
from pathlib import Path
from threading import RLock, get_ident
from typing import Callable

from app.character_agent.logic.affect_engine import AffectEngine
from app.character_agent.logic.drift_accumulator import DriftAccumulator
from app.character_agent.logic.drift_promotion_gate import DriftPromotionGate
from app.character_agent.logic.need_tension_engine import NeedTensionEngine
from app.character_agent.models.drift_candidate import DriftCandidateRecord
from app.character_agent.models.need_tension import NeedTensionState
from app.character_agent.models.dynamic_state import CharacterDynamicState
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
from app.character_agent.models.memory_consistency import (
    MemoryConsistencyResult, MemoryCorrectionRequest, MemoryCorrectionReceipt, MemoryFactClaim,
    MemorySourceRecord, compare_memory_claims, memory_claim_key,
)
from app.character_agent.models.supervision import (
    CharacterBackgroundCognitionResult,
    CharacterBackgroundMode,
    CharacterSupervisionAuthorization,
    CharacterSupervisionConstraints,
    CharacterSupervisionRequest,
    CharacterSupervisionState,
    CharacterUnresolvedTension,
)
from app.character_agent.models.simulation_seed import (
    CharacterModuleDelta,
    CharacterContinuityCommand,
    CharacterContinuityReceipt,
    CharacterMemoryCandidate,
    CharacterMemoryMaterializationReceipt,
)
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
from app.character_agent.mind.writeback_policy import MindWritebackPolicyRouter
from app.character_agent.models.mind_frame import MindDeltaLedger
from app.character_agent.skills.catalog import create_runtime_skill_registry
from app.character_agent.skills.models import ActionSettlementResult
from app.character_agent.skills.service import CharacterSkillService
from app.models.character_agent_runtime import CharacterGoalCommand
from app.models.character_agent_runtime import CHARACTER_AGENT_CONTROL_MODES
from app.models.character_agent_runtime import CHARACTER_ACTOR_AUTONOMY_MODES
from app.models.character_agent_runtime import SHARED_CHARACTER_COMMANDS
from app.models.character_agent_runtime import CharacterInterpretation
from app.models.character_agent_runtime import CharacterIntentDecision
from app.models.character_agent_runtime import CharacterSuggestionPacket
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.character_agent.reasoning.l1_perception import CharacterAgentL1Service
from app.character_agent.reasoning.active_perception import ActivePerceptionPlanner, ActivePerceptionRequest, ActivePerceptionResult
from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeEntry
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.gateway.memory_recall import MissingRequiredMemoryEvidence
from app.character_agent.execution.l4_adapter import CharacterAgentL4Adapter
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.character_agent.memory.working_memory import CharacterWorkingMemory
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore, CharacterMemoryStorePort
from app.character_agent.storage.dynamic_state_store import CharacterDynamicStateStore
from app.character_agent.storage.graph_continuity_store import CharacterGraphContinuityStore
from app.character_agent.storage.goal_state_store import CharacterGoalStateStore
from app.character_agent.storage.need_tension_store import CharacterNeedTensionStore
from app.character_agent.storage.unresolved_tension_store import CharacterUnresolvedTensionStore
from app.gameplay.runtime_state import StateGroupRegistry, StateGroupRegistryError
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.models import ActivationDecision, ActivationReceipt
from app.character_agent.services.character_behavior_evaluation import CharacterBehaviorEvaluationService
from app.character_agent.services.behavior_turn_projection import CharacterBehaviorTurnProjection
from app.character_agent.services.character_continuity import CharacterContinuityService
from app.services.character_agent_debug_projection import CharacterAgentDebugProjection
from app.services.behavior_turn_recorder import BehaviorTurnRecorder
from app.models.siming_character_bridge import SimingCharacterCompatibilityInput
from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle
from app.world_runtime.continuity import RuntimeContinuityState
from app.world_runtime.scheduling import (
    RuntimeCadencePolicy,
    RuntimePopulationPolicy,
    RuntimeWakeUpCandidate,
    select_schedulable_actor_ids,
)


@dataclass(frozen=True)
class ActivationHandle:
    actor_id: str
    world_ref: str
    lock_ref: str
    token: str
    generation: str
    deadline_monotonic: float


class CharacterAgentRuntime:
    AWAY_CONSERVATIVE_ALLOWED_COMMANDS = {"look_at", "observe", "speak"}
    _RECENT_HISTORY_LIMIT = 4
    _PROFILE_DIRECTORY = Path(__file__).resolve().parents[4] / "assets" / "characters" / "profiles"
    _SOCIAL_ENGAGEMENT_CHANNELS = {"auditory", "dialogue", "social", "speech", "verbal"}

    def __init__(
        self,
        storage_root: str | Path | None = None,
        *,
        continuity_actor_ids: set[str] | frozenset[str] | None = None,
        session_store: CharacterAgentSessionStore | None = None,
        skill_service: CharacterSkillService | None = None,
        memory_store: CharacterMemoryStorePort | None = None,
        continuity_store: CharacterGraphContinuityStore | None = None,
        activation_authority: ProfileActivationAuthority | None = None,
        behavior_turn_recorder: BehaviorTurnRecorder | None = None,
        behavior_turn_scope_resolver: Callable[[str], HeavenlyGraphScope] | None = None,
        memory_correction_authorizer: Callable[[str, MemoryCorrectionRequest], bool] | None = None,
        memory_source_resolver: Callable[[str], MemorySourceRecord | None] | None = None,
        memory_now_ts_provider: Callable[[], int] | None = None,
        state_group_registry: StateGroupRegistry | None = None,
    ) -> None:
        if os.getenv("CHARACTER_GRAPH_REQUIRE_CONTINUITY", "").strip() == "1" and continuity_store is None:
            raise ValueError("graph continuity store is required in production continuity mode")
        # ponytail: 仅旧同步调用串行 drain；生产异步入口由 owner 调度，不在等待 I/O 时持此锁。
        self._sync_cognition_lock = RLock()
        self._cognition_generation = 0
        self._pending_cognition: dict[str, PendingCognitionTurn] = {}
        self._cognition_receipts: OrderedDict[str, tuple[PreparedCognitionJob, str, CognitionAdvance]] = OrderedDict()
        self._profile_registry = CharacterProfileRegistry.from_directory(self._PROFILE_DIRECTORY)
        # ponytail: 单 runtime 的低频修复串行执行；多进程写入时需使用 owner 事务锁。
        self._memory_correction_lock = RLock()
        self._memory_correction_authorizer = memory_correction_authorizer
        self._memory_source_resolver = memory_source_resolver
        self._memory_now_ts_provider = memory_now_ts_provider
        self._supported_actor_ids = set(self._profile_registry.actor_ids())
        self._continuity_actor_ids = set(continuity_actor_ids or ())
        self._activation_world_ref = "world:default"
        self._activation_authority = activation_authority
        self._activation_generation = uuid4().hex
        self._activation_handles: dict[str, ActivationHandle] = {}
        self._activation_ending: set[str] = set()
        self._activation_owner_thread: int | None = None
        self._activation_receipts: OrderedDict[str, tuple[ActivationHandle, ActivationReceipt]] = OrderedDict()
        self._sync_activation_handles: dict[str, ActivationHandle] = {}
        self._l1 = CharacterAgentL1Service()
        self._l2 = CharacterAgentL2Service(profile_registry=self._profile_registry)
        self._l3 = CharacterAgentL3Service()
        self._l4 = CharacterAgentL4Adapter()
        self._l4_executor = CharacterAgentL4Executor()
        self._skill_service = skill_service or CharacterSkillService(
            registry=create_runtime_skill_registry()
        )
        self._mind_frame_builder = CharacterMindFrameBuilder()
        self._mind_writeback_policy = MindWritebackPolicyRouter()
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
        self._last_skill_affordance_summaries: dict[str, dict[str, object]] = {}
        self._session_store = session_store or CharacterAgentSessionStore(storage_root=storage_root,
            database_path=getattr(continuity_store, 'session_database_path', None))
        try:
            self._memory_store = memory_store or CharacterAgentMemoryStore()
            self._dynamic_state_store = CharacterDynamicStateStore()
            self._need_tension_store = CharacterNeedTensionStore()
            self._goal_state_store = CharacterGoalStateStore()
            self._unresolved_tension_store = CharacterUnresolvedTensionStore()
            self._behavior_evaluation = CharacterBehaviorEvaluationService()
            self._continuity_store = continuity_store
            self._state_group_registry = state_group_registry
            self._shared_module_states: dict[str, dict[str, dict[str, object]]] = {}
            self._continuity_flush_locks: dict[str, RLock] = {}
            self._continuity_revisions: dict[str, int] = {}
            self._continuity_service = CharacterContinuityService(
                apply_command=self._apply_continuity_command,
                materialize=self.materialize_pending_seed_memories,
            )
            self._behavior_turn_projection = (
                CharacterBehaviorTurnProjection(
                    recorder=behavior_turn_recorder,
                    scope_resolver=behavior_turn_scope_resolver,
                )
                if behavior_turn_recorder is not None
                and behavior_turn_scope_resolver is not None
                else None
            )
            self._need_tension_engine = NeedTensionEngine()
            self._affect_engine = AffectEngine()
            self._drift_accumulator = DriftAccumulator()
            self._drift_promotion_gate = DriftPromotionGate()
            self._legacy_runtime_extras = {}
            self._runtime_field_versions = {}
            self._rehydrate_graph_continuity()
            self._rehydrate_runtime_state_from_timeline()
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        """释放持久会话连接；pending 与 activation 由原 owner 先收口。"""
        self._session_store.close()

    def ingest_character_perceived_event(self, event: CharacterPerceivedEvent) -> list[CharacterGoalCommand]:
        return self._drain_cognition(source_kind="ingest_character_perceived_event", payload=event)

    def ingest_self_body_perceived_event(self, event: SelfBodyPerceivedEvent) -> list[CharacterGoalCommand]:
        return self._drain_cognition(source_kind="ingest_self_body_perceived_event", payload=event)

    def ingest_siming_output(
        self, payload: dict[str, object] | SimingCharacterCompatibilityInput,
    ) -> list[CharacterGoalCommand]:
        return self._drain_cognition(source_kind="ingest_siming_output", payload=payload)

    def run_background_cognition_tick(
        self, *, actor_id: str, producer_ts: int,
    ) -> CharacterBackgroundCognitionResult:
        return self._drain_cognition(source_kind="run_background_cognition_tick",
            actor_id=actor_id, producer_ts=producer_ts)

    def prepare_cognition_job(
        self, *, source_kind: str,
        payload: CharacterPerceivedEvent | SelfBodyPerceivedEvent | SimingCharacterCompatibilityInput | dict[str, object] | None = None,
        actor_id: str = "", producer_ts: int = 0,
        deadline_monotonic: float | None = None,
        activation_lock_ref: str = "", activation_token: str = "",
        activation_is_current: Callable[[str, str], bool] | None = None,
        on_finished: Callable[[str, str], None] | None = None,
    ) -> CognitionAdvance:
        """Owner 先预留容量，再接收感知；worker 仅获不可变请求，不获续执行对象。"""
        self._assert_cognition_owner()
        if bool(activation_lock_ref) != bool(activation_token):
            raise ValueError("activation lock and token must be provided together")
        if activation_lock_ref and activation_is_current is None:
            raise ValueError("activation lock requires owner validation")
        if source_kind == "ingest_character_perceived_event":
            event = CharacterPerceivedEvent.model_validate(payload).model_copy(deep=True)
            actor_id, producer_ts = event.actor_id, event.producer_ts
            steps = self._ingest_character_perceived_event_steps(event)
        elif source_kind == "ingest_self_body_perceived_event":
            event = SelfBodyPerceivedEvent.model_validate(payload).model_copy(deep=True)
            actor_id, producer_ts = event.actor_id, event.producer_ts
            steps = self._ingest_self_body_perceived_event_steps(event)
        elif source_kind == "ingest_siming_output":
            event = SimingCharacterCompatibilityInput.model_validate(payload).model_copy(deep=True)
            actor_id, producer_ts = event.target_actor_id or event.actor_id, event.producer_ts
            steps = self._ingest_siming_output_steps(event)
        elif source_kind == "run_background_cognition_tick":
            steps = self._run_background_cognition_tick_steps(actor_id=actor_id, producer_ts=producer_ts)
        else:
            raise ValueError("unsupported cognition source_kind")
        reason = ""
        deadline = deadline_monotonic if deadline_monotonic is not None else monotonic() + 60.0
        if not math.isfinite(deadline):
            raise ValueError("cognition deadline must be finite")
        held_activation = self._activation_handles.get(actor_id)
        if held_activation is not None and (
            activation_lock_ref != held_activation.lock_ref or activation_token != held_activation.token
        ):
            reason = "activation_invalid"
        elif actor_id in self._pending_cognition:
            reason = "actor_busy"
        elif len(self._pending_cognition) >= 4:
            reason = "pending_capacity"
        elif monotonic() >= deadline:
            reason = "deadline_expired"
        elif activation_lock_ref and not activation_is_current(activation_lock_ref, activation_token):
            reason = "activation_invalid"
        if reason:
            steps.close()
            result = CharacterBackgroundCognitionResult(actor_id=actor_id, producer_ts=producer_ts,
                ran=False, reason=reason) if source_kind == "run_background_cognition_tick" else []
            return CognitionAdvance("requeued", result=result, reason=reason)
        turn = PendingCognitionTurn(turn_id=uuid4().hex, actor_id=actor_id, producer_ts=producer_ts, source_kind=source_kind,
            steps=steps, deadline_monotonic=deadline, activation_lock_ref=activation_lock_ref,
            activation_token=activation_token, activation_is_current=activation_is_current,
            on_finished=on_finished, owner_thread=get_ident())
        self._pending_cognition[actor_id] = turn
        return self._advance_cognition(turn)

    def commit_cognition_result(
        self, job: PreparedCognitionJob, *, output: dict[str, object] | None = None,
        error: Exception | None = None,
    ) -> CognitionAdvance:
        """验证阶段凭证后才恢复业务；stale 不作为 provider 异常触发 continuity floor。"""
        self._assert_cognition_owner()
        if (output is None) == (error is None):
            raise ValueError("provide exactly one of output or error")
        completion = {"output": output} if error is None else {
            "error_type": f"{type(error).__module__}.{type(error).__qualname__}", "error": str(error)}
        fingerprint = self._cognition_digest(completion)
        receipt = self._cognition_receipts.get(job.job_id)
        if receipt is not None:
            recorded_job, recorded_fingerprint, advance = receipt
            if recorded_job != job or recorded_fingerprint != fingerprint:
                return CognitionAdvance("zero_write", reason="conflicting_completion")
            return replace(deepcopy(advance), replayed=True)
        turn = self._pending_cognition.get(job.actor_id)
        if turn is None or turn.job != job:
            return CognitionAdvance("zero_write", reason="unknown_or_invalid_job")
        try:
            reason = ""
            if job.generation != self._cognition_generation:
                reason = "generation_invalid"
            elif monotonic() >= job.deadline_monotonic:
                reason = "deadline_expired"
            elif turn.activation_lock_ref and not turn.activation_is_current(turn.activation_lock_ref, turn.activation_token):
                reason = "activation_invalid"
            elif self._capture_cognition_pin(job.actor_id, policy_id=turn.policy_id) != job.source_revision_vector:
                reason = "stale_context"
            if reason:
                self._finish_cognition_turn(turn, reason)
                advance = CognitionAdvance("requeued", reason=reason)
            else:
                # 先消费凭证；任何业务异常也不能使同一阶段再次执行。
                turn.job = None
                advance = self._advance_cognition(turn, output=deepcopy(output), error=error)
        except BaseException as failure:
            self._remember_cognition_receipt(job, fingerprint, CognitionAdvance("zero_write", reason="turn_failed"))
            try:
                self._finish_cognition_turn(turn, "failed")
            except BaseException as cleanup_failure:
                raise failure from cleanup_failure
            raise
        self._remember_cognition_receipt(job, fingerprint, advance)
        return deepcopy(advance)

    def cancel_cognition_turn(self, turn_id: str, *, reason: str = "cancelled") -> CognitionAdvance:
        self._assert_cognition_owner()
        turn = next((turn for turn in self._pending_cognition.values() if turn.turn_id == turn_id), None)
        if turn is None:
            return CognitionAdvance("zero_write", reason="unknown_turn")
        self._finish_cognition_turn(turn, reason)
        return CognitionAdvance("requeued", reason=reason)

    def reset_cognition_jobs(self) -> None:
        self._assert_cognition_owner()
        self._cognition_generation += 1
        first_error = None
        for turn in tuple(self._pending_cognition.values()):
            try:
                self._finish_cognition_turn(turn, "reset")
            except Exception as error:
                first_error = first_error or error
        self._cognition_receipts.clear()
        if first_error is not None:
            raise first_error

    def pending_cognition_jobs(self) -> tuple[PreparedCognitionJob, ...]:
        self._assert_cognition_owner()
        return tuple(turn.job for turn in self._pending_cognition.values() if turn.job is not None)

    def _assert_cognition_owner(self) -> None:
        if self._activation_handles and self._activation_owner_thread != get_ident():
            raise RuntimeError("activation must run on its owner thread")
        if any(turn.owner_thread != get_ident() for turn in self._pending_cognition.values()):
            raise RuntimeError("cognition continuation must run on its owner thread")

    def _advance_cognition(self, turn: PendingCognitionTurn, *, output=None, error=None) -> CognitionAdvance:
        try:
            if error is not None:
                request = turn.steps.throw(error)
            elif turn.stage:
                request = turn.steps.send(output)
            else:
                request = next(turn.steps)
            turn.stage += 1
            turn.policy_id = request.policy_id
            # 日志使用同一请求；存储失败必须终止，不能注入模型 fallback。
            if request.task_kind == "l2_reasoning":
                self._record_reasoning_request(turn.actor_id, turn.producer_ts, json.loads(request.request_json))
            revisions = self._capture_cognition_pin(turn.actor_id, policy_id=request.policy_id)
            job_id = f"{turn.turn_id}:{turn.stage}"
            turn.job = PreparedCognitionJob(job_id=job_id, turn_id=turn.turn_id, stage=turn.stage,
                task_kind=request.task_kind, actor_id=turn.actor_id, request_json=request.request_json,
                generation=self._cognition_generation, source_revision_vector=revisions,
                read_set_digest=self._cognition_digest(revisions), idempotency_key=job_id,
                activation_lock_ref=turn.activation_lock_ref, activation_token=turn.activation_token,
                deadline_monotonic=turn.deadline_monotonic, token=uuid4().hex)
            return CognitionAdvance("pending", next_job=turn.job)
        except StopIteration as done:
            self._finish_cognition_turn(turn, "completed")
            return CognitionAdvance("completed", result=done.value)
        except BaseException:
            self._finish_cognition_turn(turn, "failed")
            raise

    def _finish_cognition_turn(self, turn: PendingCognitionTurn, reason: str) -> None:
        if self._pending_cognition.get(turn.actor_id) is not turn:
            return
        self._pending_cognition.pop(turn.actor_id)
        try:
            turn.steps.close()
        finally:
            if turn.on_finished is not None:
                turn.on_finished(turn.turn_id, reason)

    def _remember_cognition_receipt(self, job, fingerprint, advance) -> None:
        self._cognition_receipts[job.job_id] = (job, fingerprint, deepcopy(advance))
        while len(self._cognition_receipts) > 32:
            self._cognition_receipts.popitem(last=False)

    @staticmethod
    def _cognition_digest(value) -> str:
        def encode(item):
            if isinstance(item, BaseModel):
                return item.model_dump(mode="json")
            if is_dataclass(item):
                return asdict(item)
            raise TypeError(f"unsupported cognition pin value: {type(item).__name__}")
        return hashlib.sha256(json.dumps(value, default=encode, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()

    def _cognition_social_ticks(self, actor_id):
        return [[*key[1:], value] for key, value in sorted(self._last_social_request_tick_ms.items()) if key[0] == actor_id]

    def _capture_cognition_pin(self, actor_id: str, *, policy_id: str = "") -> tuple[tuple[str, str], ...]:
        # memory 的生产写入口同步推进本人 timeline/continuity；外置 store 独立写入需另加 actor revision。
        # 只读现有状态，不调 recall、working-memory builder 或会隐式创建状态的 helper。
        values = {
            "timeline": self.get_memory_revision(actor_id),
            "continuity_revision": self._continuity_revisions.get(actor_id, 0),
            "l1": self._l1.get_snapshot(actor_id),
            "control_mode": self.get_control_mode(actor_id),
            "background_mode": self.get_background_mode(actor_id),
            "background_enabled": self._background_cognition_enabled,
            "supervision": self._supervision_states.get(actor_id),
            "profile": self._profile_payload(actor_id),
            "effective_profile": self._effective_profile_payload(actor_id),
            "l2_profile": self._l2._profile_cache.get(actor_id,
                self._profile_payload(actor_id) if self._l2._profile_registry is self._profile_registry else None),
            "needs": self._need_tension_store.read(actor_id),
            "dynamic": self._dynamic_state_store.read_record(actor_id),
            "goal": self._goal_state_store.read(actor_id),
            "goal_history": self._goal_state_store.history(actor_id),
            "tensions": self._unresolved_tension_store.recall(actor_id),
            "agenda": self._background_agenda_states.get(actor_id),
            "continuity": self._continuity_state.get(actor_id, RuntimeContinuityState(actor_id=actor_id)),
            "wake_up": self._wake_up_signals.get(actor_id),
            "last_background": self._last_background_tick_ms.get(actor_id),
            "last_cognition": self._last_cognition_tick_ms.get(actor_id),
            "cadence": self._cadence_policy,
            "social_ticks": self._cognition_social_ticks(actor_id),
            "policy_consumed": bool(policy_id and policy_id in self._l3._consumed_behavior_policy_ids),
        }
        return tuple((key, self._cognition_digest(value)) for key, value in sorted(values.items()))

    def _drain_cognition(self, **kwargs):
        with self._sync_cognition_lock:
            payload = kwargs.get("payload")
            fields = payload if isinstance(payload, dict) else (payload.model_dump() if payload is not None else {})
            actor_id = kwargs.get("actor_id") or fields.get("actor_id", "")
            if kwargs["source_kind"] == "ingest_siming_output":
                actor_id = fields.get("target_actor_id") or actor_id
            handle = self._sync_activation_handles.get(actor_id)
            if handle is not None:
                kwargs.update(activation_lock_ref=handle.lock_ref, activation_token=handle.token,
                              activation_is_current=self.activation_is_current)
            advance = self.prepare_cognition_job(**kwargs)
            while advance.status == "pending":
                job = advance.next_job
                gateway = self._l2._gateway if job.task_kind == "l2_reasoning" else self._l3._gateway
                try:
                    output = gateway.complete_prepared_request(job.request_json)
                except Exception as error:
                    advance = self.commit_cognition_result(job, error=error)
                else:
                    advance = self.commit_cognition_result(job, output=output)
            if advance.result is not None:
                return advance.result
            if kwargs["source_kind"] == "run_background_cognition_tick":
                return CharacterBackgroundCognitionResult(actor_id=kwargs["actor_id"],
                    producer_ts=kwargs["producer_ts"], ran=False, reason=advance.reason)
            return []

    def _ingest_character_perceived_event_steps(self, event: CharacterPerceivedEvent) -> Generator[CognitionRequest, dict[str, object], list[CharacterGoalCommand]]:
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
        need_tension_event = self._need_tension_event_payload(event, snapshot)
        need_delta = self._need_tension_engine.evaluate(
            effective_profile=effective_profile,
            event=need_tension_event,
        )
        need_tension_state = self._need_tension_store.merge_delta(
            event.actor_id,
            self._need_tension_delta_payload(need_delta),
        )
        self._record_need_tension_state_event(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            need_tension_state=need_tension_state,
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
        interpretation = yield from self._interpret_with_continuity_floor(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            control_mode=self.get_control_mode(event.actor_id),
            source_stage="character_perceived_event",
            run_model=lambda memory_override=None: self._l2.prepare_perceived_event(
                snapshot,
                event,
                memory_bundle=memory_override if memory_override is not None else memory_record_bundle,
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
            working_memory_state = self.get_working_memory_state_record(event.actor_id, snapshot.model_dump())
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
        decision = yield from self._select_intent_with_continuity_floor(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            interpretation=interpretation,
            control_mode=self.get_control_mode(event.actor_id),
            source_stage="character_perceived_event",
            run_model=lambda memory_override=None: self._l3.prepare_intent_plan(
                interpretation=interpretation,
                snapshot=snapshot.model_dump(),
                profile=self._profile_payload(event.actor_id),
                effective_profile=effective_profile,
                memory_bundle=memory_override if memory_override is not None else memory_record_bundle,
                control_mode=self.get_control_mode(event.actor_id),
                working_memory_state=working_memory_state,
                current_goal_state=current_goal_state,
                goal_state_history=goal_state_history,
                supervision_state=supervision_state,
                unresolved_tensions=unresolved_tensions,
                background_agenda_state=self.get_background_agenda_state(event.actor_id),
                need_tension_state=need_tension_state,
                dynamic_state=self.get_dynamic_state_record(event.actor_id).model_dump(),
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
                else (yield from self._planner_suggestion_packet(
                    actor_id=event.actor_id,
                    producer_ts=event.producer_ts,
                    interpretation=interpretation,
                    working_memory_state=working_memory_state,
                ))
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
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="character_supervision_request",
            producer_ts=producer_ts,
            payload=request.model_dump(),
        )
        self._project_session_event(stored)
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
        stored = self._append_session_event(
            actor_id=record.actor_id,
            event_type="character_supervision_authorization",
            producer_ts=record.producer_ts or record.effective_from_ts,
            payload=record.model_dump(),
        )
        self._project_session_event(stored)
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
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="character_supervision_cleared",
            producer_ts=producer_ts,
            payload=refreshed.model_dump(),
        )
        self._project_session_event(stored)
        return refreshed.model_copy(deep=True)

    def get_unresolved_tensions(self, actor_id: str) -> list[dict[str, object]]:
        return self._unresolved_tension_store.recall(actor_id)

    def get_background_agenda_state(self, actor_id: str) -> dict[str, object]:
        state = self._background_agenda_states.get(actor_id)
        return state.model_dump() if state is not None else {}

    def _ingest_self_body_perceived_event_steps(self, event: SelfBodyPerceivedEvent) -> Generator[CognitionRequest, dict[str, object], list[CharacterGoalCommand]]:
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
        interpretation = yield from self._interpret_with_continuity_floor(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            control_mode=self.get_control_mode(event.actor_id),
            source_stage="self_body_perceived_event",
            run_model=lambda memory_override=None: self._l2.prepare_self_body_event(
                snapshot,
                event,
                memory_bundle=memory_override if memory_override is not None else memory_record_bundle,
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
        decision = yield from self._select_intent_with_continuity_floor(
            actor_id=event.actor_id,
            producer_ts=event.producer_ts,
            snapshot=snapshot,
            interpretation=interpretation,
            control_mode=self.get_control_mode(event.actor_id),
            source_stage="self_body_perceived_event",
            run_model=lambda memory_override=None: self._l3.prepare_intent_plan(
                interpretation=interpretation,
                snapshot=snapshot.model_dump(),
                profile=self._profile_payload(event.actor_id),
                memory_bundle=memory_override if memory_override is not None else memory_record_bundle,
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
                else (yield from self._planner_suggestion_packet(
                    actor_id=event.actor_id,
                    producer_ts=event.producer_ts,
                    interpretation=interpretation,
                    working_memory_state=working_memory_state,
                ))
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

    def _plan_siming_entry(self, payload: dict[str, object] | SimingCharacterCompatibilityInput) -> dict[str, object]:
        validated = payload if isinstance(payload, SimingCharacterCompatibilityInput) else SimingCharacterCompatibilityInput.model_validate(payload)
        normalized = self._normalize_siming_payload(validated.model_dump(exclude_none=True))
        actor_id = str(normalized.get('target_actor_id') or normalized.get('actor_id') or '')
        if not self.supports_actor(actor_id):
            return dict(actor_id=actor_id, supported=False, events=[], after={})
        normalized['target_actor_id'] = actor_id
        producer_ts = int(normalized.get('producer_ts', 0) or 0)
        supervision = self._plan_weak_supervision_from_siming(actor_id=actor_id, payload=normalized, producer_ts=producer_ts)
        events = []
        pressure = str(normalized.get('pressure_hint', '') or '').strip()
        tension = self._plan_unresolved_tension(actor_id=actor_id, category='siming_pressure', summary=pressure,
            target_ref=str(normalized.get('target_environment_id', '') or normalized.get('target_object_id', '') or actor_id),
            producer_ts=producer_ts, source_event_id=str(normalized.get('message_id', '') or ''),
            source_stage='siming_output_event', priority=.8)
        if tension is not None:
            events.append(dict(event_type='character_unresolved_tension_event', producer_ts=producer_ts,
                payload=tension.model_dump(mode='json')))
        events.append(dict(event_type='siming_output_event', producer_ts=producer_ts, payload=self._siming_event_payload(normalized)))
        wake = deepcopy(self._wake_up_signals.get(actor_id))
        if self._is_wake_up_input(normalized):
            wake = dict(wake_up_requested=True, salience=float(normalized.get('salience_boost', 0.) or 0.), producer_ts=producer_ts)
        return dict(actor_id=actor_id, supported=True, normalized_payload=normalized, events=events,
            after=dict(supervision_state=supervision.model_dump(mode='json'), wake_up=wake,
                private_snapshot=self._l1.plan_siming_output(normalized).model_dump(mode='json')))

    def _cognition_entry_self_write_pin(self, actor_id: str, plan: dict[str, object]) -> dict[str, str]:
        after = plan['after']['entry_after']
        tensions = CharacterUnresolvedTensionStore()
        for tension in self._unresolved_tension_store.recall_records(actor_id):
            tensions.upsert(actor_id, tension)
        for event in plan['events']:
            if event['event_type'] == 'character_unresolved_tension_event':
                tensions.upsert(actor_id, event['payload'])
        values = dict(timeline=plan['expected_revision'] + len(plan['events']), tensions=tensions.recall(actor_id),
            l1=after['private_snapshot'], supervision=after['supervision_state'], wake_up=after['wake_up'])
        if 'cadence' in plan['after']:
            values['last_cognition'] = plan['after']['cadence']['last_tick']
        # 首个 session 后正常启动会物化空 continuity；只认可这个确定默认值。
        if actor_id not in self._continuity_state:
            values['continuity'] = RuntimeContinuityState(actor_id=actor_id)
        if plan['after']['source_kind'] == 'ingest_siming_output' and after['supervision_state']['current_level'] not in {'medium', 'strong'}:
            values['background_mode'] = after['supervision_state']['active_constraints']['background_mode']
        return {field: self._cognition_digest(value) for field, value in values.items()}

    def _install_cognition_entry_after(self, actor_id: str, plan: dict[str, object]) -> None:
        after = plan['after']['entry_after']
        if after is None:
            return
        snapshot = CharacterPrivateWorldSnapshot.model_validate(after['private_snapshot'])
        supervision = CharacterSupervisionState.model_validate(after['supervision_state'])
        tensions = [CharacterUnresolvedTension.model_validate(event['payload']) for event in plan['events']
            if event['event_type'] == 'character_unresolved_tension_event']
        if snapshot.actor_id != actor_id or supervision.actor_id != actor_id:
            raise ValueError('cognition_entry_after_actor_mismatch')
        # 安装冻结结果，不调用 L1 感知/监管刷新，也不再次生成 session 事件。
        self._l1._snapshots[actor_id] = snapshot
        self._supervision_states[actor_id] = supervision
        if plan['after']['source_kind'] == 'ingest_siming_output' and supervision.current_level not in {'medium', 'strong'}:
            self._background_modes[actor_id] = supervision.active_constraints.background_mode
        if after['wake_up'] is None:
            self._wake_up_signals.pop(actor_id, None)
        else:
            self._wake_up_signals[actor_id] = deepcopy(after['wake_up'])
        for tension in tensions:
            self._unresolved_tension_store.upsert(actor_id, tension)
        if 'cadence' in plan['after']:
            tick = plan['after']['cadence']['last_tick']
            if tick is not None:
                self._last_cognition_tick_ms[actor_id] = tick
        if 'last_background' in plan['after']:
            tick = plan['after']['last_background']
            if tick is None:
                self._last_background_tick_ms.pop(actor_id, None)
            else:
                self._last_background_tick_ms[actor_id] = tick
        if 'social_ticks' in plan['after']:
            self._last_social_request_tick_ms = {key: value for key, value in self._last_social_request_tick_ms.items() if key[0] != actor_id}
            self._last_social_request_tick_ms.update({(actor_id, kind, target): tick for kind, target, tick in plan['after']['social_ticks']})
        if 'l2_profile' in plan['after']:
            self._l2._profile_cache[actor_id] = deepcopy(plan['after']['l2_profile'])

    def _prepare_siming_l2_request(self, snapshot, payload, context, *, memory_override=None):
        return self._l2.prepare_siming_output(snapshot, payload,
            **dict(context, memory_bundle=context['memory_bundle'] if memory_override is None else memory_override))

    def _freeze_siming_l2_request(self, actor_id: str, frame: dict) -> tuple[bytes, dict]:
        snapshot = CharacterPrivateWorldSnapshot.model_validate(frame['entry_after']['private_snapshot'])
        context = dict(memory_bundle=self.get_memory_record_bundle(actor_id), control_mode=self.get_control_mode(actor_id),
            working_memory_state=self.get_working_memory_state_record(actor_id, snapshot.model_dump()),
            current_goal_state=self.get_goal_state(actor_id), goal_state_history=self.get_goal_state_history(actor_id),
            supervision_state=self.get_supervision_state(actor_id), unresolved_tensions=self.get_unresolved_tensions(actor_id),
            background_agenda_state=self.get_background_agenda_state(actor_id))
        if frame['source_kind'] == 'run_background_cognition_tick':
            background = self._background_reappraisal_payload(actor_id=actor_id, producer_ts=frame['producer_ts'],
                snapshot=snapshot, current_goal_state=context['current_goal_state'],
                unresolved_tensions=context['unresolved_tensions'], supervision_state=context['supervision_state'])
            request = self._run_with_memory_recall(actor_id, snapshot,
                lambda memory_override=None: self._l2.prepare_background_state(snapshot, background,
                    **dict(context, memory_bundle=context['memory_bundle'] if memory_override is None else memory_override)))
            context['background_payload'] = background
        else:
            request = self._run_with_memory_recall(actor_id, snapshot,
                lambda memory_override=None: self._prepare_siming_l2_request(snapshot, frame['normalized_payload'], context,
                    memory_override=memory_override))
        frozen = json.loads(json.dumps(context, default=lambda value: value.model_dump(mode='json'), allow_nan=False))
        return request, frozen

    def _prepare_siming_l3_request(self, actor_id, snapshot, interpretation, context, *, memory_override=None):
        return self._l3.prepare_intent_plan(
            interpretation=interpretation, snapshot=snapshot.model_dump(), profile=self._profile_payload(actor_id),
            memory_bundle=memory_override if memory_override is not None else context['memory_bundle'],
            control_mode=self.get_control_mode(actor_id), working_memory_state=context['working_memory_state'],
            current_goal_state=context['current_goal_state'], goal_state_history=context['goal_state_history'],
            supervision_state=context['supervision_state'], unresolved_tensions=context['unresolved_tensions'],
            background_agenda_state=self.get_background_agenda_state(actor_id))

    def _freeze_siming_l3_request(self, actor_id: str, frame: dict):
        snapshot = CharacterPrivateWorldSnapshot.model_validate(frame['entry_after']['private_snapshot'])
        interpretation = CharacterInterpretation.model_validate(frame['interpretation'])
        return self._run_with_memory_recall(actor_id, snapshot,
            lambda memory_override=None: self._prepare_siming_l3_request(actor_id, snapshot, interpretation,
                frame['context'], memory_override=memory_override))

    def _plan_l3_effects(self, frame: dict, output: dict, *, fallback=None):
        from app.character_agent.planning.l3_planner import PreparedCharacterIntentPlan
        from app.character_agent.runtime.session_recovery import goal_state_from_event
        prepared = PreparedCharacterIntentPlan.from_json_value(frame['l3_prepared'])
        if fallback is None:
            result = self._l3.plan_intent_completion(prepared, output)
            decision = self._l3.decision_from_plan(result, interpretation=prepared.interpretation)
        else:
            decision = CharacterIntentDecision.model_validate(fallback)
        actor_id = frame['actor_id']
        goal = self._plan_goal_state_event(actor_id, decision)
        goals = CharacterGoalStateStore()
        for previous in self._goal_state_store.history(actor_id):
            goals.write(actor_id, previous)
        goals.write(actor_id, goal_state_from_event(actor_id, goal))
        own = {field: self._cognition_digest(value) for field, value in dict(
            goal=goals.read(actor_id), goal_history=goals.history(actor_id),
            policy_consumed=bool(frame.get('policy_id')) if fallback is None else bool(frame.get('policy_id') in self._l3._consumed_behavior_policy_ids)).items()}
        return [dict(event_type='goal_state_event', producer_ts=frame['producer_ts'], payload=goal)], decision.model_dump(mode='json'), own

    def _ingest_siming_output_steps(
        self,
        payload: dict[str, object] | SimingCharacterCompatibilityInput,
    ) -> Generator[CognitionRequest, dict[str, object], list[CharacterGoalCommand]]:
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
        interpretation = yield from self._interpret_with_continuity_floor(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            control_mode=self.get_control_mode(actor_id),
            source_stage="siming_output_event",
            run_model=lambda memory_override=None: self._prepare_siming_l2_request(snapshot, normalized_payload,
                dict(memory_bundle=memory_record_bundle, control_mode=self.get_control_mode(actor_id),
                    working_memory_state=working_memory_state, current_goal_state=current_goal_state,
                    goal_state_history=goal_state_history, supervision_state=supervision_state,
                    unresolved_tensions=unresolved_tensions, background_agenda_state=self.get_background_agenda_state(actor_id)),
                memory_override=memory_override),
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
        decision = yield from self._select_intent_with_continuity_floor(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            interpretation=interpretation,
            control_mode=self.get_control_mode(actor_id),
            source_stage="siming_output_event",
            run_model=lambda memory_override=None: self._prepare_siming_l3_request(
                actor_id, snapshot, interpretation,
                dict(memory_bundle=memory_record_bundle, working_memory_state=working_memory_state,
                    current_goal_state=current_goal_state, goal_state_history=goal_state_history,
                    supervision_state=supervision_state, unresolved_tensions=unresolved_tensions),
                memory_override=memory_override),
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
                else (yield from self._planner_suggestion_packet(
                    actor_id=actor_id,
                    producer_ts=int(normalized_payload.get("producer_ts", 0) or 0),
                    interpretation=interpretation,
                    working_memory_state=working_memory_state,
                ))
            )
            self._pending_suggestions.append(packet)
            return []
        execution_plan = self._record_execution_plan(
            actor_id,
            int(normalized_payload.get("producer_ts", 0) or 0),
            snapshot,
            interpretation,
            decision,
            causation_id=str(normalized_payload.get("causation_id", "") or ""),
            correlation_id=str(normalized_payload.get("correlation_id", "") or ""),
        )
        return self.filter_commands_for_actor(
            actor_id,
            self._l4.build_commands_from_execution_plan(execution_plan),
        )

    def supports_actor(self, actor_id: str) -> bool:
        return actor_id in self._supported_actor_ids

    def supports_continuity_actor(self, actor_id: str) -> bool:
        """Return whether Character Core can persist dormant continuity for an actor."""
        return actor_id in self._supported_actor_ids or actor_id in self._continuity_actor_ids

    def character_identity_digest(self, actor_id: str) -> str:
        if not self.supports_actor(actor_id):
            raise ValueError(f"unsupported actor_id: {actor_id}")
        return self._profile_registry.authored_identity_digest(f"character:{actor_id}")

    def get_continuity_revision(self, actor_id: str) -> int:
        if not self.supports_continuity_actor(actor_id):
            raise ValueError(f"unsupported actor_id: {actor_id}")
        return int(self._continuity_revisions.get(actor_id, 0))

    def get_shared_module_state(self, actor_id: str) -> dict[str, dict[str, object]]:
        """Return Character Core's replayable shared modules, never private cognition."""
        if not self.supports_continuity_actor(actor_id):
            raise ValueError(f"unsupported actor_id: {actor_id}")
        return deepcopy(self._shared_module_states.get(actor_id, {}))

    def activation_lock_is_active(self, actor_id: str) -> bool:
        """Expose the existing activation lock without leaking authority state."""
        if not self.supports_actor(actor_id):
            raise ValueError(f"unsupported actor_id: {actor_id}")
        authority = self._activation_authority
        return bool(
            authority is not None
            and authority.is_lock_active(
                world_ref=self._activation_world_ref,
                profile_ref=f"character:{actor_id}",
            )
        )

    def activate_actor(
        self,
        actor_id: str,
        decision: ActivationDecision,
        *,
        producer_ts: int,
        cognition_callback: Callable[[], object] | None = None,
    ) -> ActivationReceipt:
        # 旧同步入口沿用相同 lease；异步调用者直接 begin/finish，不在网络等待时持锁。
        with self._sync_cognition_lock:
            handle, receipt = self.begin_actor_activation(actor_id, decision, producer_ts=producer_ts)
            if handle is None:
                return receipt
            try:
                self._sync_activation_handles[actor_id] = handle
                if cognition_callback is not None:
                    cognition_callback()
            except BaseException as error:
                self._abort_actor_activation(handle, error)
                raise
            finally:
                self._sync_activation_handles.pop(actor_id, None)
            return self.finish_actor_activation(handle, reason="completed").model_copy(
                update={"lock_scope": "synchronous_callback"})

    def begin_actor_activation(
        self, actor_id: str, decision: ActivationDecision, *, producer_ts: int,
        deadline_monotonic: float | None = None,
    ) -> tuple[ActivationHandle | None, ActivationReceipt]:
        """Owner 获取跨阶段 lease；所有 admission 拒绝均先于锁和私有记忆写入。"""
        self._assert_cognition_owner()
        profile_ref = f"character:{actor_id}"
        authority = self._activation_authority
        deadline = monotonic() + 60.0 if deadline_monotonic is None else deadline_monotonic
        if not math.isfinite(deadline):
            raise ValueError("activation deadline must be finite")
        reason = None
        if authority is None:
            reason = "activation_authority_unavailable"
        elif not self.supports_actor(actor_id):
            reason = "unsupported_actor"
        elif decision.actor_id != actor_id or decision.state != "active":
            reason = "activation_decision_not_active"
        elif deadline <= monotonic():
            reason = "activation_deadline_expired"
        elif self._activation_ending:
            reason = "activation_cleanup_pending"
        elif actor_id in self._activation_handles or actor_id in self._pending_cognition:
            reason = "activation_lock_conflict"
        elif len(set(self._activation_handles) | set(self._pending_cognition)) >= 4:
            reason = "activation_capacity"
        elif authority.is_lock_active(world_ref=self._activation_world_ref, profile_ref=profile_ref):
            reason = "activation_lock_conflict"
        if reason:
            return None, ActivationReceipt(committed=False, status="requeued", profile_ref=profile_ref,
                                           zero_write=True, stop_reason=reason)
        stream = f"population:{self._activation_world_ref}"
        receipt = authority.lock(
            world_ref=self._activation_world_ref,
            profile_ref=profile_ref,
            expected_revision=authority.store.get_stream_head(stream),
        )
        if not receipt.committed:
            return None, receipt.model_copy(update={"status": "requeued", "stop_reason": "activation_lock_conflict"})
        handle = ActivationHandle(actor_id, self._activation_world_ref, f"lock:{self._activation_world_ref}:{profile_ref}",
                                  uuid4().hex, self._activation_generation, deadline)
        self._activation_handles[actor_id] = handle
        self._activation_owner_thread = get_ident()
        try:
            if decision.load_private_memory:
                self.materialize_pending_seed_memories(actor_id, producer_ts)
        except BaseException as error:
            self._abort_actor_activation(handle, error)
            raise
        return handle, receipt.model_copy(update={"lock_scope": "asynchronous_turn", "lock_released": False})

    def activation_is_current(self, lock_ref: str, token: str) -> bool:
        self._assert_cognition_owner()
        return any(handle.lock_ref == lock_ref and handle.token == token
                   and handle.generation == self._activation_generation
                   and token not in self._activation_ending and monotonic() < handle.deadline_monotonic
                   and self.activation_lock_is_active(handle.actor_id)
                   for handle in self._activation_handles.values())

    def pending_actor_activations(self) -> tuple[ActivationHandle, ...]:
        self._assert_cognition_owner()
        return tuple(self._activation_handles.values())

    def finish_actor_activation(self, handle: ActivationHandle, *, reason: str) -> ActivationReceipt:
        """结束请求先失效 token；释放失败保留清理义务，旧 handle 不能释放新持有者。"""
        self._assert_cognition_owner()
        previous = self._activation_receipts.get(handle.token)
        if previous is not None and previous[0] == handle:
            return previous[1].model_copy(update={"zero_write": True, "idempotency_status": "duplicate_replayed"}, deep=True)
        if self._activation_handles.get(handle.actor_id) != handle:
            return ActivationReceipt(committed=False, status="rejected", profile_ref=f"character:{handle.actor_id}",
                                     zero_write=True, stop_reason="activation_token_invalid")
        self._activation_ending.add(handle.token)
        authority = self._activation_authority
        release = authority.release_lock(lock_ref=handle.lock_ref,
            expected_revision=authority.store.get_stream_head(f"population:{handle.world_ref}"))
        if not release.committed:
            return release.model_copy(update={"status": "requeued", "lock_scope": "asynchronous_turn", "lock_released": False})
        receipt = release.model_copy(update={"status": "active" if reason == "completed" else "requeued",
                                             "lock_scope": "asynchronous_turn", "lock_released": True})
        self._activation_handles.pop(handle.actor_id)
        self._activation_ending.discard(handle.token)
        if not self._activation_handles:
            self._activation_owner_thread = None
        self._activation_receipts[handle.token] = (handle, receipt.model_copy(deep=True))
        while len(self._activation_receipts) > 32:
            self._activation_receipts.popitem(last=False)
        return receipt

    def _abort_actor_activation(self, handle: ActivationHandle, error: BaseException) -> None:
        try:
            self.finish_actor_activation(handle, reason="failed")
        except BaseException as cleanup_error:
            raise error from cleanup_error

    def reset_actor_activations(self) -> None:
        self._assert_cognition_owner()
        first_error = None
        for handle in tuple(self._activation_handles.values()):
            try:
                receipt = self.finish_actor_activation(handle, reason="reset")
                if not receipt.lock_released:
                    raise RuntimeError(receipt.stop_reason or "activation_release_failed")
            except Exception as error:
                first_error = first_error or error
        self._activation_generation = uuid4().hex
        self._activation_receipts.clear()
        if first_error is not None:
            raise first_error

    def set_activation_authority(self, authority: ProfileActivationAuthority) -> None:
        if self._activation_handles and authority is not self._activation_authority:
            raise RuntimeError("cannot replace authority while activation cleanup is pending")
        self._activation_authority = authority

    def record_character_perceived_event_without_cognition(self, event: CharacterPerceivedEvent) -> None:
        if not self.supports_actor(event.actor_id):
            return
        self._record_character_perceived_event(event)
        self._record_relational_belief_from_perceived_event(event)

    def get_private_snapshot(self, actor_id: str):
        return self._l1.get_snapshot(actor_id)

    def ingest_canonical_percept_bundle(self, bundle: CanonicalPerceptBundle) -> CharacterPrivateWorldSnapshot:
        if not self.supports_actor(bundle.subject_id):
            raise ValueError(f"unsupported actor_id: {bundle.subject_id}")
        snapshot = self._l1.apply_canonical_percept_bundle(bundle)
        stored = self._append_session_event(
            actor_id=bundle.subject_id,
            event_type="canonical_percept_bundle",
            producer_ts=snapshot.producer_ts,
            payload=bundle.model_dump(),
        )
        self._project_session_event(stored)
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
        )
        return snapshot

    def get_session_timeline(self, actor_id: str) -> list[dict[str, object]]:
        return self._session_timeline_after(actor_id, 0)

    def _session_timeline_event_count(self, actor_id: str) -> int:
        return self._session_store.event_count(actor_id)

    def _session_timeline_after(self, actor_id: str, event_count: int) -> list[dict[str, object]]:
        return self._session_store.list_events_after(actor_id, event_count)

    def apply_character_continuity_command(
        self, command: CharacterContinuityCommand
    ) -> CharacterContinuityReceipt:
        return self._continuity_service.apply_command(command)

    def get_memory_revision(self, actor_id: str) -> int:
        """使用角色事件时间线的版本，普通认知写入也会使旧修复请求失效。"""
        return self._session_timeline_event_count(actor_id)

    def get_target_memory_record_bundle(self, actor_id: str, subject_refs: set[str]) -> CharacterMemoryRecordBundle:
        """按当前目标补查本人的已获知经历，不访问世界真相或其他角色。"""
        projection = CharacterAgentMemoryStore()
        # ponytail: 按需扫描单个角色时间线；历史量显著增长后增加角色内命题索引。
        for event in self.get_session_timeline(actor_id):
            payload = event.get("payload", {})
            claim = payload.get("fact_claim") if isinstance(payload, dict) else None
            if event.get("event_type") == "character_memory_correction":
                claim = payload.get("knowledge", {}).get("claim")
            if isinstance(claim, dict) and claim.get("subject_ref") in subject_refs:
                projection.write_event(event)
        bundle = projection.retrieval_record_bundle(actor_id)
        sources = {source for record in bundle.knowledge_memories for source in
            (record.source_event_id, record.claim.source_ref if record.claim else "") if source}
        return bundle.model_copy(update={
            "event_memories": [record for record in bundle.event_memories if record.source_event_id in sources or sources.intersection(record.refs)],
            "observation_memories": [record for record in bundle.observation_memories if record.source_event_id in sources or sources.intersection(record.refs)],
        })

    def _run_with_memory_recall(self, actor_id: str, snapshot: CharacterPrivateWorldSnapshot, run_model):
        try:
            return run_model()
        except MissingRequiredMemoryEvidence as error:
            subjects = set(snapshot.current_attention_targets or snapshot.attention_targets)
            focused = self.get_target_memory_record_bundle(actor_id, subjects)
            found = {record.memory_id for name in type(focused).model_fields for record in getattr(focused, name)}
            if not subjects or any(ref.split(":", 1)[-1] not in found for ref in error.missing_required_refs):
                raise
            return run_model(focused)

    def run_memory_consistency_pass(self, actor_id: str, producer_ts: int) -> MemoryConsistencyResult:
        """按需核对一个角色的已知冲突；真相只用于裁决，获知仍须经过感知链。"""
        result = MemoryConsistencyResult(actor_id=actor_id, producer_ts=producer_ts, status="no_conflicts")
        with self._memory_correction_lock:
            if not self._profile_registry.contains(actor_id):
                return result.model_copy(update={"status": "policy_skipped"})
            profile = self._effective_profile_payload(actor_id)
            deliberation = profile["personality_layer"]["facets"]["conscientiousness"]["deliberation"]
            if deliberation < 0.6:
                return result.model_copy(update={"status": "policy_skipped"})
            # 复用严谨性与记忆保持设定；毫秒时钟下普通角色一分钟，强记忆角色五分钟。
            interval = 300_000 if profile["capability_constraint_layer"].get("memory_retention") == "strong" else 60_000
            # ponytail: 按需扫描单个角色的历史；历史量显著增长后改用角色内检查时间索引。
            timeline = self.get_session_timeline(actor_id)
            if producer_ts < max((int(event["producer_ts"]) for event in timeline), default=0):
                raise ValueError("memory consistency pass predates actor events")
            last_check = max((int(event["producer_ts"]) for event in timeline
                if event["event_type"] == "character_memory_consistency_checked"), default=None)
            if last_check is not None and producer_ts < last_check + interval:
                return result.model_copy(update={"status": "rate_limited", "next_check_at": last_check + interval})
            entries = [entry for entry in self._l1.get_actor_scene_knowledge_store().entries_for_actor(actor_id)
                if entry.conflict_state == "conflicted"]
            if not entries:
                return result
            conflict_refs = tuple(conflict.conflict_id for entry in entries for conflict in entry.conflicts if not conflict.resolved)
            truth_wins = False
            if self._memory_source_resolver is not None:
                for entry in entries:
                    for source_ref in dict.fromkeys(source for conflict in entry.conflicts if not conflict.resolved
                        for source in conflict.source_refs):
                        source = self._memory_source_resolver(source_ref)
                        if source is not None and compare_memory_claims(entry.claim, source.claim) == "conflicted":
                            truth_wins = True
            requests = []
            for room_id, scene_id in dict.fromkeys((entry.session_id, entry.scene_id) for entry in entries):
                requests.extend(self.get_memory_verification_requests(actor_id, producer_ts=producer_ts,
                    room_id=room_id, scene_id=scene_id, source_entry_ids={entry.entry_id for entry in entries
                        if entry.session_id == room_id and entry.scene_id == scene_id}))
            result = result.model_copy(update={"status": "truth_wins" if truth_wins else "verification_required",
                "conflict_refs": conflict_refs, "verification_request_refs": tuple(request.request_id for request in requests),
                "next_check_at": producer_ts + interval})
            # 持久化检查时间以便重启后保持限频；不写有效记忆，也不隐式调用 edit。
            self._append_session_event(actor_id=actor_id, event_type="character_memory_consistency_checked",
                producer_ts=producer_ts, payload=result.model_dump(mode="json"))
            self._persist_graph_continuity(actor_id=actor_id, producer_ts=producer_ts)
            return result

    def get_memory_verification_requests(
        self, actor_id: str, *, producer_ts: int, room_id: str = "room_demo",
        scene_id: str = "scene_demo", zone_id: str = "zone_focus",
        source_entry_ids: set[str] | None = None,
    ):
        """只为当前角色已知的异常生成一次感知请求，由现有 provider 链执行。"""
        requests = ActivePerceptionPlanner().requests_for_actor(
            self._l1.get_actor_scene_knowledge_store(), actor_id=actor_id, session_id=room_id,
            room_id=room_id, scene_id=scene_id, zone_id=zone_id)
        if source_entry_ids is not None:
            requests = [request for request in requests if source_entry_ids.intersection(request.source_entry_ids)]
        timeline = self.get_session_timeline(actor_id)
        consumed = {event.get("payload", {}).get("verification_request_ref") for event in timeline}
        pending = [event["payload"] for event in timeline
            if event.get("event_type") == "character_memory_verification_requested"
            and event["payload"]["request_id"] not in consumed]
        created = False
        for index, request in enumerate(requests):
            existing = next((item for item in pending if all(item.get(key) == getattr(request, key)
                for key in ("session_id", "scene_id", "subject_ref", "reason", "source_entry_ids"))), None)
            if existing is not None:
                requests[index] = ActivePerceptionRequest.model_validate(existing)
                continue
            request.request_id += f":{self.get_memory_revision(actor_id)}"
            request.to_pqf(started_at=producer_ts, ended_at=producer_ts)
            self._session_append_event(actor_id=actor_id, event_type="character_memory_verification_requested",
                producer_ts=producer_ts, payload=request.model_dump())
            created = True
        if created:
            self._persist_graph_continuity(actor_id=actor_id, producer_ts=producer_ts)
        return requests

    def apply_memory_verification_result(self, result: ActivePerceptionResult, *, producer_ts: int) -> None:
        """消费可信后端 provider 的实际回执；不接受客户端或模型自报的感知结果。"""
        result = ActivePerceptionResult.model_validate(result.model_dump())
        timeline = self.get_session_timeline(result.actor_id)
        request_event = next((event for event in timeline if event.get("event_type") == "character_memory_verification_requested"
            and event.get("payload", {}).get("request_id") == result.request_id), None)
        if request_event is None:
            raise ValueError("memory verification request not found")
        request = request_event["payload"]
        if any(request.get(key) != getattr(result, key) for key in ("actor_id", "session_id", "scene_id", "subject_ref", "pqf_query_id")):
            raise ValueError("memory verification result does not match request")
        if producer_ts < int(request_event["producer_ts"]):
            raise ValueError("memory verification result predates request")
        for event in timeline:
            payload = event.get("payload", {})
            if payload.get("verification_request_ref") == result.request_id:
                if payload.get("verification_result") != result.model_dump() or event["producer_ts"] != producer_ts:
                    raise ValueError("memory verification request already consumed with different result")
                self._persist_graph_continuity(actor_id=result.actor_id, producer_ts=producer_ts)
                self._project_session_event(event)
                self._update_memory_scene_knowledge(event)
                return
        store = self._l1.get_actor_scene_knowledge_store()
        entries = [entry for entry in store.entries_for_actor(result.actor_id, session_id=result.session_id, scene_id=result.scene_id)
            if entry.entry_id in request["source_entry_ids"] and entry.subject_ref == result.subject_ref]
        if result.fact_claim is not None:
            if any(entry.claim and (entry.claim.scope_ref, entry.claim.predicate) !=
                (result.fact_claim.scope_ref, result.fact_claim.predicate) for entry in entries):
                raise ValueError("memory verification claim scope does not match request")
            if result.fact_claim.valid_at < int(request_event["producer_ts"]):
                raise ValueError("memory verification claim predates request")
        conflict_refs = [conflict.conflict_id for entry in entries for conflict in entry.conflicts if not conflict.resolved]
        if result.conflict_refs and not set(result.conflict_refs).issubset(conflict_refs):
            raise ValueError("memory verification references unrelated conflict")
        projected_result = result.model_copy(update={"conflict_refs": result.conflict_refs or conflict_refs})
        # 先在副本检查；持久事件成功提交后，才修改角色的可重建认知投影。
        ActivePerceptionPlanner().apply_result(deepcopy(store), projected_result, producer_ts=producer_ts)
        self._record_character_perceived_event(CharacterPerceivedEvent(
            actor_id=result.actor_id, percept_channel="visual", producer_ts=producer_ts,
            room_id=request["room_id"], scene_id=result.scene_id, zone_id=request["zone_id"],
            perceived_summary=result.summary, source_candidate_event_id=result.result_id,
            target_object_id=result.subject_ref, certainty_score=result.confidence,
            source_ref_lineage=[result.result_id, result.request_id, result.pqf_query_id, *result.provider_result_refs],
            fact_claim=result.fact_claim,
        ), verification_result=result, verification_conflict_refs=projected_result.conflict_refs)

    def apply_memory_correction(
        self, request: MemoryCorrectionRequest, *, principal_ref: str,
    ) -> MemoryCorrectionReceipt:
        """按次修复已知证据；授权与源版本由服务端 owner 提供。"""
        request = MemoryCorrectionRequest.model_validate(request.model_dump())
        with self._memory_correction_lock:
            actor_id = request.actor_id
            timeline = self.get_session_timeline(actor_id)
            revision = len(timeline)
            local_revision = self._session_store.event_count(actor_id)
            def reject(reason: str) -> MemoryCorrectionReceipt:
                return MemoryCorrectionReceipt(request_id=request.request_id, actor_id=actor_id,
                    status="rejected", reason=reason, before_revision=revision, after_revision=revision)

            if not self.supports_continuity_actor(actor_id):
                return reject("target_unavailable")
            if self._memory_correction_authorizer is None or not self._memory_correction_authorizer(principal_ref, request):
                return reject("permission_denied")
            digest = hashlib.sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            for event in timeline:
                payload = event.get("payload", {})
                if event.get("event_type") != "character_memory_correction" or not isinstance(payload, dict):
                    continue
                if payload.get("idempotency_key") == request.idempotency_key or payload.get("request_id") == request.request_id:
                    if payload.get("request_digest") != digest:
                        return reject("idempotency_conflict")
                    # 已提交事件是回执和投影的共同来源，投影失败可以再次重建。
                    self._project_session_event(event)
                    self._persist_graph_continuity(actor_id=actor_id, producer_ts=int(event["producer_ts"]))
                    return MemoryCorrectionReceipt.model_validate(payload["receipt"])
            now = self._memory_now_ts_provider() if self._memory_now_ts_provider else max((int(event.get("producer_ts", 0)) for event in timeline), default=0)
            if now < request.requested_at or now >= request.expires_at:
                return reject("request_expired")
            if revision != request.expected_character_revision:
                return reject("character_revision_conflict")
            target = next((record for record in self.get_memory_record_bundle(actor_id).knowledge_memories
                if record.memory_id == request.target_memory_refs[0]), None)
            if target is None:
                return reject("target_memory_not_found")
            known: dict[str, MemoryFactClaim] = {}
            for event in timeline:
                payload = event.get("payload", {})
                if event.get("event_type") != "character_perceived_event" or not isinstance(payload, dict):
                    continue
                claim_payload = payload.get("fact_claim")
                if isinstance(claim_payload, dict) and int(event.get("producer_ts", 0)) <= now:
                    claim = MemoryFactClaim.model_validate(claim_payload)
                    if claim.source_ref in known and known[claim.source_ref] != claim:
                        return reject("source_conflict")
                    known[claim.source_ref] = claim
            if any(source not in known for source in request.source_refs):
                return reject("source_not_known")
            claims = [known[source] for source in request.source_refs]
            if any(memory_claim_key(claim) != target.proposition_key for claim in claims):
                return reject("source_target_mismatch")
            selected = max(claims, key=lambda claim: claim.valid_at)
            if any(memory_claim_key(claim) == target.proposition_key and claim.valid_at > selected.valid_at for claim in known.values()):
                return reject("source_superseded")
            if any(claim.valid_at == selected.valid_at and claim.value != selected.value for claim in claims):
                return reject("source_conflict")
            if self._memory_source_resolver is None:
                return reject("source_validation_unavailable")
            for source in request.source_refs:
                authoritative = self._memory_source_resolver(source)
                if authoritative is None or authoritative.revision != request.source_revision_vector[source]:
                    return reject("source_revision_conflict")
                if authoritative.claim != known[source]:
                    return reject("source_content_mismatch")
            receipt = MemoryCorrectionReceipt(request_id=request.request_id, actor_id=actor_id,
                status="applied", before_revision=revision, after_revision=revision + 1,
                applied_memory_refs=request.target_memory_refs, source_refs=request.source_refs)
            knowledge = target.model_copy(update={"claim": selected,
                "proposition": f"{selected.subject_ref}:{selected.predicate}={selected.value}",
                "state": "high_confidence_believed", "confidence": 1.0, "producer_ts": now})
            try:
                stored = self._append_session_event(actor_id=actor_id,
                    event_type="character_memory_correction", producer_ts=now,
                    expected_revision=local_revision, payload={
                        "request_id": request.request_id, "idempotency_key": request.idempotency_key,
                        "request_digest": digest, "principal_ref": principal_ref, "reason": request.reason,
                        "source_refs": list(request.source_refs), "source_revision_vector": request.source_revision_vector,
                        "supersedes": target.source_event_id, "knowledge": knowledge.model_dump(mode="json"),
                        "receipt": receipt.model_dump(mode="json"),
                    })
            except ValueError as error:
                if str(error) == "character_revision_conflict":
                    return reject("character_revision_conflict")
                raise
            # 图模式也先提交可回放时间线；有效记忆只是该事件的派生投影。
            self._persist_graph_continuity(actor_id=actor_id, producer_ts=now)
            self._project_session_event(stored)
            return receipt

    def ingest_seed_projection(self, seed: object) -> list[CharacterGoalCommand]:
        # Public callers must use apply_character_continuity_command; this parser is internal.
        return []

    def get_seed_projection(self, actor_id: str) -> dict[str, object]:
        state = self._session_store.read_runtime_state(actor_id)
        event_id = state.get('seed_event_id') if state else None
        event = self._session_store.read_event(actor_id,event_id=event_id) if event_id else None
        return {key:deepcopy(value) for key,value in event['payload'].items() if key != 'continuity_commit'} if event else {}

    def get_pending_seed_candidates(self, actor_id: str) -> list[dict[str, object]]:
        return self._session_store.list_candidates(actor_id)

    def materialize_pending_seed_memories(
        self, actor_id: str, producer_ts: int
    ) -> list[CharacterMemoryMaterializationReceipt]:
        candidates = {value["candidate_id"]: CharacterMemoryCandidate.model_validate(value) for value in self.get_pending_seed_candidates(actor_id)}
        receipts: list[CharacterMemoryMaterializationReceipt] = []
        for candidate_id, candidate in list(candidates.items()):
            prior_payload = self._session_store.read_receipt(actor_id, kind="materialization", key=candidate_id)
            prior = CharacterMemoryMaterializationReceipt.model_validate(prior_payload) if prior_payload else None
            if prior is not None:
                if prior.status == "committed":
                    committed_event = self._session_store.read_committed_event_for_receipt(actor_id, kind="materialization", key=candidate_id)
                    if committed_event is None:
                        raise ValueError("character_materialization_commit_missing")
                    self._project_session_event(committed_event)
                receipts.append(
                    prior.model_copy(update={"status": "idempotent_replay"})
                )
                continue
            if candidate.exposure_basis not in {
                "affected_directly",
                "public_propagation",
                "observed",
                "participated",
            }:
                receipt = CharacterMemoryMaterializationReceipt(
                    candidate_id=candidate_id,
                    actor_ref=actor_id,
                    status="rejected",
                    refusal_reason="memory_materialization_denied",
                )
                self._remember_materialization_receipt(candidate_id, receipt)
                receipts.append(receipt)
                continue
            if producer_ts < candidate.knowledge_available_at:
                receipt = CharacterMemoryMaterializationReceipt(
                    candidate_id=candidate_id,
                    actor_ref=actor_id,
                    status="rejected",
                    refusal_reason="temporal_knowledge_denied",
                )
                self._remember_materialization_receipt(candidate_id, receipt)
                receipts.append(receipt)
                continue
            event_type, payload = self._memory_materialization_event(candidate, actor_id, candidate_id)
            receipt = CharacterMemoryMaterializationReceipt(
                candidate_id=candidate_id,
                actor_ref=actor_id,
                status="committed",
                selected_pool=self._memory_pool_for_candidate(candidate),
                memory_cursor=producer_ts,
            )
            event = self._append_session_event(
                actor_id=actor_id,
                event_type=event_type,
                producer_ts=producer_ts,
                payload={
                    **payload,
                    "materialization_receipt": receipt.model_dump(mode="json"),
                },
            )
            self._project_session_event(event)
            receipts.append(receipt)
        self._persist_graph_continuity(actor_id=actor_id, producer_ts=producer_ts)
        return receipts

    def _memory_pool_for_candidate(self, candidate: CharacterMemoryCandidate) -> str:
        return {
            "event_experience": "event_memory",
            "perceptual_observation": "observation_memory",
            "factual_knowledge": "knowledge_memory",
            "social_impression": "social_memory",
            "higher_order_belief": "higher_order_memory",
        }[candidate.candidate_kind]

    def _memory_materialization_event(
        self, candidate: CharacterMemoryCandidate, actor_id: str, candidate_id: str
    ) -> tuple[str, dict[str, object]]:
        source = candidate.source_event_refs[0]
        base = {"summary": candidate.summary, "candidate_id": candidate_id, "source_ref_lineage": list(candidate.source_event_refs)}
        if candidate.candidate_kind == "event_experience":
            return "character_agent_settlement_result", {**base, "result_type": "simulation_memory_materialized", "change_summary": candidate.summary}
        if candidate.candidate_kind == "perceptual_observation":
            return "character_perceived_event", {**base, "percept_channel": "simulation", "source_candidate_event_id": source, "clarity_score": candidate.confidence, "certainty_score": candidate.confidence}
        if candidate.candidate_kind == "factual_knowledge":
            return "knowledge_belief_event", {**base, "proposition_key": candidate.dedup_key, "proposition": candidate.summary, "confidence": candidate.confidence}
        if candidate.candidate_kind == "social_impression":
            return "social_cognition_event", {**base, "entity_id": source, "trust_baseline": candidate.confidence, "suspicion_baseline": 1.0 - candidate.confidence, "unresolved_tension": 0.0}
        return "higher_order_belief_event", {**base, "subject_actor_id": actor_id, "proposition_key": candidate.dedup_key, "meta_belief": candidate.summary, "confidence": candidate.confidence}

    def _apply_continuity_command(
        self, command: CharacterContinuityCommand
    ) -> CharacterContinuityReceipt:
        actor_id = command.actor_ref.removeprefix("character:")
        if not self.supports_continuity_actor(actor_id):
            return CharacterContinuityReceipt(
                receipt_ref=f"rejected:{command.command_id}",
                command_id=command.command_id,
                actor_ref=command.actor_ref,
                status="rejected",
                character_revision_before=0,
                character_revision_after=0,
                refusal_reason="unsupported_actor",
            )
        prior_payload = self._session_store.read_receipt(actor_id, kind='continuity', key=command.idempotency_key)
        prior = CharacterContinuityReceipt.model_validate(prior_payload) if prior_payload else None
        if prior is not None:
            event = self._session_store.read_committed_event_for_receipt(actor_id, kind='continuity', key=command.idempotency_key)
            if event is None:
                raise ValueError('character_continuity_commit_missing')
            commit = event['payload']['continuity_commit']
            digest = commit.get('command_digest')
            if digest is not None:
                matches = digest == self._cognition_digest(command.model_dump(mode='json', exclude={'expected_character_revision'}))
            else:
                # 旧事件没有 digest，只比较当时确实持久化的命令事实。
                delta = deepcopy(command.state_delta)
                projection = {k:v for k,v in event['payload'].items() if k != 'continuity_commit'}
                presentation = delta.pop('presentation_seed', None)
                hints = delta.pop('activation_hints', ())
                need = delta.pop('need_tension', None)
                dynamic = delta.pop('dynamic_state', None)
                matches = (command.command_id == prior.command_id
                    and command.to_tick == event['producer_ts'] and dict(command.source_revision_vector) == prior.source_revision_vector
                    and command.simulation_tick_cursor == prior.simulation_tick_cursor and command.source_owner_receipt_refs == prior.source_owner_receipt_refs
                    and command.policy_revision == 'policy:character-continuity:v1'
                    and projection.get('state_deltas') == delta and projection.get('memory_candidate_refs') == list(command.memory_candidate_refs)
                    and projection.get('supersedes') == (command.exposure_evidence.get('supersedes') or delta.get('supersedes'))
                    and projection.get('presentation_seed') == (presentation if isinstance(presentation,dict) else {})
                    and projection.get('activation_hints') == (list(hints) if isinstance(hints,(list,tuple)) else list(command.exposure_evidence.get('activation_hints',[])))
                    and commit.get('need_tension_delta',{}) == (need or {}) and commit.get('dynamic_state_delta',{}) == (dynamic or {})
                    and commit.get('memory_candidates',[]) == command.exposure_evidence.get('memory_candidates',[]))
            if not matches:
                raise ValueError('character_continuity_command_conflict')
            self._finish_session_projections(actor_id)
            self._persist_graph_continuity(actor_id=actor_id, producer_ts=prior.recorded_at)
            return prior.model_copy(update={'status':'idempotent_replay'}, deep=True)
        current_revision = self._continuity_revisions.get(actor_id, 0)
        if command.expected_character_revision != current_revision:
            return CharacterContinuityReceipt(
                receipt_ref=f"requeued:{command.command_id}",
                command_id=command.command_id,
                actor_ref=command.actor_ref,
                status="requeued",
                character_revision_before=current_revision,
                character_revision_after=current_revision,
                refusal_reason="character_revision_conflict",
            )
        if command.policy_revision != "policy:character-continuity:v1":
            return self._continuity_refusal(command, current_revision, "schema_revision_unsupported")
        if not command.source_revision_vector or any(int(v) < 0 for v in command.source_revision_vector.values()):
            return self._continuity_refusal(command, current_revision, "source_revision_vector_invalid")
        if any(not str(ref).strip() for ref in command.source_owner_receipt_refs):
            return self._continuity_refusal(command, current_revision, "owner_receipt_invalid")
        evidence = command.exposure_evidence
        basis = evidence.get("exposure_basis")
        if basis is not None and not isinstance(basis, str):
            return self._continuity_refusal(command, current_revision, "exposure_evidence_invalid")
        if evidence.get("visibility_scope", "actor:self") != "actor:self":
            return self._continuity_refusal(command, current_revision, "visibility_denied")
        if evidence.get("privacy_disposition", "actor_private") != "actor_private":
            return self._continuity_refusal(command, current_revision, "privacy_denied")
        if not command.source_owner_receipt_refs and command.state_delta.get("world_effect"):
            return CharacterContinuityReceipt(
                receipt_ref=f"rejected:{command.command_id}",
                command_id=command.command_id,
                actor_ref=command.actor_ref,
                status="rejected",
                character_revision_before=current_revision,
                character_revision_after=current_revision,
                refusal_reason="owner_settlement_required",
            )
        state_delta = deepcopy(command.state_delta)
        presentation_seed = state_delta.pop("presentation_seed", None)
        activation_hints = state_delta.pop("activation_hints", ())
        supersedes = state_delta.get("supersedes")
        need_delta = state_delta.pop("need_tension", None)
        dynamic_delta = state_delta.pop("dynamic_state", None)
        candidates = command.exposure_evidence.get("memory_candidates", [])
        if not isinstance(candidates, list):
            return self._continuity_refusal(command, current_revision, "memory_candidates_invalid")
        if set(command.memory_candidate_refs) != {
            str(item.get("candidate_id", "")) for item in candidates if isinstance(item, dict)
        }:
            return self._continuity_refusal(command, current_revision, "memory_candidate_refs_mismatch")
        staged_candidates: list[CharacterMemoryCandidate] = []
        for raw in candidates:
            if not isinstance(raw, dict):
                return self._continuity_refusal(command, current_revision, "memory_candidate_invalid")
            try:
                candidate = CharacterMemoryCandidate.model_validate(raw)
            except Exception:
                return self._continuity_refusal(command, current_revision, "memory_candidate_schema_invalid")
            if candidate.actor_ref != command.actor_ref or candidate.visibility_scope != "actor:self" or candidate.privacy_disposition != "actor_private":
                return self._continuity_refusal(command, current_revision, "memory_candidate_scope_denied")
            if candidate.event_valid_at > candidate.knowledge_available_at:
                return self._continuity_refusal(command, current_revision, "memory_candidate_temporal_invalid")
            if basis is not None and candidate.exposure_basis != basis:
                return self._continuity_refusal(command, current_revision, "exposure_basis_mismatch")
            if self._session_store.has_other_candidate(actor_id, candidate.candidate_id, candidate.dedup_key):
                return self._continuity_refusal(command, current_revision, "memory_candidate_duplicate")
            staged_candidates.append(candidate)
        try:
            if isinstance(need_delta, dict):
                staged_need = {**self._need_tension_store.read(actor_id), **deepcopy(need_delta), "actor_id": actor_id}
                NeedTensionState(**staged_need)
            if isinstance(dynamic_delta, dict):
                probe = CharacterDynamicStateStore()
                probe.write(actor_id, self._dynamic_state_store.read_record(actor_id).model_dump())
                probe.merge_delta(actor_id, deepcopy(dynamic_delta))
        except Exception:
            return self._continuity_refusal(command, current_revision, "state_delta_invalid")
        try:
            staged_modules = self._stage_shared_module_deltas(
                actor_id,
                command.module_deltas,
            )
        except ValueError as exc:
            return self._continuity_refusal(
                command,
                current_revision,
                str(exc) or "module_delta_invalid",
            )
        projection = {
            "actor_ref": command.actor_ref,
            "state_deltas": deepcopy(state_delta),
            "module_deltas": [
                delta.model_dump(mode="json") for delta in command.module_deltas
            ],
            "shared_modules": deepcopy(staged_modules),
            "presentation_seed": deepcopy(presentation_seed) if isinstance(presentation_seed, dict) else {},
            "activation_hints": list(activation_hints) if isinstance(activation_hints, (list, tuple)) else list(command.exposure_evidence.get("activation_hints", [])),
            "memory_candidate_refs": list(command.memory_candidate_refs),
            "supersedes": command.exposure_evidence.get("supersedes") or supersedes,
        }
        simulation_tick_cursor = command.simulation_tick_cursor
        receipt = CharacterContinuityReceipt(
            receipt_ref=f"continuity:{command.command_id}",
            command_id=command.command_id,
            actor_ref=command.actor_ref,
            status="committed",
            character_revision_before=current_revision,
            character_revision_after=current_revision + 1,
            seed_delta_refs=(f"seed-delta:{command.command_id}",),
            materialization_status="pending",
            simulation_tick_cursor=simulation_tick_cursor,
            source_revision_vector=dict(command.source_revision_vector),
            cursor_vector={
                "state_cursor": simulation_tick_cursor,
                "experience_cursor": simulation_tick_cursor,
                "memory_cursor": 0,
            },
            source_owner_receipt_refs=command.source_owner_receipt_refs,
            recorded_at=command.to_tick,
        )
        event = self._append_session_event(
            actor_id=actor_id,
            event_type="character_simulation_seed_event",
            producer_ts=command.to_tick,
            payload={
                **projection,
                "continuity_commit": {
                    "idempotency_key": command.idempotency_key,
                    "command_digest": self._cognition_digest(command.model_dump(mode='json', exclude={'expected_character_revision'})),
                    "receipt": receipt.model_dump(mode="json"),
                    "need_tension_delta": deepcopy(need_delta) if isinstance(need_delta, dict) else {},
                    "dynamic_state_delta": deepcopy(dynamic_delta) if isinstance(dynamic_delta, dict) else {},
                    "memory_candidates": [
                        candidate.model_dump(mode="json") for candidate in staged_candidates
                    ],
                },
            },
        )
        self._continuity_revisions[actor_id] = current_revision + 1
        self._persist_graph_continuity(actor_id=actor_id, producer_ts=receipt.recorded_at)
        return receipt

    def _stage_shared_module_deltas(
        self,
        actor_id: str,
        module_deltas,
    ) -> dict[str, dict[str, object]]:
        staged = deepcopy(self._shared_module_states.get(actor_id, {}))
        for delta in module_deltas:
            if self._state_group_registry is not None:
                try:
                    self._state_group_registry.validate_module_payload(
                        delta.group_id,
                        delta.definition_version,
                        delta.projection_schema_version,
                        delta.payload,
                    )
                except StateGroupRegistryError as exc:
                    reason = {
                        "state_group_definition_unknown": "module_definition_unknown",
                        "state_group_definition_version_unknown": "module_definition_unknown",
                        "state_group_projection_schema_mismatch": "module_schema_version_conflict",
                        "state_group_field_unknown": "module_field_unknown",
                    }.get(str(exc), "module_definition_invalid")
                    raise ValueError(reason) from exc
            previous = staged.get(delta.group_id)
            current_revision = int(previous.get("revision", 0)) if previous else 0
            if delta.expected_group_revision != current_revision:
                raise ValueError("module_revision_conflict")
            if previous and (
                previous.get("definition_version") != delta.definition_version
                or previous.get("projection_schema_version")
                != delta.projection_schema_version
            ):
                raise ValueError("module_definition_conflict")
            previous_payload = previous.get("payload", {}) if previous else {}
            if not isinstance(previous_payload, dict):
                raise ValueError("module_state_invalid")
            staged[delta.group_id] = {
                "definition_version": delta.definition_version,
                "projection_schema_version": delta.projection_schema_version,
                "revision": current_revision + 1,
                "payload": {**deepcopy(previous_payload), **deepcopy(delta.payload)},
                "source_ref": delta.source_ref,
            }
        return staged

    def _remember_materialization_receipt(self, key: str, receipt: CharacterMemoryMaterializationReceipt) -> None:
        self._session_store.save_receipt(receipt.actor_ref.removeprefix('character:'), kind='materialization', key=key, receipt=receipt.model_dump(mode='json'))

    def _continuity_refusal(self, command: CharacterContinuityCommand, revision: int, reason: str) -> CharacterContinuityReceipt:
        return CharacterContinuityReceipt(
            receipt_ref=f"rejected:{command.command_id}", command_id=command.command_id,
            actor_ref=command.actor_ref, status="rejected",
            character_revision_before=revision, character_revision_after=revision,
            refusal_reason=reason,
        )

    def apply_mind_delta_ledger(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        ledger: MindDeltaLedger | dict[str, object],
    ) -> None:
        if not self.supports_actor(actor_id):
            raise ValueError(f"unsupported actor_id: {actor_id}")
        typed_ledger = ledger if isinstance(ledger, MindDeltaLedger) else MindDeltaLedger(**ledger)
        if typed_ledger.actor_id != actor_id:
            raise ValueError("ledger actor_id mismatch")
        self._mind_writeback_policy.apply(
            runtime=self,
            actor_id=actor_id,
            producer_ts=producer_ts,
            ledger=typed_ledger,
        )

    def get_memory_bundle(self, actor_id: str) -> dict[str, list[dict[str, object]]]:
        return self._memory_store.retrieval_bundle(actor_id)

    def get_memory_record_bundle(
        self,
        actor_id: str,
        *,
        story_branch_id: str | None = None,
        valid_at: int | None = None,
    ) -> CharacterMemoryRecordBundle:
        bundle = self._memory_store.retrieval_record_bundle(
            actor_id,
            story_branch_id=story_branch_id,
            valid_at=valid_at,
        )
        snapshot = self._l1.get_snapshot(actor_id)
        if valid_at is None and story_branch_id is None and snapshot is not None and self.supports_actor(actor_id):
            capability = self._effective_profile_payload(actor_id).get("capability_constraint_layer", {})
            if isinstance(capability, dict) and capability.get("memory_retention") == "strong":
                focused = self.get_target_memory_record_bundle(actor_id, set(snapshot.current_attention_targets or snapshot.attention_targets))
                for field in type(bundle).model_fields:
                    records = {record.memory_id: record for record in getattr(bundle, field)}
                    records.update({record.memory_id: record for record in getattr(focused, field)})
                    setattr(bundle, field, list(records.values()))
        return bundle

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

    def build_shadow_mind_frame(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        trigger_event: dict[str, object] | None = None,
    ) -> dict[str, object]:
        snapshot = self._l1.get_snapshot(actor_id)
        snapshot_payload = snapshot.model_dump() if snapshot is not None else {}
        if snapshot is not None:
            focus_target = self._snapshot_focus_target(snapshot)
            if focus_target:
                snapshot_payload.setdefault("current_focus_target", focus_target)
        effective_profile = self._effective_profile_payload(actor_id)
        frame = self._mind_frame_builder.build_frame(
            actor_id=actor_id,
            producer_ts=producer_ts,
            trigger_event=trigger_event or {},
            snapshot=snapshot_payload,
            effective_profile=effective_profile,
            memory_bundle=self.get_memory_bundle(actor_id),
            need_tension_state=self.get_need_tension_state(actor_id),
            dynamic_state=self.get_dynamic_state(actor_id),
            current_goal_state=self.get_goal_state(actor_id),
            goal_state_history=self.get_goal_state_history(actor_id),
            unresolved_tensions=self.get_unresolved_tensions(actor_id),
            supervision_state=self.get_supervision_state(actor_id),
            skill_affordance_summary=self._skill_affordance_summary_payload(
                actor_id=actor_id,
                effective_profile=effective_profile,
            ),
        )
        return frame.model_dump()

    def _skill_affordance_summary_payload(
        self,
        *,
        actor_id: str,
        effective_profile: dict[str, object],
    ) -> dict[str, object]:
        cached = self._last_skill_affordance_summaries.get(actor_id)
        if cached is not None:
            return dict(cached)
        return self._build_skill_affordance_summary(
            actor_id=actor_id,
            effective_profile=effective_profile,
        )

    def _build_skill_affordance_summary(
        self,
        *,
        actor_id: str,
        effective_profile: dict[str, object],
    ) -> dict[str, object]:
        skill_states = self._skill_service.initial_skill_states(
            actor_id=actor_id,
            profile=effective_profile,
        )
        return self._skill_service.build_affordance_summary(
            actor_id=actor_id,
            skill_states=skill_states,
        ).model_dump()

    def _background_entry_reason(self, actor_id, producer_ts, supervision, snapshot):
        if not self.supports_actor(actor_id):
            return 'unsupported_actor'
        if not self._background_cognition_enabled:
            return 'background_disabled'
        if self.get_background_mode(actor_id) == 'off':
            return 'actor_background_off'
        if not supervision.active_constraints.allow_background_loop:
            return 'supervision_blocked_background_loop'
        interval = int(supervision.active_constraints.min_tick_interval_ms or 0)
        previous = self._last_background_tick_ms.get(actor_id)
        if interval > 0 and previous is not None and producer_ts - previous < interval:
            return 'tick_not_due'
        return 'missing_snapshot' if snapshot is None else ''

    def _plan_background_entry(self, actor_id, producer_ts):
        if not self.supports_actor(actor_id):
            return dict(supported=False, events=[], normalized_payload={}, after=None,
                result=CharacterBackgroundCognitionResult(actor_id=actor_id, producer_ts=producer_ts, ran=False, reason='unsupported_actor').model_dump(mode='json'))
        supervision = self._supervision_states.get(actor_id) or self._default_supervision_state(actor_id)
        snapshot = self.get_private_snapshot(actor_id)
        reason = self._background_entry_reason(actor_id, producer_ts, supervision, snapshot)
        result = CharacterBackgroundCognitionResult(actor_id=actor_id, producer_ts=producer_ts,
            ran=False, reason=reason, current_level=supervision.current_level).model_dump(mode='json') if reason else None
        return dict(supported=True, events=[], normalized_payload={}, result=result,
            after=None if snapshot is None else dict(private_snapshot=snapshot.model_dump(mode='json'),
                supervision_state=supervision.model_dump(mode='json'), wake_up=deepcopy(self._wake_up_signals.get(actor_id))))

    def _run_background_cognition_tick_steps(
        self,
        *,
        actor_id: str,
        producer_ts: int,
    ) -> Generator[CognitionRequest, dict[str, object], CharacterBackgroundCognitionResult]:
        if self.supports_actor(actor_id):
            self._supervision_state_for(actor_id)
        planned = self._plan_background_entry(actor_id, producer_ts)
        if planned['result'] is not None:
            return CharacterBackgroundCognitionResult.model_validate(planned['result'])
        supervision_state = self._supervision_state_for(actor_id)
        background_mode = self.get_background_mode(actor_id)
        snapshot = self.get_private_snapshot(actor_id)
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
        interpretation = yield from self._interpret_with_continuity_floor(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            control_mode=self.get_control_mode(actor_id),
            source_stage="background_cognition_tick",
            run_model=lambda memory_override=None: self._l2.prepare_background_state(
                snapshot,
                background_payload,
                memory_bundle=memory_override if memory_override is not None else memory_record_bundle,
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
        decision = yield from self._select_intent_with_continuity_floor(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=snapshot,
            interpretation=interpretation,
            control_mode=self.get_control_mode(actor_id),
            source_stage="background_cognition_tick",
            run_model=lambda memory_override=None: self._l3.prepare_intent_plan(
                interpretation=interpretation,
                snapshot=snapshot.model_dump(),
                profile=self._profile_payload(actor_id),
                memory_bundle=memory_override if memory_override is not None else memory_record_bundle,
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

    def _record_character_perceived_event(self, event: CharacterPerceivedEvent, *,
        verification_result: ActivePerceptionResult | None = None, verification_conflict_refs: list[str] | None = None,
    ) -> None:
        event = CharacterPerceivedEvent.model_validate(event.model_dump())
        stored = self._append_session_event(
            actor_id=event.actor_id,
            event_type="character_perceived_event",
            producer_ts=event.producer_ts,
            payload={
                "percept_channel": event.percept_channel,
                "room_id": event.room_id, "scene_id": event.scene_id, "zone_id": event.zone_id,
                **({"verification_request_ref": verification_result.request_id,
                    "verification_result": verification_result.model_dump(),
                    "verification_conflict_refs": verification_conflict_refs or []} if verification_result else {}),
                "summary": event.perceived_summary,
                "tags": [event.percept_channel],
                "source_candidate_event_id": event.source_candidate_event_id,
                "source_actor_id": event.source_actor_id,
                "target_actor_id": event.target_actor_id,
                "target_object_id": event.target_object_id,
                "target_environment_id": event.target_environment_id,
                "target_ref": event.target_ref,
                "world_anchor_id": event.world_anchor_id,
                "capture_id": event.capture_id,
                "capture_root_id": event.capture_root_id,
                "source_ref_lineage": list(event.source_ref_lineage),
                "clarity_score": event.clarity_score,
                "certainty_score": event.certainty_score,
                **({"fact_claim": event.fact_claim.model_dump()} if event.fact_claim is not None else {}),
            },
        )
        if verification_result is not None:
            self._persist_graph_continuity(actor_id=event.actor_id, producer_ts=event.producer_ts)
        self._project_session_event(stored)
        self._update_memory_scene_knowledge(stored)

    def _update_memory_scene_knowledge(self, event: dict[str, object]) -> None:
        actor_id, index = str(event['actor_id']), int(event['event_index'])
        with self._session_store.transaction():
            if self._session_store.projection_cursor(actor_id, 'ask') >= index:
                return
            self._update_memory_scene_knowledge_unchecked(event)
            self._session_store.set_projection_cursor(actor_id, 'ask', index)

    def _update_memory_scene_knowledge_unchecked(self, event: dict[str, object]) -> None:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            return
        if event.get("event_type") == "character_agent_settlement_result":
            target = str(payload.get("target_object_id", "") or payload.get("target_actor_id", "") or "")
            if target and payload.get("result_type") == "constraint_state_result":
                self._l1.get_actor_scene_knowledge_store().record(ActorSceneKnowledgeEntry(
                    entry_id=f"ask:{event['actor_id']}:{target}:failure", actor_id=str(event["actor_id"]),
                    session_id=str(payload.get("room_id", "room_demo")), scene_id=str(payload.get("scene_id", "scene_demo")),
                    subject_ref=target, knowledge_type="space", summary=str(payload.get("constraint_summary", "interaction failed")),
                    source_kind="interaction_failure", source_refs=[str(event["event_id"])], confidence=1.0,
                ), producer_ts=int(event["producer_ts"]))
            return
        if payload.get("verification_result"):
            result = ActivePerceptionResult.model_validate(payload["verification_result"])
            result.conflict_refs = list(payload.get("verification_conflict_refs", result.conflict_refs))
            ActivePerceptionPlanner().apply_result(self._l1.get_actor_scene_knowledge_store(), result,
                producer_ts=int(event["producer_ts"]))
            return
        claim_payload = payload.get("fact_claim") if isinstance(payload, dict) else None
        if not isinstance(claim_payload, dict):
            return
        claim = MemoryFactClaim.model_validate(claim_payload)
        self._l1.get_actor_scene_knowledge_store().record(ActorSceneKnowledgeEntry(
            entry_id=f"ask:{event['actor_id']}:{claim.subject_ref}:memory",
            actor_id=str(event["actor_id"]), session_id=str(payload.get("room_id", "room_demo")),
            scene_id=str(payload.get("scene_id", "scene_demo")), subject_ref=claim.subject_ref,
            knowledge_type="space", summary=str(payload.get("summary", "")), source_kind="canonical_percept_bundle",
            source_refs=[str(event["event_id"]), claim.source_ref], confidence=float(payload.get("certainty_score", 1.0)), claim=claim,
        ), producer_ts=int(event["producer_ts"]))

    def _record_relational_belief_from_perceived_event(self, event: CharacterPerceivedEvent) -> None:
        entity_id = str(event.source_actor_id or "")
        if entity_id == "" or entity_id == event.actor_id:
            return
        value = self._infer_relational_belief_value(event)
        stored = self._append_session_event(
            actor_id=event.actor_id,
            event_type="relational_belief_event",
            producer_ts=event.producer_ts,
            payload={
                "entity_id": entity_id,
                "belief_type": "trust_level",
                "value": value,
            },
        )
        self._project_session_event(stored)

    def _infer_relational_belief_value(self, event: CharacterPerceivedEvent) -> str:
        if event.certainty_score < 0.75 or event.clarity_score < 0.85:
            return "guarded"
        return "noticed"

    def _record_self_body_event(self, event: SelfBodyPerceivedEvent) -> None:
        stored = self._append_session_event(
            actor_id=event.actor_id,
            event_type="self_body_perceived_event",
            producer_ts=event.producer_ts,
            payload={
                "body_state_class": event.body_state_class,
                "summary": event.perceived_summary,
                "source_body_result_id": event.source_body_result_id,
            },
        )
        self._project_session_event(stored)

    def _record_siming_event(self, payload: dict[str, object]) -> None:
        actor_id = str(payload.get("target_actor_id", "") or "")
        if actor_id == "":
            return
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="siming_output_event",
            producer_ts=int(payload.get("producer_ts", 0) or 0),
            payload=self._siming_event_payload(payload),
        )
        self._project_session_event(stored)

    @staticmethod
    def _siming_event_payload(payload: dict[str, object]) -> dict[str, object]:
        return {
            "summary": str(payload.get("presentation_hint", "") or ""),
            "pressure_hint": str(payload.get("pressure_hint", "") or ""),
            "salience_boost": payload.get("salience_boost"),
            "reason_scope": str(payload.get("reason_scope", "") or ""),
            "target_object_id": str(payload.get("target_object_id", "") or ""),
            "target_environment_id": str(payload.get("target_environment_id", "") or ""),
        }

    def _plan_execution_request_state(self, actor_id, producer_ts, payload):
        request = self._primary_requested_action(payload)
        request_type = str(request.get('request_type', '') or '')
        target_actor_id = str(request.get('target_actor_id', '') or '')
        ticks = dict(self._last_social_request_tick_ms)
        deferred = self._defer_social_request(ticks, actor_id, request_type, target_actor_id, producer_ts)
        continuity = deepcopy(self._continuity_state.get(actor_id, RuntimeContinuityState(actor_id=actor_id)))
        if not deferred:
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
        return dict(deferred=deferred, continuity=continuity.model_dump(mode='json'),
            social_ticks=[[*key[1:], value] for key, value in sorted(ticks.items()) if key[0] == actor_id])

    def _install_execution_request_state(self, actor_id, state):
        if not state['deferred']:
            self._continuity_state[actor_id] = RuntimeContinuityState.model_validate(state['continuity'])
        self._last_social_request_tick_ms = {key: value for key, value in self._last_social_request_tick_ms.items() if key[0] != actor_id}
        self._last_social_request_tick_ms.update({(actor_id, kind, target): tick for kind, target, tick in state['social_ticks']})

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
        state = self._plan_execution_request_state(actor_id, producer_ts, payload)
        self._install_execution_request_state(actor_id, state)
        if state['deferred']:
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
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="character_agent_execution_request",
            producer_ts=producer_ts,
            payload=payload,
        )
        self._project_session_event(stored)
        self._queue_observatory_snapshot(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=self._get_snapshot_for_observatory(actor_id, producer_ts),
        )
        self._persist_graph_continuity(actor_id=actor_id, producer_ts=producer_ts)

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
        stored_payload = deepcopy(payload)
        stored_payload["action_settlement_result"] = self._action_settlement_result_metadata(stored_payload)
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="character_agent_settlement_result",
            producer_ts=producer_ts,
            payload=stored_payload,
        )
        self._project_session_event(stored)
        target = str(payload.get("target_object_id", "") or payload.get("target_actor_id", "") or "")
        self._update_memory_scene_knowledge(stored)
        if (payload.get("result_type") == "action_resolution_result" and payload.get("resolution_status") == "accepted"
            and payload.get("actor_id") == actor_id and target and payload.get("read_content") and payload.get("read_source_ref")):
            source = str(payload["read_source_ref"])
            self._record_character_perceived_event(CharacterPerceivedEvent(
                actor_id=actor_id, percept_channel="record", producer_ts=producer_ts,
                room_id=str(payload.get("room_id", "room_demo")), scene_id=str(payload.get("scene_id", "scene_demo")),
                zone_id=str(payload.get("zone_id", "zone_focus")), target_object_id=target,
                perceived_summary=f"record {target}: {payload['read_content']}",
                source_candidate_event_id=str(payload["result_id"]), source_ref_lineage=[source, str(payload["result_id"])],
                fact_claim=MemoryFactClaim(scope_ref=f"record:{payload.get('room_id', 'room_demo')}", subject_ref=target,
                    predicate="record_content", value=str(payload["read_content"]), valid_at=producer_ts, source_ref=source),
            ))
        behavior_timeline = self._session_store.read_events_page(
            actor_id,
            through_index=int(stored["event_index"]),
            event_types=(
                "l2_reasoning_request",
                "character_interpretation_event",
                "goal_state_event",
                "character_agent_execution_request",
            ),
            limit=max(1, int(stored["event_index"])),
        )
        evaluation = self._record_behavior_evaluation(
            actor_id=actor_id,
            producer_ts=producer_ts,
            settlement_event=stored,
            timeline=behavior_timeline,
        )
        if self._behavior_turn_projection is not None:
            self._behavior_turn_projection.record(
                actor_id=actor_id,
                producer_ts=producer_ts,
                settlement_event=stored,
                evaluation=evaluation,
                timeline=behavior_timeline,
            )
        outcome_summary = str(stored_payload.get("constraint_summary", "") or stored_payload.get("change_summary", "") or stored_payload.get("stable_state_summary", "") or stored_payload.get("result_type", "") or "")
        self._set_observatory_context(actor_id, "latest_outcome_summary", outcome_summary)
        self._queue_observatory_stage_event(
            actor_id=actor_id,
            producer_ts=producer_ts,
            stage="settlement_result",
            summary=outcome_summary,
            focus_target=self._snapshot_focus_target(self._get_snapshot_for_observatory(actor_id, producer_ts)),
            intent_label=str(stored_payload.get("result_type", "") or ""),
            participants=self._participants_for_actor(actor_id, str(stored_payload.get("target_actor_id", "") or str(stored_payload.get("target_object_id", "") or str(stored_payload.get("target_environment_id", "") or "")))),
            detail=dict(stored_payload),
        )
        self._queue_observatory_snapshot(
            actor_id=actor_id,
            producer_ts=producer_ts,
            snapshot=self._get_snapshot_for_observatory(actor_id, producer_ts),
        )
        self._persist_graph_continuity(actor_id=actor_id, producer_ts=producer_ts)

    def _record_behavior_evaluation(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        settlement_event: dict[str, object],
        timeline: list[dict[str, object]],
    ) -> dict[str, object]:
        evaluation = self._behavior_evaluation.evaluate(
            actor_id=actor_id,
            settlement_event=settlement_event,
            timeline=timeline,
        )
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="character_behavior_evaluation_event",
            producer_ts=producer_ts,
            payload=evaluation,
        )
        self._project_session_event(stored)
        candidate = evaluation.get("candidate_policy")
        if isinstance(candidate, dict):
            candidate_event = self._append_session_event(
                actor_id=actor_id,
                event_type="character_policy_candidate_event",
                producer_ts=producer_ts,
                payload=candidate,
            )
            self._project_session_event(candidate_event)
            evaluation["policy_candidate_event_id"] = str(
                candidate_event.get("event_id", "")
            )
        return evaluation

    def _action_settlement_result_metadata(self, payload: dict[str, object]) -> dict[str, object]:
        advisory_metadata = self._settlement_advisory_metadata(payload)
        outcome_band = self._settlement_outcome_band(payload)
        failure_domains = self._settlement_failure_domains(
            payload=payload,
            advisory_metadata=advisory_metadata,
            outcome_band=outcome_band,
        )
        skill_path_id = self._settlement_skill_path_id(advisory_metadata)
        missing_requirements = self._settlement_missing_requirements(advisory_metadata)
        change_summary = str(payload.get("change_summary", "") or "")
        stable_state_summary = str(payload.get("stable_state_summary", "") or "")
        constraint_summary = str(payload.get("constraint_summary", "") or "")
        result_type = str(payload.get("result_type", "") or "")
        skill_contributions = self._settlement_skill_contributions(advisory_metadata)
        realization_hints = self._settlement_realization_hints(advisory_metadata)
        risk_tags = self._settlement_risk_tags(advisory_metadata)
        semantic_effects = [stable_state_summary] if stable_state_summary != "" else []
        if result_type == "constraint_state_result" and constraint_summary != "":
            semantic_effects.append(constraint_summary)
        physical_effects = (
            [change_summary]
            if result_type in {"object_state_result", "body_state_result", "environment_state_result"} and change_summary != ""
            else []
        )
        costs = [change_summary] if result_type == "body_state_result" and change_summary != "" else []
        settlement_result = ActionSettlementResult(
            outcome_band=outcome_band,
            failure_domains=failure_domains,
            primary_failure_domain=failure_domains[0] if failure_domains else "none",
            semantic_effects=semantic_effects,
            physical_effects=physical_effects,
            social_effects=[],
            costs=costs,
            realization_hints=realization_hints,
            skill_path_id=skill_path_id,
            skill_contributions=skill_contributions,
            risk_tags=risk_tags,
            missing_requirements=missing_requirements,
        )
        return settlement_result.model_dump()

    def _settlement_advisory_metadata(self, payload: dict[str, object]) -> dict[str, object]:
        advisory_payload = payload.get("advisory_metadata")
        advisory_metadata = deepcopy(advisory_payload) if isinstance(advisory_payload, dict) else {}
        for key in ("skill_evaluation_result", "primitive_action_plan"):
            value = payload.get(key)
            if isinstance(value, dict) and key not in advisory_metadata:
                advisory_metadata[key] = deepcopy(value)
        return advisory_metadata

    def _settlement_outcome_band(self, payload: dict[str, object]) -> str:
        settlement_status = str(payload.get("settlement_status", "") or payload.get("resolution_status", "") or "")
        result_type = str(payload.get("result_type", "") or "")
        if settlement_status in {"accepted", "applied", "observed"}:
            if result_type == "body_state_result":
                return "success_with_cost"
            return "clean_success"
        if settlement_status in {"rejected", "blocked", "denied"}:
            if result_type == "constraint_state_result":
                return "blocked"
            return "failed"
        return "partial"

    def _settlement_failure_domains(
        self,
        *,
        payload: dict[str, object],
        advisory_metadata: dict[str, object],
        outcome_band: str,
    ) -> list[str]:
        failure_domains: list[str] = []
        result_type = str(payload.get("result_type", "") or "")
        if outcome_band in {"blocked", "failed", "misfire", "partial"}:
            if result_type == "constraint_state_result":
                failure_domains.append("world_constraint")
            elif result_type in {"object_state_result", "body_state_result", "environment_state_result"}:
                failure_domains.append("physical_failure")
            missing_requirements = self._settlement_missing_requirements(advisory_metadata)
            if missing_requirements:
                failure_domains.append("missing_requirement")
            elif self._settlement_has_blocked_skill_path(advisory_metadata):
                failure_domains.append("skill_failure")
        return list(dict.fromkeys(failure_domains))

    def _settlement_skill_path_id(self, advisory_metadata: dict[str, object]) -> str:
        skill_evaluation = advisory_metadata.get("skill_evaluation_result")
        if not isinstance(skill_evaluation, dict):
            return ""
        selected_path = skill_evaluation.get("selected_path")
        if not isinstance(selected_path, dict):
            return ""
        return str(selected_path.get("binding_id", "") or "")

    def _settlement_skill_contributions(self, advisory_metadata: dict[str, object]) -> list[str]:
        primitive_action_plan = advisory_metadata.get("primitive_action_plan")
        if isinstance(primitive_action_plan, dict):
            contributions = primitive_action_plan.get("primitive_actions")
            if isinstance(contributions, list):
                return [str(entry) for entry in contributions if str(entry or "") != ""]
        skill_evaluation = advisory_metadata.get("skill_evaluation_result")
        if not isinstance(skill_evaluation, dict):
            return []
        selected_path = skill_evaluation.get("selected_path")
        if not isinstance(selected_path, dict):
            return []
        contributions = selected_path.get("skill_path_tags")
        if not isinstance(contributions, list):
            return []
        return [str(entry) for entry in contributions if str(entry or "") != ""]

    def _settlement_realization_hints(self, advisory_metadata: dict[str, object]) -> list[str]:
        primitive_action_plan = advisory_metadata.get("primitive_action_plan")
        if not isinstance(primitive_action_plan, dict):
            return []
        hints = primitive_action_plan.get("realization_keys")
        if not isinstance(hints, list):
            return []
        return [str(entry) for entry in hints if str(entry or "") != ""]

    def _settlement_risk_tags(self, advisory_metadata: dict[str, object]) -> list[str]:
        skill_evaluation = advisory_metadata.get("skill_evaluation_result")
        if not isinstance(skill_evaluation, dict):
            return []
        selected_path = skill_evaluation.get("selected_path")
        if not isinstance(selected_path, dict):
            return []
        risk_tags = selected_path.get("risk_tags")
        if not isinstance(risk_tags, list):
            return []
        return [str(entry) for entry in risk_tags if str(entry or "") != ""]

    def _settlement_missing_requirements(self, advisory_metadata: dict[str, object]) -> list[str]:
        skill_evaluation = advisory_metadata.get("skill_evaluation_result")
        if not isinstance(skill_evaluation, dict):
            return []
        blocked_paths = skill_evaluation.get("blocked_paths")
        if not isinstance(blocked_paths, list):
            return []
        missing_requirements: list[str] = []
        for blocked_path in blocked_paths:
            if not isinstance(blocked_path, dict):
                continue
            entries = blocked_path.get("missing_requirements")
            if not isinstance(entries, list):
                continue
            for entry in entries:
                requirement = str(entry or "")
                if requirement != "":
                    missing_requirements.append(requirement)
        return list(dict.fromkeys(missing_requirements))

    def _settlement_has_blocked_skill_path(self, advisory_metadata: dict[str, object]) -> bool:
        skill_evaluation = advisory_metadata.get("skill_evaluation_result")
        if not isinstance(skill_evaluation, dict):
            return False
        blocked_paths = skill_evaluation.get("blocked_paths")
        if not isinstance(blocked_paths, list) or not blocked_paths:
            return False
        return self._settlement_skill_path_id(advisory_metadata) == ""

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
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="character_agent_dialogue_response",
            producer_ts=producer_ts,
            payload=payload,
        )
        self._project_session_event(stored)
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
        )

    def _record_reasoning_request(
        self,
        actor_id: str,
        producer_ts: int,
        request: dict[str, object],
    ) -> None:
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="l2_reasoning_request",
            producer_ts=producer_ts,
            payload=request,
        )
        self._project_session_event(stored)

    def _record_interpretation_event(
        self,
        actor_id: str,
        producer_ts: int,
        interpretation: CharacterInterpretation,
    ) -> None:
        stored = self._append_session_event(actor_id=actor_id,
            **self._plan_interpretation_event(producer_ts, interpretation))
        self._project_session_event(stored)

    @staticmethod
    def _plan_interpretation_event(producer_ts: int, interpretation: CharacterInterpretation) -> dict:
        return dict(event_type='character_interpretation_event', producer_ts=producer_ts,
            payload=interpretation.model_dump(mode='json'))

    def _plan_provider_failure(self, frame, stage, error):
        if os.getenv('CHARACTER_MODEL_REQUIRE_ONLINE', '').strip() == '1':
            raise error
        args = dict(actor_id=frame['actor_id'],
            snapshot=CharacterPrivateWorldSnapshot.model_validate(frame['entry_after']['private_snapshot']),
            control_mode=frame['context']['control_mode'], error=error)
        if stage == 'l2':
            result = self._continuity_floor_interpretation(**args)
        else:
            result = self._continuity_floor_decision(**args,
                interpretation=CharacterInterpretation.model_validate(frame['interpretation']))
        return result.model_dump(mode='json')

    def _plan_l2_effects(self, frame: dict, output: dict, *, fallback=None) -> tuple[list[dict], dict]:
        interpretation = (self._l2.map_reasoning_output(actor_id=frame['actor_id'], output=output)
            if fallback is None else CharacterInterpretation.model_validate(fallback))
        events = self._plan_cognition_update(actor_id=frame['actor_id'], producer_ts=frame['producer_ts'],
            interpretation=interpretation) if interpretation.cognition_status == 'model' else []
        events.append(self._plan_interpretation_event(frame['producer_ts'], interpretation))
        return events, interpretation.model_dump(mode='json')

    def _record_goal_state_event(
        self,
        actor_id: str,
        producer_ts: int,
        decision: CharacterIntentDecision,
    ) -> None:
        event_payload = self._plan_goal_state_event(actor_id, decision)
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="goal_state_event",
            producer_ts=producer_ts,
            payload=event_payload,
        )
        self._project_session_event(stored)
        self._record_shadow_skill_affordance_summary(
            actor_id=actor_id,
            producer_ts=producer_ts,
        )

    def _plan_goal_state_event(self, actor_id: str, decision: CharacterIntentDecision) -> dict[str, object]:
        """冻结目标转换；同步写入和持久阶段共用同一领域计算。"""
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
        return {
            **goal_state,
            "selected_intent": decision.selected_intent,
            "goal_changed": bool(changed_fields),
            "changed_fields": changed_fields,
            "transition_kind": transition_kind,
            "transition_reason_tags": transition_reason_tags,
        }

    def _record_shadow_skill_affordance_summary(
        self,
        *,
        actor_id: str,
        producer_ts: int,
    ) -> None:
        summary = self._build_skill_affordance_summary(
            actor_id=actor_id,
            effective_profile=self._effective_profile_payload(actor_id),
        )
        self._last_skill_affordance_summaries[actor_id] = summary
        snapshot = self._get_snapshot_for_observatory(actor_id, producer_ts)
        self._queue_observatory_stage_event(
            actor_id=actor_id,
            producer_ts=producer_ts,
            stage="skill_affordance_shadow",
            summary="skill affordance summary observed",
            focus_target=self._snapshot_focus_target(snapshot),
            intent_label="shadow_only",
            participants=self._participants_for_actor(actor_id, self._snapshot_focus_target(snapshot)),
            detail={"skill_affordance_summary": summary},
        )

    def _record_need_tension_state_event(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        need_tension_state: dict[str, object],
    ) -> None:
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="need_tension_state_event",
            producer_ts=producer_ts,
            payload=need_tension_state,
        )
        self._project_session_event(stored)

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
    ) -> Generator[CognitionRequest, dict[str, object], CharacterInterpretation]:
        try:
            request_json = self._run_with_memory_recall(actor_id, snapshot, run_model)
            output = yield CognitionRequest("l2_reasoning", request_json)
            return self._l2.map_reasoning_output(actor_id=actor_id, output=output)
        except Exception as exc:
            if os.getenv("CHARACTER_MODEL_REQUIRE_ONLINE", "").strip() == "1":
                raise
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
    ) -> Generator[CognitionRequest, dict[str, object], CharacterIntentDecision]:
        try:
            prepared = self._run_with_memory_recall(actor_id, snapshot, run_model)
            output = yield CognitionRequest("l3_planning", prepared.request_json,
                str(prepared.behavior_policy.get("candidate_id", "") or ""))
            plan = self._l3.finish_intent_plan(prepared, output)
            return self._l3.decision_from_plan(plan, interpretation=interpretation)
        except Exception as exc:
            if isinstance(exc, MissingRequiredMemoryEvidence):
                self._session_append_event(actor_id=actor_id, event_type="character_memory_recall_deferred",
                    producer_ts=producer_ts, payload={"missing_required_refs": exc.missing_required_refs})
                return self._continuity_floor_decision(actor_id=actor_id, snapshot=snapshot,
                    interpretation=interpretation, control_mode=control_mode, error=exc).model_copy(update={
                        "selected_intent": "stay_silent", "fallback_mode": "memory_evidence_pending",
                        "rationale": "关键已知证据仍未进入上下文，延后依赖该证据的决策。",
                    })
            if os.getenv("CHARACTER_MODEL_REQUIRE_ONLINE", "").strip() == "1":
                raise
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
        for event in self._plan_cognition_update(
                actor_id=actor_id, producer_ts=producer_ts, interpretation=interpretation):
            stored = self._append_session_event(actor_id=actor_id, **event)
            self._project_session_event(stored)

    def _plan_cognition_update(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        interpretation: CharacterInterpretation,
    ) -> list[dict[str, object]]:
        events = []
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
            # 模型摘要不能覆盖已经获得的结构化事实；新证据走感知/核验入口。
            if any(record.proposition_key == proposition_key and record.claim is not None
                   for record in self.get_memory_record_bundle(actor_id).knowledge_memories):
                continue
            events.append(dict(
                event_type="knowledge_belief_event",
                producer_ts=producer_ts,
                payload={
                    "proposition_key": proposition_key,
                    "proposition": proposition,
                    "state": state,
                    "confidence": confidence,
                    "event_index": index,
                },
            ))
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
            events.append(dict(
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
            ))
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
            events.append(dict(
                event_type="higher_order_belief_event",
                producer_ts=producer_ts,
                payload={
                    "subject_actor_id": subject_actor_id,
                    "proposition_key": proposition_key,
                    "meta_belief": meta_belief,
                    "confidence": confidence,
                    "event_index": index,
                },
            ))
        delta_payload = interpretation.dynamic_state_delta.as_mapping()
        if delta_payload:
            # 仅复制本 actor 的当前值，在局部 typed store 计算确定 after-state。
            state = CharacterDynamicStateStore()
            state.write(actor_id, self._dynamic_state_store.read_record(actor_id).storage_dump())
            state.merge_delta(actor_id, delta_payload)
            updated_state = state.read_record(actor_id).storage_dump()
            events.append(dict(
                event_type="dynamic_state_event",
                producer_ts=producer_ts,
                payload=updated_state,
            ))
        return events

    def _session_append_event(
        self,
        *,
        actor_id: str,
        event_type: str,
        producer_ts: int,
        payload: dict[str, object],
    ) -> None:
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type=event_type,
            producer_ts=producer_ts,
            payload=payload,
        )
        self._project_session_event(stored)

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
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="character_personality_drift_promotion_event",
            producer_ts=producer_ts,
            payload=candidate.model_dump(),
        )
        self._project_session_event(stored)

    def _build_execution_plan(self, actor_id, snapshot, interpretation, decision, *, causation_id='', correlation_id=''):
        plan = self._l4_executor.build_execution_plan(
            snapshot=snapshot,
            interpretation=interpretation,
            decision=decision,
        )
        frames = plan.get("actor_control_frames", [])
        if isinstance(frames, list):
            for frame in frames:
                if not isinstance(frame, dict):
                    continue
                if causation_id:
                    frame["causation_id"] = causation_id
                if correlation_id:
                    frame["correlation_id"] = correlation_id
        self._attach_skill_shadow_fields(actor_id=actor_id, plan=plan)
        self._attach_skill_behavior_guardrail(actor_id=actor_id, plan=plan)
        return plan

    def _plan_execution_effects(self, frame):
        actor_id, producer_ts = frame['actor_id'], frame['producer_ts']
        payload = frame['normalized_payload']
        plan = self._build_execution_plan(actor_id,
            CharacterPrivateWorldSnapshot.model_validate(frame['entry_after']['private_snapshot']),
            CharacterInterpretation.model_validate(frame['interpretation']),
            CharacterIntentDecision.model_validate(frame['decision']),
            causation_id=str(payload.get('causation_id', '') or ''),
            correlation_id=str(payload.get('correlation_id', '') or ''))
        state = self._plan_execution_request_state(actor_id, producer_ts, plan)
        commands = self.filter_commands_for_actor(actor_id, self._l4.build_commands_from_execution_plan(deepcopy(plan)))
        return dict(state, execution_plan=plan, commands=[command.model_dump(mode='json') for command in commands],
            events=[] if state['deferred'] else [dict(event_type='character_agent_execution_request',
                producer_ts=producer_ts, payload=plan)])

    def _record_execution_plan(
        self,
        actor_id: str,
        producer_ts: int,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
        *,
        causation_id: str = "",
        correlation_id: str = "",
    ) -> dict[str, object]:
        plan = self._build_execution_plan(actor_id, snapshot, interpretation, decision,
            causation_id=causation_id, correlation_id=correlation_id)
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
        )
        return plan

    def _attach_skill_shadow_fields(
        self,
        *,
        actor_id: str,
        plan: dict[str, object],
    ) -> None:
        shadow_payload = self._skill_evaluation_payload(actor_id=actor_id, plan=plan)
        plan["skill_evaluation_result"] = shadow_payload["skill_evaluation_result"]
        shadow_metadata = shadow_payload.get("skill_evaluation_shadow")
        if isinstance(shadow_metadata, dict):
            plan["skill_evaluation_shadow"] = shadow_metadata
        primitive_action_plan = shadow_payload.get("primitive_action_plan")
        if isinstance(primitive_action_plan, dict):
            plan["primitive_action_plan"] = primitive_action_plan
        else:
            plan.pop("primitive_action_plan", None)

    def _skill_evaluation_payload(
        self,
        *,
        actor_id: str,
        plan: dict[str, object],
    ) -> dict[str, object]:
        proposal = plan.get("composite_action_proposal", {})
        if not isinstance(proposal, dict):
            proposal = {}
        action_id = str(proposal.get("action_id", "") or "")
        preferred_strategy_tags = proposal.get("preferred_strategy_tags", [])
        profile = self._effective_profile_payload(actor_id)
        skill_states = self._skill_service.initial_skill_states(
            actor_id=actor_id,
            profile=profile,
        )
        evaluation_result = self._skill_service.evaluate_action(
            actor_id=actor_id,
            action_id=action_id,
            skill_states=skill_states,
            preferred_strategy_tags=preferred_strategy_tags if isinstance(preferred_strategy_tags, list) else [],
        )
        payload: dict[str, object] = {
            "skill_evaluation_result": evaluation_result.model_dump(),
            "skill_evaluation_shadow": {
                "advisory": True,
                "evaluation_mode": "shadow",
            },
        }
        selected_path = evaluation_result.selected_path
        if not isinstance(selected_path, dict):
            return payload
        binding_id = str(selected_path.get("binding_id", "") or "")
        if binding_id == "":
            return payload
        try:
            primitive_action_plan = self._skill_service.expand_primitive_plan(
                action_id=action_id,
                skill_path_id=binding_id,
            )
        except KeyError:
            pass
        else:
            if primitive_action_plan.primitive_actions:
                payload["primitive_action_plan"] = primitive_action_plan.model_dump()
        return payload

    def _attach_skill_behavior_guardrail(self, *, actor_id: str, plan: dict[str, object]) -> None:
        proposal = plan.get("composite_action_proposal", {})
        if not isinstance(proposal, dict):
            return
        action_id = str(proposal.get("action_id", "") or "")
        action_id = {"observe": "survey_scene", "inspect_object": "survey_scene", "self_protect": "assess_visible_threat"}.get(action_id, action_id)
        if not action_id:
            return
        skill_states = self._skill_service.initial_skill_states(actor_id=actor_id, profile=self._profile_payload(actor_id))
        strategy_tags = proposal.get("preferred_strategy_tags", [])
        evaluation = self._skill_service.evaluate_action(
            actor_id=actor_id,
            action_id=action_id,
            skill_states=skill_states,
            preferred_strategy_tags=[str(tag) for tag in strategy_tags if str(tag)] if isinstance(strategy_tags, list) else [],
        )
        selected_path = evaluation.selected_path
        primitive_action_plan = None
        if selected_path:
            status = "selected_path"
            candidate = self._skill_service.expand_primitive_plan(
                action_id=action_id,
                skill_path_id=str(selected_path.get("binding_id", "") or ""),
            )
            if candidate.primitive_actions:
                primitive_action_plan = candidate
                plan["primitive_action_plan"] = candidate.model_dump()
            else:
                plan.pop("primitive_action_plan", None)
        elif evaluation.blocked_paths:
            status = "no_eligible_path"
        else:
            status = "no_registered_path"
        self._l4.attach_skill_realization_metadata(
            plan=plan,
            skill_evaluation_result=evaluation,
            primitive_action_plan=primitive_action_plan,
        )
        plan["skill_guardrail"] = {
            "status": status,
            "advisory_only": True,
            "execution_preserved": True,
            "source_intent": str(proposal.get("source_intent", "") or ""),
            "action_id": action_id,
            "selected_path": dict(selected_path),
        }

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

    def _prepare_suggestion_request(self, actor_id, interpretation, working_memory_state):
        snapshot_record = self._l1.get_snapshot(actor_id)
        original_snapshot = snapshot_record.model_dump() if snapshot_record is not None else {}
        original_memory = self.get_memory_record_bundle(actor_id)
        prepared = self._run_with_memory_recall(actor_id, snapshot_record,
            lambda memory_override=None: self._l3.prepare_intent_plan(
                interpretation=interpretation,
                control_mode="player_priority_assisted",
                snapshot=original_snapshot,
                profile=self._profile_payload(actor_id),
                memory_bundle=memory_override if memory_override is not None else original_memory,
                working_memory_state=working_memory_state or {},
                current_goal_state=self.get_goal_state(actor_id),
                goal_state_history=self.get_goal_state_history(actor_id),
                supervision_state=self.get_supervision_state(actor_id),
                unresolved_tensions=self.get_unresolved_tensions(actor_id),
                background_agenda_state=self.get_background_agenda_state(actor_id),
            )
        )
        return prepared, original_snapshot, original_memory

    def _freeze_suggestion_request(self, actor_id, frame):
        interpretation = CharacterInterpretation.model_validate(frame['interpretation'])
        prepared, snapshot, memory = self._prepare_suggestion_request(actor_id, interpretation,
            frame['context']['working_memory_state'])
        context = json.loads(json.dumps(dict(snapshot=snapshot, memory=memory),
            default=lambda value: value.model_dump(mode='json'), allow_nan=False))
        return prepared, context

    def _plan_suggestion_effects(self, frame, output):
        from app.character_agent.planning.l3_planner import PreparedCharacterIntentPlan
        prepared = PreparedCharacterIntentPlan.from_json_value(frame['l3_prepared'])
        plan = self._l3.plan_intent_completion(prepared, output)
        context = frame['suggestion_context']
        packet = self._suggestion_from_plan(frame['actor_id'], frame['producer_ts'], prepared.interpretation,
            plan, context['snapshot'], context['memory'])
        return packet.model_dump(mode='json', exclude_none=True)

    def _suggestion_from_plan(self, actor_id, producer_ts, interpretation, plan, original_snapshot, original_memory):
        packet = self._l3.suggestion_from_plan(plan, interpretation=interpretation,
            snapshot=original_snapshot, memory_bundle=original_memory)
        latest_goal_state = self._latest_goal_state_payload(actor_id)
        packet["actor_id"] = actor_id
        packet["producer_ts"] = producer_ts
        packet["causation_id"] = f"character_suggestion:{producer_ts}:{actor_id}"
        packet["correlation_id"] = f"character_suggestion:{producer_ts}:{actor_id}"
        packet["transition_kind"] = str(latest_goal_state.get("transition_kind", "") or "")
        packet["transition_reason_tags"] = list(latest_goal_state.get("transition_reason_tags", [])) if isinstance(latest_goal_state.get("transition_reason_tags", []), list) else []
        suggestion_packet = CharacterSuggestionPacket(**packet)
        return suggestion_packet

    def _planner_suggestion_packet(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        interpretation: CharacterInterpretation,
        working_memory_state: dict[str, object] | None = None,
    ) -> Generator[CognitionRequest, dict[str, object], CharacterSuggestionPacket]:
        prepared, original_snapshot, original_memory = self._prepare_suggestion_request(
            actor_id, interpretation, working_memory_state)
        output = yield CognitionRequest("l3_planning", prepared.request_json,
            str(prepared.behavior_policy.get("candidate_id", "") or ""))
        plan = self._l3.finish_intent_plan(prepared, output)
        suggestion_packet = self._suggestion_from_plan(actor_id, producer_ts, interpretation, plan,
            original_snapshot, original_memory)
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="character_agent_suggestion_packet",
            producer_ts=producer_ts,
            payload=suggestion_packet.model_dump(exclude_none=True),
        )
        self._project_session_event(stored)
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
        )
        return suggestion_packet

    def _build_continuity_floor_suggestion(
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
        return suggestion_packet

    def _continuity_floor_suggestion_packet(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> CharacterSuggestionPacket:
        suggestion_packet = self._build_continuity_floor_suggestion(actor_id=actor_id,
            producer_ts=producer_ts, interpretation=interpretation, decision=decision)
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="character_agent_suggestion_packet",
            producer_ts=producer_ts,
            payload=suggestion_packet.model_dump(exclude_none=True),
        )
        self._project_session_event(stored)
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
        default = self._default_supervision_state(actor_id)
        self._supervision_states[actor_id] = default
        return default

    def _default_supervision_state(self, actor_id):
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

    def _refresh_weak_supervision_from_siming(self, *, actor_id: str, payload: dict[str, object],
                                               producer_ts: int) -> CharacterSupervisionState:
        state = self._plan_weak_supervision_from_siming(actor_id=actor_id, payload=payload, producer_ts=producer_ts)
        if state.current_level in {"medium", "strong"}:
            return state
        self._supervision_states[actor_id] = state
        if self.supports_actor(actor_id):
            self._background_modes[actor_id] = state.active_constraints.background_mode
        return state

    def _plan_weak_supervision_from_siming(
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


    def _background_cognition_event_payload(self, background_payload, interpretation, decision,
                                             supervision_state, unresolved_tensions, agenda_state):
        return dict(background_payload=background_payload, interpretation_summary=interpretation.interpreted_summary,
            selected_intent=decision.selected_intent, goal_primary=decision.primary_goal,
            supervision_state=supervision_state, unresolved_tension_count=len(unresolved_tensions),
            background_agenda_state=agenda_state.model_dump())

    def _plan_background_completion(self, frame, decision_value):
        interpretation = CharacterInterpretation.model_validate(frame['interpretation'])
        decision = CharacterIntentDecision.model_validate(decision_value)
        context = frame['context']
        agenda = self._build_background_agenda_state(actor_id=frame['actor_id'], producer_ts=frame['producer_ts'],
            interpretation=interpretation, decision=decision, supervision_state=context['supervision_state'],
            unresolved_tensions=context['unresolved_tensions'])
        payload = self._background_cognition_event_payload(context['background_payload'], interpretation, decision,
            context['supervision_state'], context['unresolved_tensions'], agenda)
        result = CharacterBackgroundCognitionResult(actor_id=frame['actor_id'], producer_ts=frame['producer_ts'], ran=True,
            reason='background_tick_completed', interpretation_summary=interpretation.interpreted_summary,
            selected_intent=decision.selected_intent, current_level=context['supervision_state']['current_level'])
        return dict(event_type='character_background_cognition_event', producer_ts=frame['producer_ts'], payload=payload), result.model_dump(mode='json'), agenda

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
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="character_background_cognition_event",
            producer_ts=producer_ts,
            payload=self._background_cognition_event_payload(background_payload, interpretation, decision,
                supervision_state, unresolved_tensions, agenda_state),
        )
        self._project_session_event(stored)

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

    def _plan_unresolved_tension(
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
    ) -> CharacterUnresolvedTension | None:
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
        return record

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
        record = self._plan_unresolved_tension(actor_id=actor_id, category=category, summary=summary,
            target_ref=target_ref, producer_ts=producer_ts, source_event_id=source_event_id,
            source_stage=source_stage, priority=priority)
        if record is None:
            return
        self._unresolved_tension_store.upsert(actor_id, record)
        stored = self._append_session_event(
            actor_id=actor_id,
            event_type="character_unresolved_tension_event",
            producer_ts=producer_ts,
            payload=record.model_dump(),
        )
        self._project_session_event(stored)

    def _build_default_control_modes(self) -> dict[str, str]:
        return {
            actor_id: self._profile_registry.get(actor_id).runtime_defaults.default_control_mode
            for actor_id in self._supported_actor_ids
        }

    def _profile_payload(self, actor_id: str) -> dict[str, object]:
        return self._profile_registry.get(actor_id).model_dump()

    def _effective_profile_payload(self, actor_id: str) -> dict[str, object]:
        return resolve_effective_profile(self._profile_payload(actor_id))

    def _need_tension_event_payload(
        self,
        event: CharacterPerceivedEvent,
        snapshot: CharacterPrivateWorldSnapshot,
    ) -> dict[str, object]:
        payload = event.model_dump()
        payload["event_tags"] = self._derived_need_tension_event_tags(event, snapshot)
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

    def _derived_need_tension_event_tags(
        self,
        event: CharacterPerceivedEvent,
        snapshot: CharacterPrivateWorldSnapshot,
    ) -> list[str]:
        tags: list[str] = []
        if event.clarity_score < 0.85 or event.certainty_score < 0.85:
            tags.append("spatial_uncertainty")
        if snapshot.recent_constraint_results:
            tags.append("goal_blocked")
        if any(self._is_siming_pressure_marker(signal) for signal in snapshot.unresolved_signals):
            tags.append("supervision_pressure")
        if event.percept_channel in self._SOCIAL_ENGAGEMENT_CHANNELS and (
            event.source_actor_id or event.target_actor_id
        ):
            tags.append("social_engagement")
        return list(dict.fromkeys(tags))

    @staticmethod
    def _is_siming_pressure_marker(signal: object) -> bool:
        marker = str(signal)
        return marker == "siming_pressure" or marker.startswith("siming_pressure:")

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
        # 名称保留给既有构造故障接缝；正常恢复只安装事务内 current。
        for actor_id in self._session_store.actor_ids():
            self._install_recovery_state(actor_id)
            self._finish_session_projections(actor_id, migration=self._session_migrated)
        if self._session_migrated:
            self._session_store.finish_recovery_migration()

    def _install_recovery_state(self, actor_id: str) -> None:
        state = self._session_store.read_runtime_state(actor_id)
        if state is None:
            return
        self._runtime_field_versions[actor_id] = dict(state.get('field_versions',{}))
        if 'dynamic_state' in state:
            self._dynamic_state_store.write(actor_id, state['dynamic_state'])
        if 'need_tension_state' in state:
            self._need_tension_store.write(actor_id, state['need_tension_state'])
        # 替换单 actor 的已保存窗口，重复安装不会把 goal 再追加一次。
        self._goal_state_store._history_by_actor.pop(actor_id, None)
        self._goal_state_store._by_actor.pop(actor_id, None)
        self._goal_state_store._previous_by_actor.pop(actor_id, None)
        for goal in state.get('goal_history', []):
            self._goal_state_store.write(actor_id, goal)
        self._unresolved_tension_store.clear(actor_id)
        for tension in state.get('unresolved_tensions', []):
            self._unresolved_tension_store.upsert(actor_id, tension)
        supervision = state.get('supervision_state')
        if supervision:
            model = CharacterSupervisionState.model_validate(supervision)
            self._supervision_states[actor_id] = model
            if self.supports_actor(actor_id):
                self._background_modes[actor_id] = model.active_constraints.background_mode
        if state.get('background_agenda_state'):
            self._background_agenda_states[actor_id] = CharacterBackgroundAgendaState.model_validate(state['background_agenda_state'])
        if state.get('continuity_state'):
            self._continuity_state[actor_id] = RuntimeContinuityState.model_validate(state['continuity_state'])
        self._continuity_revisions[actor_id] = state.get('continuity_revision', 0)
        self._shared_module_states[actor_id] = deepcopy(state.get('shared_module_state', {}))
        if state.get('wake_up'):
            self._wake_up_signals[actor_id] = deepcopy(state['wake_up'])
        stage = self._session_store.read_current_cognition_stage(actor_id) if state.get('cognition_stage') else None
        if stage is not None:
            after = stage['plan']['after']
            if after.get('stage') in {'entry', 'l2', 'l3', 'suggestion', 'execution'} and after.get('source_kind') in {'ingest_siming_output', 'run_background_cognition_tick'}:
                if after.get('actor_id') != actor_id or 'entry_after' not in after:
                    raise ValueError('cognition_entry_after_actor_mismatch')
                self._install_cognition_entry_after(actor_id, stage['plan'])
                if after.get('policy_consumed') and after.get('policy_id'):
                    self._l3._consumed_behavior_policy_ids.add(after['policy_id'])
                self._l3._consumed_behavior_policy_ids.update(after.get('consumed_policy_ids', []))
                if after.get('background_result', {}).get('ran'):
                    self._last_background_tick_ms[actor_id] = after['producer_ts']
                if after.get('stage') == 'execution':
                    self._install_execution_request_state(actor_id, after['execution'])

    def _rehydrate_graph_continuity(self) -> None:
        self._memory_store.bind_session_reader(
            self._session_store.list_events, working_reader=self._working_memory_events,
            summary_reader=self._session_store.read_memory_summary,
        )
        self._l1.get_actor_scene_knowledge_store().bind_persistence(self._session_store)
        self._session_migrated = self._session_store.initialize_recovery(
            import_legacy=self._import_legacy_graph_continuity,
            project_event=self._update_memory_scene_knowledge_unchecked,
        )
        if self._continuity_store is not None and hasattr(self._continuity_store, 'bind_snapshot_reader'):
            self._continuity_store.bind_snapshot_reader(self._export_continuity_snapshot)

    def _working_memory_events(self, actor_id: str):
        through_index = self._session_store.event_count(actor_id)
        after_index = 0
        while after_index < through_index:
            page = self._session_store.read_events_page(
                actor_id, after_index=after_index, through_index=through_index,
                event_types=tuple(sorted(CharacterWorkingMemory.RELEVANT_EVENT_TYPES)), limit=128,
            )
            if not page:
                break
            yield from page
            after_index = page[-1]["event_index"]

    def _append_session_event(self, actor_id: str, event_type: str, producer_ts: int,
                              payload: dict[str, object], expected_revision: int | None = None) -> dict[str, object]:
        # 失败投影须先完成，保证正常恢复的未应用后缀至多一条。
        self._finish_session_projections(actor_id)
        event = self._session_store.append_event(actor_id=actor_id, event_type=event_type,
            producer_ts=producer_ts, payload=payload, expected_revision=expected_revision)
        state = self._session_store.read_runtime_state(actor_id)
        if event_type == 'character_simulation_seed_event':
            self._install_recovery_state(actor_id)
        elif event_type == 'dynamic_state_event':
            self._dynamic_state_store.write(actor_id, state['dynamic_state'])
            self._runtime_field_versions.setdefault(actor_id, {})['dynamic_state'] = state['field_versions']['dynamic_state']
        elif event_type in {'character_supervision_authorization', 'character_supervision_cleared'}:
            model = CharacterSupervisionState.model_validate(state['supervision_state'])
            self._supervision_states[actor_id] = model
            if self.supports_actor(actor_id):
                self._background_modes[actor_id] = model.active_constraints.background_mode
            self._runtime_field_versions.setdefault(actor_id, {})['supervision_state'] = state['field_versions']['supervision_state']
        elif event_type == 'goal_state_event':
            self._goal_state_store.write(actor_id, state['goal_history'][-1])
        self._project_session_event(event)
        return event

    def _finish_session_projections(self, actor_id: str, *, migration: bool = False) -> None:
        head = self._session_store.event_count(actor_id)
        cursors = [self._session_store.projection_cursor(actor_id, kind) for kind in ('memory','ask')]
        cursor = min(cursors)
        if any(value < 0 or value > head for value in cursors):
            raise ValueError('character_session_projection_rebuild_required')
        if not migration and head - cursor > 1:
            # 只有原子阶段回执能证明这个多事件后缀；仍拒绝任意历史重建。
            for event in self._session_store.read_cognition_stage_suffix(actor_id, after_index=cursor, through_index=head):
                self._project_session_event(event)
            return
        while cursor < head:
            events = self._session_store.read_events_page(actor_id, after_index=cursor, through_index=head, limit=128 if migration else 1)
            if not events:
                raise ValueError('character_session_projection_gap')
            for event in events:
                self._project_session_event(event)
                cursor = int(event['event_index'])

    def _project_session_event(self, event: dict[str, object]) -> None:
        actor_id, index = str(event['actor_id']), int(event['event_index'])
        if self._session_store.projection_cursor(actor_id, 'memory') < index:
            self._memory_store.write_event(event)
            self._session_store.set_projection_cursor(actor_id, 'memory', index)
        self._update_memory_scene_knowledge(event)

    def _import_legacy_graph_continuity(self) -> dict[str, dict[str, object]]:
        if self._continuity_store is None:
            return {}
        for actor_id in sorted(self._supported_actor_ids | self._continuity_actor_ids):
            checkpoint = dict(self._continuity_store.read_snapshot(actor_id) or {})
            current = dict(self._continuity_store.read_current_state(actor_id) or {})
            timeline, extra = self._session_store.merge_legacy_continuity(actor_id, checkpoint, current)
            if timeline is not None:
                self._session_store.import_timeline(actor_id, timeline)
            if extra:
                self._legacy_runtime_extras[actor_id] = extra
        return self._legacy_runtime_extras

    def _persist_graph_continuity(self, *, actor_id: str, producer_ts: int) -> None:
        with self._continuity_flush_locks.setdefault(actor_id, RLock()):
            self._persist_graph_continuity_locked(actor_id=actor_id, producer_ts=producer_ts)

    def _persist_graph_continuity_locked(self, *, actor_id: str, producer_ts: int) -> None:
        count = self._session_timeline_event_count(actor_id)
        if not count:
            return
        self._finish_session_projections(actor_id)
        snapshot = {'continuity_state': self.get_runtime_continuity_state(actor_id),
                    'dynamic_state': self._dynamic_state_store.read_record(actor_id).storage_dump()}
        # 弱监管也可能由 Siming 更新而没有独立 authorization event。
        if actor_id in self._supervision_states:
            snapshot['supervision_state'] = self._supervision_states[actor_id].model_dump(mode='json')
        self._session_store.save_runtime_state(actor_id, expected_head=count, snapshot=snapshot,
            field_versions=self._runtime_field_versions.get(actor_id, {}))
        state = self._session_store.read_runtime_state(actor_id)
        if self._continuity_store is not None:
            self._continuity_store.write_current_state(actor_id=actor_id, producer_ts=producer_ts,
                source_event_ref=str(state['event_id']), snapshot=state)

    def _export_continuity_snapshot(self, actor_id: str) -> dict[str, object] | None:
        state = self._session_store.read_runtime_state(actor_id)
        if state is None:
            return None
        return {
            'working_memory': self.get_working_memory_state(actor_id),
            'dynamic_state': state.get('dynamic_state', {}),
            'need_tension_state': state.get('need_tension_state', {}),
            'supervision_state': state.get('supervision_state', {}),
            'goal_state': state.get('goal_history', [{}])[-1],
            'goal_state_history': state.get('goal_history', []),
            'session_timeline': self.get_session_timeline(actor_id),
            'continuity_state': state.get('continuity_state', {}),
            'continuity_revisions': state.get('continuity_revision', 0),
            'continuity_receipts': self._session_store.list_receipts(actor_id, 'continuity'),
            'materialization_receipts': self._session_store.list_receipts(actor_id, 'materialization'),
            'pending_seed_candidates': {value['candidate_id']: value for value in self._session_store.list_candidates(actor_id)},
            'seed_projection': self.get_seed_projection(actor_id),
            'shared_module_state': deepcopy(state.get('shared_module_state', {})),
            'checkpoint_event_index': state['event_index'],
            CharacterGraphContinuityStore.SOURCE_EVENT_REF_FIELD: state['event_id'],
        }

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
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
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
            memory_summary=self._memory_store.debug_memory_summary(actor_id) if memory_bundle is None else None,
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
        entry = self._session_store.last_event(actor_id, event_type="goal_state_event")
        if entry is not None:
            payload = entry.get("payload", {})
            if isinstance(payload, dict):
                return dict(payload)
        return {}

    def _plan_cognition_cadence(self, actor_id: str, producer_ts: int, *, wake_up: bool = False) -> dict:
        previous = self._last_cognition_tick_ms.get(actor_id)
        deferred = (self._cadence_policy.degraded_mode and previous is not None
            and producer_ts - previous < self._cadence_policy.cognition_interval_ms and not wake_up)
        return dict(deferred=deferred, last_tick=previous if deferred else producer_ts)

    def _should_defer_cognition(self, actor_id: str, producer_ts: int) -> bool:
        planned = self._plan_cognition_cadence(actor_id, producer_ts)
        if planned['last_tick'] is not None:
            self._last_cognition_tick_ms[actor_id] = planned['last_tick']
        return planned['deferred']

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
        return self._defer_social_request(self._last_social_request_tick_ms, actor_id, request_type, target_actor_id, producer_ts)

    def _defer_social_request(self, ticks, actor_id, request_type, target_actor_id, producer_ts):
        if not self._cadence_policy.degraded_mode:
            if request_type in {"approach", "follow_target", "seek_private_distance", "withdraw", "break_contact"} and target_actor_id != "":
                ticks[(actor_id, request_type, target_actor_id)] = producer_ts
            return False
        if request_type not in {"approach", "follow_target", "seek_private_distance", "withdraw", "break_contact"}:
            return False
        if target_actor_id == "":
            return False
        key = (actor_id, request_type, target_actor_id)
        previous_tick = ticks.get(key)
        if previous_tick is None:
            ticks[key] = producer_ts
            return False
        if producer_ts - previous_tick < self._cadence_policy.cognition_interval_ms:
            return True
        ticks[key] = producer_ts
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
