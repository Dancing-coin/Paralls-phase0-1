from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .world import PopulationCadenceConfirmationReceipt
from .siming_contracts import PopulationCadenceInput

if TYPE_CHECKING:
    from .world import WorldContinuityRuntime


def population_kernel_digest() -> str:
    """摘要跨机器使用相同源码文本；同时覆盖实际绑定的 kernel，不能只信版本名。"""
    from . import world

    names = ("continuous.py", "hot_state.py", "world.py", "recovery.py", "siming_contracts.py",
             "publication.py", "store_projection_assembler.py", "domain_projection_sources.py")
    sources = {name: (Path(__file__).parent / name).read_text(encoding="utf-8") for name in names}
    # 对实际 code 取源码，避免 functools.wraps 的 __wrapped__ 隐藏正在执行的包装实现。
    sources["active_b0_kernel"] = inspect.getsource(world.advance_b0_row.__code__).replace("\r\n", "\n")
    return recovery_digest(sources)


def recovery_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _validate_receipt_binding(receipt: PopulationCadenceConfirmationReceipt, fingerprint: str) -> None:
    counts = (receipt.advanced_count, receipt.presentation_due_count, receipt.new_due_count, receipt.due_count,
              receipt.deferred_count, receipt.rejected_count, receipt.due_backlog_count)
    if (any(value < 0 for value in counts) or receipt.new_due_count != receipt.presentation_due_count
            or receipt.due_count != receipt.presentation_due_count or receipt.deferred_count != receipt.due_backlog_count
            or receipt.rejected_count != 0 or any(re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
                for value in (fingerprint, receipt.projection_digest, receipt.result_digest))):
        raise ValueError("population_recovery_confirmation_invalid")
    # 与 world 既有确认公式相同；此处所有字符串是 ASCII sha256。
    expected = recovery_digest({"cadence": fingerprint, "projection_digest": receipt.projection_digest,
                                "advanced_count": receipt.advanced_count,
                                "presentation_due_count": receipt.presentation_due_count,
                                "due_backlog_count": receipt.due_backlog_count})
    if receipt.result_digest != expected:
        raise ValueError("population_recovery_receipt_digest_mismatch")


class _RecoveryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RecoveryActor(_RecoveryModel):
    actor_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    last_update_tick: int = Field(ge=0)
    activity_phase: Literal["rest", "routine", "routine_work", "leisure"]
    fatigue: float = Field(ge=0, le=1, allow_inf_nan=False)
    need_pressure: float = Field(ge=0, le=1, allow_inf_nan=False)
    next_due_tick: int = Field(ge=0)
    starvation_credit: float = Field(ge=0, le=1, allow_inf_nan=False)


class RecoveryDueEntry(_RecoveryModel):
    actor_id: str = Field(min_length=1)
    obligation_id: str = Field(min_length=1)
    due_tick: int = Field(ge=0)
    revision: int = Field(ge=0)


class PopulationRecoveryState(_RecoveryModel):
    """只包含可重建的最新热状态；权威事件锚点由 publisher 单独核验。"""

    schema_version: Literal[1]
    context_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    confirmed_tick: int | None = Field(ge=0)
    rule_identity: tuple[str, str, str, str] | None
    actors: tuple[RecoveryActor, ...]
    due_entries: tuple[RecoveryDueEntry, ...]
    last_receipt: PopulationCadenceConfirmationReceipt | None
    last_fingerprint: str | None = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    state_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def consistent_state(self) -> PopulationRecoveryState:
        if recovery_digest(self.model_dump(mode="json", exclude={"state_digest"})) != self.state_digest:
            raise ValueError("population_recovery_state_digest_mismatch")
        ids = tuple(actor.actor_id for actor in self.actors)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("population_recovery_actor_order_invalid")
        actors = {actor.actor_id: actor for actor in self.actors}
        keys = [(entry.actor_id, entry.obligation_id) for entry in self.due_entries]
        if keys != sorted(set(keys)):
            raise ValueError("population_recovery_due_keys_invalid")
        for entry in self.due_entries:
            actor = actors.get(entry.actor_id)
            if actor is None:
                raise ValueError("population_recovery_due_actor_invalid")
            if entry.obligation_id == "b0:presentation-threshold" and (
                entry.due_tick != actor.next_due_tick or entry.revision != actor.revision
            ):
                raise ValueError("population_recovery_due_revision_invalid")
        if any(actor.last_update_tick != (self.confirmed_tick or 0) for actor in self.actors):
            raise ValueError("population_recovery_actor_tick_invalid")
        if self.confirmed_tick is None:
            if any(value is not None for value in (self.rule_identity, self.last_receipt, self.last_fingerprint)):
                raise ValueError("population_recovery_confirmation_invalid")
        else:
            receipt = self.last_receipt
            if (receipt is None or self.last_fingerprint is None or self.rule_identity is None
                    or not all(self.rule_identity) or self.rule_identity[-1] != "public"
                    or receipt.status != "committed" or not receipt.cadence_id
                    or receipt.window_start < 0 or receipt.window_start >= receipt.window_end
                    or receipt.window_end != self.confirmed_tick or receipt.advanced_count != len(self.actors)):
                raise ValueError("population_recovery_confirmation_invalid")
            _validate_receipt_binding(receipt, self.last_fingerprint)
        return self


