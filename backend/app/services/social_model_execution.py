"""纯契约校验，不认证客户端自签授权，不读取或提交世界事实。"""
from app.models.social_model import (
    DAILY_SUPPLY_DIMENSIONS, FrozenModelInput, ModelComputation, ModelRunGrant, SocialModelTemplate,
)
from dataclasses import dataclass

from app.models.social_model import DailySupplyReport, ModelRunReceipt, SocialModelDraft
from app.models.siming_event import SimingAuditRecord
from app.population_continuity.daily_supply import calculate_daily_supply, daily_supply_template
from app.population_continuity.simulation_contracts import simulation_digest


def validate_model_run(*, template: SocialModelTemplate, grant: ModelRunGrant,
                       inputs: FrozenModelInput, tick: int) -> None:
    template = SocialModelTemplate.model_validate(template)
    grant = ModelRunGrant.model_validate(grant)
    inputs = FrozenModelInput.model_validate(inputs)
    if type(tick) is not int or tick < 0:
        raise ValueError("model_tick_invalid")
    if grant.mode == "off" or grant.issued_tick > tick:
        raise ValueError("policy_denied")
    if (grant.reader_ref, grant.purpose, grant.scope) != (inputs.reader_ref, inputs.purpose, inputs.scope):
        raise ValueError("policy_denied")
    if ((grant.template_ref, grant.definition_version, grant.operator_revision)
            != (template.template_ref, template.definition_version, template.operator_revision)
            or (inputs.vector.template_ref, inputs.vector.definition_version, inputs.vector.operator_revision)
            != (template.template_ref, template.definition_version, template.operator_revision)
            or grant.policy_revision != inputs.vector.policy_revision):
        raise ValueError("policy_denied")
    if (inputs.vector.from_tick, inputs.vector.to_tick) != grant.analysis_window:
        raise ValueError("policy_denied")
    if inputs.vector.to_tick - inputs.vector.from_tick > template.max_analysis_window:
        raise ValueError("policy_denied")
    if tick >= min(grant.expiry_tick, inputs.vector.expiry_tick, *(card.expiry_tick for card in inputs.cards)):
        raise ValueError("stale_input")
    if any(tick < max(card.valid_at, card.recorded_at) for card in inputs.cards):
        raise ValueError("stale_input")
    if grant.budget_units < len(DAILY_SUPPLY_DIMENSIONS):
        raise ValueError("budget_exhausted")
    data = inputs.data
    if any(value is None for value in (data.qualification_confirmed, data.route_open, data.process_open,
                                       data.arrival_delay_ticks, data.deadline_tick)):
        raise ValueError("context_insufficient")


def validate_model_computation(*, computation: ModelComputation, inputs: FrozenModelInput,
                               grant: ModelRunGrant) -> None:
    computation = ModelComputation.model_validate(computation)
    inputs = FrozenModelInput.model_validate(inputs)
    grant = ModelRunGrant.model_validate(grant)
    if grant.mode == "off" or (grant.reader_ref, grant.purpose, grant.scope) != (inputs.reader_ref, inputs.purpose, inputs.scope):
        raise ValueError("policy_denied")
    if computation.work_units > grant.budget_units:
        raise ValueError("budget_exhausted")
    report = computation.report
    if report is None:
        return
    if grant.policy_revision != inputs.vector.policy_revision:
        raise ValueError("policy_denied")
    data = inputs.data
    if any(value is None for value in (data.qualification_confirmed, data.route_open, data.process_open,
                                       data.arrival_delay_ticks, data.deadline_tick)):
        raise ValueError("context_insufficient")
    if (not data.qualification_confirmed or not data.route_open or not data.process_open
            or inputs.vector.from_tick + data.arrival_delay_ticks > data.deadline_tick):
        if report.reachable_supply_units != (0, 0) or not report.blocking_reasons:
            raise ValueError("model_report_known_block_ignored")
    if report.reachable_supply_units[1] > data.confirmed_supply_units:
        raise ValueError("model_report_supply_exceeded")
    if computation.work_units < len(DAILY_SUPPLY_DIMENSIONS):
        raise ValueError("model_work_units_invalid")
    if (report.shard_ref != inputs.shard_ref or (report.from_tick, report.to_tick) != grant.analysis_window
            or (report.from_tick, report.to_tick) != (inputs.vector.from_tick, inputs.vector.to_tick)
            or report.demand_units != inputs.data.demand_units
            or report.confirmed_supply_units != inputs.data.confirmed_supply_units
            or report.input_digest != inputs.vector.input_digest
            or report.source_revisions != inputs.vector.source_revisions
            or report.expiry_tick > min(grant.expiry_tick, inputs.vector.expiry_tick, *(card.expiry_tick for card in inputs.cards))):
        raise ValueError("model_report_input_mismatch")


@dataclass(frozen=True)
class SocialModelExecutionResult:
    receipt: ModelRunReceipt
    report: DailySupplyReport | None = None


