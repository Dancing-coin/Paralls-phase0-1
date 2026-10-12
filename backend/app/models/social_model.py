"""固定日供给模板的共享契约；事实和授权仍由原 Owner 提供。"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from app.population_continuity.simulation_contracts import (
    FrozenJsonObject, FrozenPolicyPins, FrozenRevisionVector, SimulationContract, simulation_digest,
)


DAILY_SUPPLY_DIMENSIONS = (
    "qualification", "custody", "reachability", "process", "commitment", "constraint", "risk", "summary",
)
ModelStatus = Literal["ok", "unknown", "context_insufficient", "proposal_only", "graph_unavailable",
    "graph_degraded", "owner_unavailable", "stale_input", "budget_exhausted", "policy_denied",
    "conflict_detected", "error"]
ModelMode = Literal["off", "shadow", "advisory"]
Reference = Annotated[str, Field(min_length=1)]
Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
OptionalDigest = Annotated[str, Field(pattern=r"^(?:sha256:[0-9a-f]{64})?$")]
Unit = Annotated[int, Field(ge=0, le=2**63-1)]
Bps = Annotated[int, Field(ge=0, le=10000)]


def _ordered(value: tuple[int, int]) -> tuple[int, int]:
    if value[0] > value[1]:
        raise ValueError("model_interval_invalid")
    return value


UnitRange = Annotated[tuple[Unit, Unit], AfterValidator(_ordered)]
BpsRange = Annotated[tuple[Bps, Bps], AfterValidator(_ordered)]


def _pins(value):
    if any(not key or not pin for key, pin in value.items()):
        raise ValueError("model_pin_invalid")
    return value


Pins = Annotated[FrozenPolicyPins, AfterValidator(_pins)]


class SocialModelTemplate(SimulationContract):
    template_ref: Literal["daily-shard-supply@1"] = "daily-shard-supply@1"
    definition_version: Literal["1"] = "1"
    operator_revision: Literal["daily-supply-operators@1"] = "daily-supply-operators@1"
    max_analysis_window: Literal[86400] = 86400
    max_work_units: Literal[100] = 100
    dimensions: tuple[str, ...] = DAILY_SUPPLY_DIMENSIONS

    @model_validator(mode="after")
    def fixed_dimensions(self):
        if self.dimensions != DAILY_SUPPLY_DIMENSIONS:
            raise ValueError("model_template_dimensions_invalid")
        return self


class SocialModelDraft(SimulationContract):
    template_ref: Literal["daily-shard-supply@1"]
    shard_ref: Reference
    window: UnitRange
    correlation_ref: Reference

    @model_validator(mode="after")
    def bounded_window(self):
        if not 0 < self.window[1] - self.window[0] <= 86400:
            raise ValueError("policy_denied")
        return self


class ModelRunGrant(SimulationContract):
    grant_ref: Reference
    revision: Reference
    reader_ref: Reference
    purpose: Literal["daily_supply_analysis"]
    scope: Reference
    mode: ModelMode
    template_ref: Literal["daily-shard-supply@1"]
    definition_version: Literal["1"]
    operator_revision: Literal["daily-supply-operators@1"]
    policy_revision: Reference
    issued_tick: Unit
    expiry_tick: Unit
    budget_units: Annotated[int, Field(ge=0, le=100)]
    analysis_window: UnitRange
    correlation_ref: Reference

    @model_validator(mode="after")
    def validity(self):
        if self.expiry_tick <= self.issued_tick or not 0 < self.analysis_window[1] - self.analysis_window[0] <= 86400:
            raise ValueError("policy_denied")
        return self


class FactCard(SimulationContract):
    card_ref: Reference
    fact_kind: Literal["qualification", "custody", "reachability", "process", "commitment", "constraint", "risk", "summary"]
    owner_ref: Reference
    source_ref: Reference
    source_revision: Reference
    source_revision_vector: FrozenRevisionVector
    source_digest: Digest
    reader_ref: Reference
    purpose: Literal["daily_supply_analysis"]
    scope: Reference
    valid_at: Unit
    recorded_at: Unit
    expiry_tick: Unit
    content: FrozenJsonObject
    content_digest: OptionalDigest = ""

    @model_validator(mode="after")
    def content_pin(self):
        if not self.source_revision_vector or self.expiry_tick <= self.valid_at or self.expiry_tick <= self.recorded_at:
            raise ValueError("model_card_source_invalid")
        digest = simulation_digest(self.model_dump(mode="json")["content"])
        if self.content_digest and self.content_digest != digest:
            raise ValueError("model_card_content_digest_mismatch")
        object.__setattr__(self, "content_digest", digest)
        return self


# 两个逻辑名称复用同一窄来源凭据，不形成另一份事实模型。
Proof = FactCard


class InputVersionVector(SimulationContract):
    source_revisions: FrozenRevisionVector
    query_pins: Pins
    shard_revision: Reference
    projection_digests: Pins
    content_digests: Pins
    policy_revision: Reference
    template_ref: Literal["daily-shard-supply@1"]
    definition_version: Literal["1"]
    operator_revision: Literal["daily-supply-operators@1"]
    observed_at: Reference
    from_tick: Unit
    to_tick: Unit
    expiry_tick: Unit
    input_digest: OptionalDigest = ""

    @model_validator(mode="after")
    def declared_dependencies(self):
        if not self.source_revisions or not self.query_pins or self.to_tick <= self.from_tick:
            raise ValueError("model_source_context_insufficient")
        for digest in (*self.projection_digests.values(), *self.content_digests.values()):
            if not digest.startswith("sha256:") or len(digest) != 71 or any(c not in "0123456789abcdef" for c in digest[7:]):
                raise ValueError("model_source_digest_invalid")
        return self


class DailySupplyInput(SimulationContract):
    resource_unit: Reference
    custody_ref: Reference
    route_ref: Reference
    demand_units: UnitRange
    confirmed_supply_units: Unit
    window_capacity_units: Unit
    capacity_factor_bps: Bps
    delivery_ratio_bps: BpsRange
    qualification_confirmed: bool | None
    route_open: bool | None
    process_open: bool | None
    arrival_delay_ticks: Unit | None
    deadline_tick: Unit | None
    protected_categories: tuple[Reference, ...] = ()


class FrozenModelInput(SimulationContract):
    reader_ref: Reference
    purpose: Literal["daily_supply_analysis"]
    scope: Reference
    shard_ref: Reference
    cards: tuple[FactCard, ...]
    vector: InputVersionVector
    data: DailySupplyInput

    @model_validator(mode="after")
    def source_and_input_pins(self):
        cards = tuple(sorted(self.cards, key=lambda card: (card.fact_kind, card.card_ref)))
        if len(cards) != len(DAILY_SUPPLY_DIMENSIONS) or {card.fact_kind for card in cards} != set(DAILY_SUPPLY_DIMENSIONS):
            raise ValueError("context_insufficient")
        if len({card.card_ref for card in cards}) != len(cards):
            raise ValueError("model_duplicate_card")
        revisions, projections, contents = {}, {}, {}
        for card in cards:
            if (card.reader_ref, card.purpose, card.scope) != (self.reader_ref, self.purpose, self.scope):
                raise ValueError("policy_denied")
            for ref, revision in card.source_revision_vector.items():
                if ref in revisions and revisions[ref] != revision:
                    raise ValueError("model_source_revision_conflict")
                revisions[ref] = revision
            if card.source_ref in projections and projections[card.source_ref] != card.source_digest:
                raise ValueError("model_source_digest_conflict")
            projections[card.source_ref] = card.source_digest
            contents[card.card_ref] = card.content_digest
        if (dict(self.vector.source_revisions) != revisions or dict(self.vector.projection_digests) != projections
                or dict(self.vector.content_digests) != contents):
            raise ValueError("model_source_vector_mismatch")
        object.__setattr__(self, "cards", cards)
        values = self.model_dump(mode="json")
        values["vector"].pop("input_digest")
        digest = simulation_digest(values)
        if self.vector.input_digest and self.vector.input_digest != digest:
            raise ValueError("model_input_digest_mismatch")
        object.__setattr__(self, "vector", self.vector.model_copy(update={"input_digest": digest}))
        return self


class DailySupplyReport(SimulationContract):
    shard_ref: Reference
    from_tick: Unit
    to_tick: Unit
    demand_units: UnitRange
    confirmed_supply_units: Unit
    reachable_supply_units: UnitRange
    coverage_bps: BpsRange | None
    blocking_reasons: tuple[Reference, ...]
    upgrade_categories: tuple[Reference, ...]
    input_digest: Digest
    source_revisions: FrozenRevisionVector
    expiry_tick: Unit

    @model_validator(mode="after")
    def complete_report(self):
        if self.to_tick <= self.from_tick or not self.source_revisions:
            raise ValueError("model_report_context_invalid")
        zero = self.demand_units == (0, 0)
        if zero != (self.coverage_bps is None) or zero != ("not_required" in self.blocking_reasons):
            raise ValueError("model_report_zero_demand_invalid")
        if not zero and self.reachable_supply_units == (0, 0) and self.coverage_bps != (0, 0):
            raise ValueError("model_report_zero_reachability_invalid")
        return self


class ModelComputation(SimulationContract):
    status: ModelStatus
    report: DailySupplyReport | None = None
    work_units: Unit
    diagnostics: tuple[Reference, ...] = ()

    @model_validator(mode="after")
    def result_completeness(self):
        if (self.status in {"ok", "graph_degraded"}) != (self.report is not None):
            raise ValueError("model_report_status_invalid")
        return self


class ModelRunReceipt(SimulationContract):
    receipt_ref: Reference
    correlation_ref: Reference
    grant_ref: Reference
    grant_revision: Reference
    template_ref: Literal["daily-shard-supply@1"]
    definition_version: Literal["1"]
    operator_revision: Literal["daily-supply-operators@1"]
    policy_revision: Reference
    reader_ref: Reference
    purpose: Literal["daily_supply_analysis"]
    scope: Reference
    mode: ModelMode
    status: ModelStatus
    input_digest: Digest | None
    output_digest: Digest | None
    read_card_refs: tuple[Reference, ...]
    source_revisions: FrozenRevisionVector
    work_units: Unit
    budget_units: Annotated[int, Field(ge=0, le=100)]
    source_validation: Literal["not_checked", "pins_checked", "stale", "denied", "unavailable"]
    degradation: tuple[Reference, ...] = ()

    @model_validator(mode="after")
    def minimal_result(self):
        if (self.status in {"ok", "graph_degraded"}) != (self.output_digest is not None):
            raise ValueError("model_receipt_output_invalid")
        if self.output_digest is not None and (self.input_digest is None or not self.read_card_refs or not self.source_revisions):
            raise ValueError("model_receipt_input_missing")
        return self
