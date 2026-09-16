from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Sequence

from pydantic import Field, TypeAdapter, model_validator

from app.models.authority_event import AuthorityEvent
from app.population_continuity.models import ContinuityModel
from app.population_continuity.decision_surface import PopulationDecision
from app.population_continuity.hot_state import HOT_FIELDS


def _check_vector(value: dict[str, int]) -> None:
    if any(not key or isinstance(revision, bool) or revision < 0 for key, revision in value.items()):
        raise ValueError("revision_vector_invalid")


class PopulationCadenceInput(ContinuityModel):
    cadence_id: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    world_mode_ref: str = Field(min_length=1)
    world_mode_revision: str = Field(min_length=1)
    cadence_source_ref: str = ""
    cadence_source_revision: int = Field(default=0, ge=0)
    window_start: int = Field(ge=0)
    window_end: int = Field(ge=0)
    base_checkpoint_ref: str = Field(min_length=1)
    base_checkpoint_digest: str = Field(min_length=1)
    base_revision_vector: dict[str, int] = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    selector_revision: str = Field(min_length=1)
    ruleset_revision: str = Field(min_length=1)
    deterministic_seed: str = Field(min_length=1)
    catch_up_limit: int = Field(ge=0)
    budget: int = Field(ge=0)
    report_scope: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def accept_world_mode_names(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "cadence_id" not in data and "cadence_ref" in data:
            data["cadence_id"] = data.pop("cadence_ref")
        if "world_mode_ref" not in data and "mode_ref" in data:
            data["world_mode_ref"] = data.pop("mode_ref")
        if "world_mode_revision" not in data and "mode_revision" in data:
            data["world_mode_revision"] = data.pop("mode_revision")
        legacy_refs = data.pop("source_refs", None)
        legacy_vector = data.pop("source_revision_vector", None)
        if legacy_refs is not None or legacy_vector is not None:
            if not isinstance(legacy_refs, (list, tuple)) or len(legacy_refs) != 1 or not isinstance(legacy_refs[0], str) or not legacy_refs[0]:
                raise ValueError("cadence_source_pin_incomplete")
            if not isinstance(legacy_vector, dict) or len(legacy_vector) != 1:
                raise ValueError("cadence_source_pin_incomplete")
            vector_ref, vector_revision = next(iter(legacy_vector.items()))
            if vector_ref != legacy_refs[0]:
                raise ValueError("revision_vector_invalid")
            canonical_ref = data.get("cadence_source_ref")
            canonical_revision = data.get("cadence_source_revision")
            if canonical_ref is not None and canonical_ref != legacy_refs[0]:
                raise ValueError("cadence_source_pin_incomplete")
            if canonical_revision is not None and canonical_revision != vector_revision:
                raise ValueError("revision_vector_invalid")
            data.setdefault("cadence_source_ref", legacy_refs[0])
            data.setdefault("cadence_source_revision", vector_revision)
        return data

    @model_validator(mode="after")
    def validate_cadence(self) -> "PopulationCadenceInput":
        if self.window_end <= self.window_start:
            raise ValueError("cadence_window_invalid")
        if not self.cadence_source_ref:
            raise ValueError("cadence_source_pin_incomplete")
        if isinstance(self.cadence_source_revision, bool) or self.cadence_source_revision < 0:
            raise ValueError("cadence_source_pin_incomplete")
        _check_vector(self.base_revision_vector)
        return self

    @property
    def cadence_ref(self) -> str:
        return self.cadence_id

    @property
    def source_refs(self) -> tuple[str, ...]:
        return (self.cadence_source_ref,)

    @property
    def source_revision_vector(self) -> dict[str, int]:
        return {self.cadence_source_ref: self.cadence_source_revision}

    @classmethod
    def from_authority_event(cls, event: AuthorityEvent) -> "PopulationCadenceInput":
        if event.event_type != "population_cadence_event":
            raise ValueError("cadence_event_type_invalid")
        payload_value = event.payload.get("population_cadence")
        if not isinstance(payload_value, dict):
            raise ValueError("cadence_source_pin_incomplete")
        payload = dict(payload_value)
        if payload.get("revoked") is True or payload.get("status") in {"revoked", "stale", "expired"}:
            raise ValueError("cadence_authorization_revoked")
        envelope_scope = payload.pop("scope", None)
        if envelope_scope not in (None, payload.get("report_scope")):
            raise ValueError("cadence_scope_incompatible")
        return cls.model_validate(payload)


class PopulationProjection(ContinuityModel):
    ref: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    revision_vector: dict[str, int] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_projection(self) -> "PopulationProjection":
        _check_vector(self.revision_vector)
        return self


_POPULATION_PROJECTIONS_ADAPTER = TypeAdapter(tuple[PopulationProjection, ...])


def dump_population_projections(
    projections: Sequence[PopulationProjection],
) -> list[dict[str, Any]]:
    return list(
        _POPULATION_PROJECTIONS_ADAPTER.dump_python(tuple(projections), mode="json")
    )


class PopulationB0ContinuousDelta(ContinuityModel):
    """无写权限的客观连续推进结果；只能由 cadence 确认路径提交。"""

    actor_ref: str = Field(min_length=1)
    fidelity_tier: Literal["B0"] = "B0"
    from_tick: int = Field(ge=0)
    to_tick: int = Field(ge=0)
    simulation_tick_cursor: int = Field(ge=0)
    actor_revision: int = Field(ge=0)
    state_deltas: dict[str, Any] = Field(default_factory=dict)
    presentation_seed: dict[str, Any] = Field(default_factory=dict)
    due_obligation_refs: tuple[str, ...] = ()
    source_revision_vector: dict[str, int] = Field(min_length=1)
    scope: Literal["public"] = "public"
    idempotency_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_delta(self) -> "PopulationB0ContinuousDelta":
        if not self.actor_ref.startswith("character:"):
            raise ValueError("b0_actor_ref_invalid")
        if self.to_tick <= self.from_tick:
            raise ValueError("b0_window_invalid")
        if self.simulation_tick_cursor != self.to_tick:
            raise ValueError("b0_cursor_invalid")
        _check_vector(self.source_revision_vector)
        unknown = set(self.state_deltas).difference(HOT_FIELDS)
        if unknown:
            raise ValueError("b0_state_field_not_allowed")
        integer_fields = {"last_update_tick", "next_due_tick"}
        numeric_fields = {"fatigue", "need_pressure", "starvation_credit"}
        for key, value in self.state_deltas.items():
            if key in integer_fields and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError("b0_state_value_invalid")
            if key in numeric_fields and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not 0.0 <= float(value) <= 1.0
            ):
                raise ValueError("b0_state_value_invalid")
            if key == "activity_phase" and value not in {
                "rest", "routine", "routine_work", "leisure"
            }:
                raise ValueError("b0_state_value_invalid")
        if any(not isinstance(ref, str) or not ref for ref in self.due_obligation_refs):
            raise ValueError("b0_due_obligation_invalid")
        return self

    def __getitem__(self, key: str) -> Any:
        aliases = {"window_start": "from_tick", "window_end": "to_tick"}
        return getattr(self, aliases.get(key, key))

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except AttributeError:
            return default