class SocialModelExecutionService:
    """由受信装配提供当前授权和窄读侧；请求不能传入 grant 或事实。"""

    def __init__(self, *, grant_reader, input_reader, revision_reader, audit_writer, room_id):
        self._grant_reader = grant_reader
        self._input_reader = input_reader
        self._revision_reader = revision_reader
        self._audit_writer = audit_writer
        self._room_id = room_id

    def run(self, draft, *, reader_ref, scope, tick):
        draft = SocialModelDraft.model_validate(draft)
        if type(tick) is not int or tick < 0:
            raise ValueError("model_tick_invalid")
        arguments = dict(draft=draft, reader_ref=reader_ref, scope=scope, tick=tick)
        grant, inputs, computation = None, None, None
        status, validation, degradation = "policy_denied", "denied", ()
        try:
            issued = self._grant_reader(**arguments)
            grant = ModelRunGrant.model_validate(issued) if issued is not None else None
            if (grant is None or (grant.reader_ref, grant.scope, grant.analysis_window, grant.correlation_ref)
                    != (reader_ref, scope, draft.window, draft.correlation_ref)):
                raise ValueError("policy_denied")
            if tick < grant.issued_tick:
                raise ValueError("policy_denied")
            if tick >= grant.expiry_tick:
                raise ValueError("stale_input")
            if grant.mode == "off":
                status, validation, degradation = "proposal_only", "not_checked", ("mode_off",)
            else:
                raw = self._input_reader(draft, grant)
                if raw is None:
                    degradation = ("source_contract_missing",)
                    raise ValueError("context_insufficient")
                inputs = FrozenModelInput.model_validate(raw)
                if inputs.shard_ref != draft.shard_ref:
                    raise ValueError("policy_denied")
                validate_model_run(template=daily_supply_template(), grant=grant, inputs=inputs, tick=tick)
                computation = calculate_daily_supply(inputs, budget_units=grant.budget_units)
                if computation.report is not None:
                    computation = computation.model_copy(update={"report": computation.report.model_copy(
                        update={"expiry_tick": min(grant.expiry_tick, computation.report.expiry_tick)})})
                validate_model_computation(computation=computation, inputs=inputs, grant=grant)
                current = self._grant_reader(**arguments)
                if current is None or ModelRunGrant.model_validate(current) != grant:
                    raise ValueError("policy_denied")
                if any(self._revision_reader(ref) != revision for ref, revision in inputs.vector.source_revisions.items()):
                    raise ValueError("stale_input")
                # 再核对授权过滤内容、查询、名单和观察时间，不能只比较流 head。
                current_input = self._input_reader(draft, grant)
                if current_input is None or FrozenModelInput.model_validate(current_input) != inputs:
                    raise ValueError("stale_input")
                # 窄读侧也可能跨越治理变更，再次确认授权及全部依赖。
                current = self._grant_reader(**arguments)
                if current is None or ModelRunGrant.model_validate(current) != grant:
                    raise ValueError("policy_denied")
                if any(self._revision_reader(ref) != revision for ref, revision in inputs.vector.source_revisions.items()):
                    raise ValueError("stale_input")
                status, validation = computation.status, "pins_checked"
        except ValueError as error:
            reason = str(error)
            status = reason if reason in {"policy_denied", "stale_input", "budget_exhausted", "context_insufficient"} else "error"
            validation = {"policy_denied": "denied", "stale_input": "stale",
                "context_insufficient": "unavailable"}.get(status, "not_checked")
            computation = None
        except OSError:
            status, validation, computation = "owner_unavailable", "unavailable", None
            degradation = ("owner_read_unavailable",)
        receipt = ModelRunReceipt(receipt_ref="model-receipt:" + simulation_digest(dict(
            draft=draft.model_dump(mode="json"), grant=grant.model_dump(mode="json") if grant else None,
            status=status, input_digest=inputs.vector.input_digest if inputs else None, tick=tick)),
            correlation_ref=draft.correlation_ref, grant_ref=grant.grant_ref if grant else "grant:unavailable",
            grant_revision=grant.revision if grant else "unavailable", template_ref=draft.template_ref,
            definition_version="1", operator_revision="daily-supply-operators@1",
            policy_revision=grant.policy_revision if grant else "policy:unavailable",
            reader_ref=reader_ref, purpose="daily_supply_analysis", scope=scope, mode=grant.mode if grant else "off",
            status=status, input_digest=inputs.vector.input_digest if inputs else None,
            output_digest=simulation_digest(computation.report.model_dump(mode="json"))
                if computation and computation.report else None,
            read_card_refs=tuple(card.card_ref for card in inputs.cards) if inputs else (),
            source_revisions=inputs.vector.source_revisions if inputs else {},
            work_units=computation.work_units if computation else 0, budget_units=grant.budget_units if grant else 0,
            source_validation=validation, degradation=degradation)
        self._audit_writer.record(SimingAuditRecord(audit_id=receipt.receipt_ref, room_id=self._room_id,
            correlation_id=draft.correlation_ref, causation_id=draft.correlation_ref,
            source_event_id=draft.correlation_ref, status="recorded", reason=receipt.model_dump_json()))
        return SocialModelExecutionResult(receipt=receipt,
            report=computation.report if computation and grant.mode == "advisory" else None)


class PopulationDailySupplyObserver:
    """原 cadence 的可选只读旁路；分片及权限由后端装配固定。"""

    def __init__(self, *, service, reader_ref, scope, shard_ref):
        self._service, self._reader_ref = service, reader_ref
        self._scope, self._shard_ref = scope, shard_ref

    def __call__(self, read_set):
        cadence = read_set.cadence
        return self._service.run(SocialModelDraft(template_ref="daily-shard-supply@1",
            shard_ref=self._shard_ref, window=(cadence.window_start, cadence.window_end),
            correlation_ref=cadence.cadence_id), reader_ref=self._reader_ref, scope=self._scope,
            tick=cadence.window_end)
