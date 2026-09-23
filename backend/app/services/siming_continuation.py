"""Siming 专用 JSON 阶段协议；worker 不持有任何 owner 服务。"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.authority_event import AuthorityEvent
from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch
from app.models.siming_narrative import NarrativeRoomState
from app.models.siming_runtime_state import NarrativeObligationLedgerSnapshot
from app.models.siming_adaptive_bridge import GeneratedAdaptiveBridgeProposalBatch
from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate, SimingInput, SimingTickResult
from app.models.siming_runtime_state import ObservedSimingEvent, StateTreeSnapshot, StorylineStateSnapshot, ProjectionRunSnapshot
from app.services.siming_llm_provider import SimingLlmProviderError, SimingLlmProviderTimeout, SimingLlmProviderInvalidOutput


def json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


CANDIDATE_TIMELINE_REQUEUE = "candidate_timeline_changed"
RETRYABLE_SIMING_PROVIDER_ERRORS = frozenset({
    "SimingLlmProviderError",
    "SimingLlmProviderInvalidOutput",
})


def candidate_timeline_changed(previous: dict, current: dict) -> bool:
    """只允许原候选读集的 actor timeline 改变，其余授权与请求仍须精确相同。"""
    from copy import deepcopy
    if previous == current or not previous.get("actors") or previous.get("actors", {}).keys() != current.get("actors", {}).keys():
        return False
    left, right = deepcopy(previous), deepcopy(current)
    for actor in left["actors"]:
        for pin in (left, right):
            value = pin["actors"][actor]
            # 生产 Character getter 返回排序 tuple pairs，冻结 JSON 后为 list pairs。
            if not isinstance(value, list) or any(
                    not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str)
                    for pair in value):
                return False
            names = [pair[0] for pair in value]
            if "timeline" not in names or len(names) != len(set(names)):
                return False
            pin["actors"][actor] = [pair for pair in value if pair[0] != "timeline"]
    return left == right


class SimingCandidate(InterventionCandidate):
    # 保留同步 provider 已支持的三个高层提示；绝不允许低层控制字段。
    pressure_hint: str | None = None
    salience_boost: float | None = None
    reason_scope: str | None = None


class SimingProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    stage: Literal["candidate", "adaptive"]
    snapshot: FairnessStateSnapshot | None = None
    event: AuthorityEvent
    compiled_context: dict | None = None


class SimingProviderCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_digest: str
    candidates: list[SimingCandidate] = Field(default_factory=list)
    proposal_batch: GeneratedAdaptiveBridgeProposalBatch | None = None
    error: Literal["", "SimingLlmProviderTimeout", "SimingLlmProviderInvalidOutput", "SimingLlmProviderError", "ValueError"] = ""
    message: str = ""


def run_siming_provider(provider: object, request_json: bytes) -> bytes:
    """唯一跨线程入口：纯 JSON 请求、独立 provider 和纯 JSON completion。"""
    request = SimingProviderRequest.model_validate_json(request_json)
    completion = SimingProviderCompletion(request_digest=hashlib.sha256(request_json).hexdigest())
    try:
        if request.stage == "candidate":
            if request.snapshot is None:
                raise ValueError("candidate snapshot required")
            values = provider.generate_candidates(snapshot=request.snapshot, recent_events=[request.event], recent_audit=[])
            completion.candidates = [SimingCandidate.model_validate(
                item.model_dump(mode="json") if isinstance(item, BaseModel) else
                {key: getattr(item, key) for key in SimingCandidate.model_fields if hasattr(item, key)}
            ) for item in values]
        else:
            batch = provider.generate_adaptive_bridge_proposals(compiled_context=request.compiled_context, correlation_id=request.event.correlation_id)
            completion.proposal_batch = GeneratedAdaptiveBridgeProposalBatch.model_validate(batch)
    except SimingLlmProviderError as error:
        completion.error = ("SimingLlmProviderTimeout" if isinstance(error, SimingLlmProviderTimeout) else
                            "SimingLlmProviderInvalidOutput" if isinstance(error, SimingLlmProviderInvalidOutput) else "SimingLlmProviderError")
        completion.message = str(error)
    except ValueError as error:
        if request.stage != "candidate":
            raise
        completion.error, completion.message = "ValueError", str(error)
    return completion.model_dump_json().encode("utf-8")


class PreparedSimingJob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    turn_id: str
    source_event_id: str
    stage: Literal["candidate", "adaptive"]
    attempt: int = Field(default=1, ge=1)
    token: str
    generation: str
    request_json: bytes
    pin_digest: str
    idempotency_key: str
    deadline: float = Field(allow_inf_nan=False)


class SimingTurnFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    turn_id: str
    siming_input: SimingInput
    stage: Literal["initial", "adaptive", "candidate", "completed"] = "initial"
    result: SimingTickResult = Field(default_factory=SimingTickResult)
    observed: list[ObservedSimingEvent] = Field(default_factory=list)
    prepared: dict | None = None
    heavenly_frame: dict | None = None
    state_tree: StateTreeSnapshot | None = None
    fairness_snapshot: FairnessStateSnapshot | None = None
    storyline: StorylineStateSnapshot | None = None
    projection: ProjectionRunSnapshot | None = None
    narrative_summary: dict | None = None
    quality_summary: dict | None = None
    guardrail_summary: dict | None = None
    policy_snapshot: FairnessStateSnapshot | None = None
    request: SimingProviderRequest | None = None
    actor_ids: list[str] = Field(default_factory=list)
    pin: dict = Field(default_factory=dict)
    job: PreparedSimingJob | None = None
    synchronous: bool = False
    expires_at: float = Field(default=0.0, allow_inf_nan=False)


class SimingAdvance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["pending", "completed", "zero_write", "failed"]
    job: PreparedSimingJob | None = None
    result: SimingTickResult | None = None
    replayed: bool = False
    reason: str = ""


class SimingCompletionValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["accepted", "zero_write"]
    reason: str = ""
    completion: SimingProviderCompletion | None = None


class SimingStageEffects(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batches: list[HeavenlyGraphWriteBatch] = Field(default_factory=list)
    observatory_messages: list[dict] = Field(default_factory=list)
    narrative_state: NarrativeRoomState | None = None
    state_tree: StateTreeSnapshot | None = None
    storyline: StorylineStateSnapshot | None = None
    obligation_ledger: NarrativeObligationLedgerSnapshot | None = None


class SimingAcceptedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    after: SimingTurnFrame
    effects: SimingStageEffects