class PopulationB0BatchStats(ContinuityModel):
    """有界 cadence 统计，不包含居民历史或私有 profile。"""

    cadence_id: str = Field(min_length=1)
    read_set_digest: str = Field(min_length=1)
    actor_count: int = Field(ge=0)
    due_count: int = Field(ge=0)
    deferred_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)


class PopulationReadSet(ContinuityModel):
    cadence: PopulationCadenceInput
    projections: tuple[PopulationProjection, ...] = ()
    read_set_digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_projection_refs(self) -> "PopulationReadSet":
        refs = [projection.ref for projection in self.projections]
        if len(refs) != len(set(refs)):
            raise ValueError("read_set_projection_duplicate")
        return self

    @classmethod
    def from_inputs(
        cls,
        cadence: PopulationCadenceInput,
        projections: Sequence[PopulationProjection],
    ) -> "PopulationReadSet":
        ordered = tuple(sorted(projections, key=lambda item: item.ref))
        refs = tuple(item.ref for item in ordered)
        if len(refs) != len(set(refs)):
            raise ValueError("read_set_projection_duplicate")
        canonical = {
            "cadence": cadence.model_dump(mode="json"),
            "projections": dump_population_projections(ordered),
        }
        encoded = json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode()
        return cls.model_construct(
            cadence=cadence,
            projections=ordered,
            read_set_digest="sha256:" + hashlib.sha256(encoded).hexdigest(),
        )


