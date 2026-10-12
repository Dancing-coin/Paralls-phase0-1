"""合成完整来源仅验证模式语义；真实洪灾 Owner 缺口单独失败闭合。"""
import pytest

from app.models.social_model import FrozenModelInput, SocialModelDraft
from app.population_continuity.flood_vertical import FloodPopulationFixture
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.social_model_execution import SocialModelExecutionService
from app.services.social_model_execution import PopulationDailySupplyObserver
from app.services.siming_runtime import SimingRuntime
from test_social_model_execution_contract import grant, standard_inputs


def make_service(*, mode="shadow", inputs=None, on_read=None):
    current = {"grant": grant(mode=mode)}
    revisions = dict(standard_inputs().vector.source_revisions)
    audit = SimingAuditWriter()
    reads = []

    def read(draft, issued):
        reads.append(draft)
        if on_read:
            on_read(current, revisions)
        return standard_inputs() if inputs is None else inputs

    service = SocialModelExecutionService(grant_reader=lambda **kwargs: current["grant"],
        input_reader=read, revision_reader=revisions.get, audit_writer=audit, room_id="room:test")
    return service, current, revisions, audit, reads


def run(service, *, tick=1):
    return service.run(SocialModelDraft(template_ref="daily-shard-supply@1", shard_ref="shard:1",
        window=(0, 20), correlation_ref="correlation:1"), reader_ref="siming:test", scope="cohort:1", tick=tick)


def test_off_does_not_read_model_sources_or_expose_report():
    service, _, _, _, reads = make_service(mode="off")
    result = run(service)
    assert not reads and result.report is None
    assert result.receipt.status == "proposal_only" and result.receipt.work_units == 0


def test_shadow_is_audit_only_while_advisory_exposes_the_same_pure_report():
    shadow, _, _, audit, _ = make_service()
    observed = run(shadow)
    advisory, _, _, _, _ = make_service(mode="advisory")
    visible = run(advisory)
    assert observed.report is None and visible.report.coverage_bps == (3428, 5167)
    assert observed.receipt.output_digest == visible.receipt.output_digest
    serialized = audit.get_record(observed.receipt.receipt_ref).reason
    assert '"output_digest"' in serialized
    assert '"content"' not in serialized and '"confirmed_supply_units"' not in serialized


@pytest.mark.parametrize("source", tuple(standard_inputs().vector.source_revisions))
def test_every_source_pin_is_rechecked_before_model_exposure(source):
    service, _, _, _, _ = make_service(mode="advisory", on_read=lambda current, heads: heads.update({source: 2}))
    result = run(service)
    assert result.report is None and result.receipt.status == "stale_input"


def test_revocation_during_source_read_cannot_expose_advisory():
    service, _, _, _, _ = make_service(mode="advisory", on_read=lambda current, heads: current.update(grant=None))
    result = run(service)
    assert result.receipt.status == "policy_denied" and result.report is None


@pytest.mark.parametrize("tick,status", [(100, "stale_input"), (1, "budget_exhausted")])
def test_time_and_budget_fail_without_complete_report(tick, status):
    service, current, _, _, _ = make_service(mode="advisory")
    if status == "budget_exhausted":
        current["grant"] = grant(mode="advisory", budget_units=7)
    result = run(service, tick=tick)
    assert result.receipt.status == status and result.report is None


def test_real_owner_gap_never_invents_route_process_or_shard_facts(tmp_path):
    case = FloodPopulationFixture.create(storage_root=tmp_path)
    try:
        case.run_window(from_tick=0, to_tick=3600)
        before = case.authority_snapshot()
        service = SocialModelExecutionService(grant_reader=lambda **kwargs: grant(mode="advisory"),
            input_reader=lambda draft, issued: None, revision_reader=case.store.get_stream_head,
            audit_writer=SimingAuditWriter(), room_id="room:flood")
        result = run(service)
        assert result.receipt.status == "context_insufficient" and result.report is None
        assert "source_contract_missing" in result.receipt.degradation
        assert case.authority_snapshot() == before
    finally:
        case.close()


def test_public_siming_observer_cannot_add_owner_core_or_handoff_work(tmp_path):
    case = FloodPopulationFixture.create(storage_root=tmp_path)
    try:
        service = SocialModelExecutionService(grant_reader=lambda **kwargs: grant(mode="shadow",
            scope="cohort:flood", correlation_ref=kwargs["draft"].correlation_ref,
            analysis_window=kwargs["draft"].window, expiry_tick=10000),
            input_reader=lambda draft, issued: None, revision_reader=case.store.get_stream_head,
            audit_writer=SimingAuditWriter(), room_id="room:flood")
        observer = PopulationDailySupplyObserver(service=service, reader_ref="siming:test",
            scope="cohort:flood", shard_ref="shard:flood")
        case.siming = SimingRuntime(population_capability=case.capability, population_model_observer=observer)
        result = case.run_window(from_tick=0, to_tick=3600)
        assert len(result.owner_receipts) == 1
        assert len(result.continuity_receipts) == 2
        assert not case.intersections
        assert not case.last_siming_result.model_reports
        assert case.last_siming_result.model_execution_receipts[0].status == "context_insufficient"
        assert case.world.latest_confirmation.advanced_count == 1
    finally:
        case.close()


@pytest.mark.parametrize("change", [{"observed_at": "2026-10-10T05:15:00Z"},
    {"shard_revision": "2"}, {"query_pins": {"query:members": "2"}}])
def test_current_content_query_and_observation_must_match_the_original_freeze(change):
    service, _, _, _, _ = make_service(mode="advisory")
    original = standard_inputs()
    changed = FrozenModelInput.model_validate({**original.model_dump(),
        "vector": {**original.vector.model_dump(), **change, "input_digest": ""}})
    values = iter((original, changed))
    service._input_reader = lambda *args: next(values)
    result = run(service)
    assert result.receipt.status == "stale_input" and result.report is None


def test_source_read_failure_is_formal_and_does_not_expose_partial_report():
    service, _, _, _, _ = make_service(mode="advisory")

    def unavailable(*args):
        raise OSError("source offline")

    service._input_reader = unavailable
    result = run(service)
    assert result.receipt.status == "owner_unavailable" and result.report is None


def test_unauthorized_scope_does_not_read_model_facts():
    service, current, _, _, reads = make_service(mode="advisory")
    current["grant"] = grant(mode="advisory", scope="cohort:other")
    result = run(service)
    assert result.receipt.status == "policy_denied" and not reads