class PopulationRecoveryCheckpoint(_RecoveryModel):
    schema_version: Literal[1]
    canonical_version: Literal[1]
    context_digest: str
    kernel_digest: str
    cadence: PopulationCadenceInput
    event_id: str = Field(min_length=1)
    cadence_stream_revision: int = Field(ge=1)
    global_sequence: int = Field(ge=1)
    record_digest: str
    receipt: PopulationCadenceConfirmationReceipt
    fingerprint: str
    recovery_state: PopulationRecoveryState | None = None

    @model_validator(mode="after")
    def bound_receipt(self) -> PopulationRecoveryCheckpoint:
        if self.fingerprint != recovery_digest(self.cadence.model_dump(mode="json")):
            raise ValueError("population_recovery_checkpoint_fingerprint")
        receipt = self.receipt
        _validate_receipt_binding(receipt, self.fingerprint)
        if (receipt.status != "committed" or receipt.cadence_id != self.cadence.cadence_id
                or receipt.window_start != self.cadence.window_start or receipt.window_end != self.cadence.window_end):
            raise ValueError("population_recovery_checkpoint_receipt")
        state = self.recovery_state
        if state is not None and (state.last_receipt != receipt or state.last_fingerprint != self.fingerprint
                or state.confirmed_tick != self.cadence.window_end or state.context_digest != self.context_digest
                or state.rule_identity != (self.cadence.policy_revision, self.cadence.selector_revision,
                                          self.cadence.ruleset_revision, self.cadence.report_scope)):
            raise ValueError("population_recovery_checkpoint_state")
        return self


def parse_population_checkpoint(world: WorldContinuityRuntime, checkpoint) -> PopulationRecoveryCheckpoint:
    """在安装热状态前验证原事实、delivered 锚点和当前规则实现。"""
    data = PopulationRecoveryCheckpoint.model_validate_json(json.dumps(checkpoint.state))
    kernel_digest = getattr(world, "_population_kernel_digest", None) or population_kernel_digest()
    if (checkpoint.projector_version != "1" or checkpoint.projection_schema_version != 1
            or checkpoint.projection_hash != recovery_digest(checkpoint.model_dump(mode="json", exclude={"projection_hash"}))
            or data.context_digest != world._recovery_context_digest()
            or data.kernel_digest != kernel_digest
            or data.cadence.world_ref != world.mode.world_ref or data.cadence.world_mode_revision != world.mode.revision
            or data.receipt.advanced_count != len(world.roster.actor_ids)):
        raise ValueError("population_recovery_checkpoint_context")
    stream = f"population-cadence:{world.mode.world_ref}"
    expected_projector = ("population-recovery:" if data.recovery_state is not None else "population-receipt:") + world.mode.world_ref
    expected_id = (f"{expected_projector}:{(data.cadence_stream_revision // 16) % 2}" if data.recovery_state is not None
                   else f"{expected_projector}:{data.cadence.cadence_id}")
    if (checkpoint.projector_id != expected_projector or checkpoint.checkpoint_id != expected_id
            or checkpoint.last_global_sequence != data.global_sequence
            or checkpoint.source_revision_vector != {stream: data.cadence_stream_revision}
            or checkpoint.applied_event_ids != [data.event_id]):
        raise ValueError("population_recovery_checkpoint_anchor")
    event = world.store.get_event(data.event_id)
    record = event.payload
    record_hash = "sha256:" + hashlib.sha256(json.dumps(
        {key: value for key, value in record.items() if key != "record_digest"},
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    outbox = world.store.get_outbox(f"outbox:population-runtime:{data.cadence.cadence_id}")
    if (event.stream_id != stream or event.stream_revision != data.cadence_stream_revision
            or event.global_sequence != data.global_sequence or event.event_type != "population.cadence.admitted"
            or record.get("record_digest") != data.record_digest or record_hash != data.record_digest
            or record.get("cadence") != data.cadence.model_dump(mode="json")
            or outbox.event_id != event.event_id or outbox.transaction_id != event.transaction_id
            or outbox.delivery_state != "delivered"):
        raise ValueError("population_recovery_checkpoint_anchor")
    return data


def durable_population_receipt(world: WorldContinuityRuntime, cadence: PopulationCadenceInput):
    checkpoint = world.store.get_projection_checkpoint(f"population-receipt:{world.mode.world_ref}:{cadence.cadence_id}")
    if checkpoint is None:
        return None
    data = parse_population_checkpoint(world, checkpoint)
    if data.fingerprint != world._cadence_fingerprint(cadence):
        raise ValueError("population_cadence_confirmation_conflict")
    return data.receipt