class PopulationOwnerReceipt(ContinuityModel):
    receipt_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    event_family: str = Field(min_length=1)
    committed: bool
    revision_vector: dict[str, int] = Field(default_factory=dict)
    zero_write: bool
    idempotency_status: str = "new_commit"
    settlement_status: Literal[
        "committed", "duplicate", "requeue", "rejected", "zero_write"
    ] = "zero_write"
    reason: str = ""

    @model_validator(mode="before")
    @classmethod
    def derive_settlement_status(cls, value: object) -> object:
        if not isinstance(value, dict) or value.get("settlement_status") is not None:
            return value
        data = dict(value)
        if data.get("committed") and data.get("idempotency_status") == "duplicate_replayed":
            data["settlement_status"] = "duplicate"
        elif data.get("committed") and not data.get("zero_write"):
            data["settlement_status"] = "committed"
        elif data.get("committed"):
            data["settlement_status"] = "zero_write"
        else:
            data["settlement_status"] = "rejected"
        return data

    @model_validator(mode="after")
    def validate_receipt_vector(self) -> "PopulationOwnerReceipt":
        _check_vector(self.revision_vector)
        return self


class PopulationOwnerBatchResult(ContinuityModel):
    receipts: tuple[PopulationOwnerReceipt, ...]
    append_count: int = Field(ge=0, le=1)
    atomic: bool


class PopulationBatchReport(ContinuityModel):
    batch_ref: str = Field(min_length=1)
    cohort_ref: str | None = None
    cohort_member_refs: tuple[str, ...] = ()
    selected_cohort_refs: tuple[str, ...] = ()
    presentation_seeds: dict[str, Any] = Field(default_factory=dict)
    activation_candidates: tuple[str, ...] = ()
    owner_bound_intents: tuple[Any, ...] = ()
    rejected_candidates: tuple[Any, ...] = ()
    budget_used: int = Field(ge=0)
    budget_remaining: int = Field(ge=0)
    unprocessed_cohort_refs: tuple[str, ...] = ()
    selected_count: int = Field(default=0, ge=0)
    unprocessed_count: int = Field(default=0, ge=0)
    presentation_seed_count: int = Field(default=0, ge=0)
    activation_candidate_count: int = Field(default=0, ge=0)
    owner_intent_count: int = Field(default=0, ge=0)
    owner_committed_count: int = Field(default=0, ge=0)
    continuity_committed_count: int = Field(default=0, ge=0)
    continuity_requeue_count: int = Field(default=0, ge=0)
    read_set_digest: str = Field(min_length=1)
    result_digest: str = Field(min_length=1)


class PopulationCognitionStats(ContinuityModel):
    b0_advanced: int = Field(default=0, ge=0)
    quiet_actors: int = Field(default=0, ge=0)
    active_actors: int = Field(default=0, ge=0)
    deep_selected: int = Field(default=0, ge=0)
    deep_deferred: int = Field(default=0, ge=0)
    llm_queued: int = Field(default=0, ge=0)
    llm_completed: int = Field(default=0, ge=0)
    llm_expired: int = Field(default=0, ge=0)
    max_wait_windows: int = Field(default=0, ge=0)
    requeue_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def bound_requeue_reasons(self) -> "PopulationCognitionStats":
        if len(self.requeue_reasons) > 16 or any(not reason for reason in self.requeue_reasons):
            raise ValueError("population_cognition_stats_unbounded")
        return self


class PopulationCycleResult(ContinuityModel):
    status: Literal["accepted", "owner_settlement_required", "requeue", "rejected"]
    batch_ref: str = Field(min_length=1)
    report: PopulationBatchReport
    seed_candidates: tuple[Any, ...] = ()
    owner_receipts: tuple[PopulationOwnerReceipt, ...] = ()
    continuity_receipts: tuple[Any, ...] = ()
    audits: tuple[Any, ...] = ()
    reason: str = ""
    production_append_count: int = Field(ge=0)
    decision: PopulationDecision | None = None
    b0_results: tuple[PopulationB0ContinuousDelta, ...] = ()
    cognition_stats: PopulationCognitionStats = Field(
        default_factory=PopulationCognitionStats
    )
