from __future__ import annotations

import pytest

from app.services.siming_orchestration import AUDITORS
from app.services.siming_orchestrator import OrchestratorTick, SimingOrchestrator


def _orchestrator(**updates: object) -> SimingOrchestrator:
    values: dict[str, object] = {
        "pressure_threshold": 2,
        "survival_threshold": 4,
    }
    values.update(updates)
    return SimingOrchestrator(**values)


def test_fresh_orchestrator_has_no_snapshot_before_any_event() -> None:
    # An empty snapshot would read as "measured and balanced".
    orchestrator = _orchestrator()

    assert orchestrator.build_fairness_snapshot() is None


def test_tick_without_events_still_writes_an_audit() -> None:
    result = _orchestrator().tick(sim_tick_ts=1.0, world_ts=1.0)

    assert result.consumed_events == 0
    assert any(audit.reason.startswith("orchestrator") for audit in result.audits)


def test_tick_reports_standard_mode_when_queue_is_short() -> None:
    result = _orchestrator().tick(sim_tick_ts=1.0, world_ts=1.0)

    assert result.mode == "standard"
    assert result.shed_priorities == ()


def test_queue_depth_selects_pressure_then_survival() -> None:
    orchestrator = _orchestrator()

    for _ in range(2):
        orchestrator.ingest_event(_event())
    assert orchestrator.current_mode() == "pressure"

    for _ in range(2):
        orchestrator.ingest_event(_event())
    assert orchestrator.current_mode() == "survival"


def test_survival_mode_sheds_enhancement_priorities_but_not_the_main_chain() -> None:
    orchestrator = _orchestrator()
    for _ in range(4):
        orchestrator.ingest_event(_event())

    result = orchestrator.tick(sim_tick_ts=1.0, world_ts=1.0)

    assert result.mode == "survival"
    assert "P0" not in result.shed_priorities
    assert "P1" not in result.shed_priorities
    assert "P3" in result.shed_priorities
    assert "P4" in result.shed_priorities


def test_standard_mode_schedules_all_five_auditors() -> None:
    orchestrator = _orchestrator()

    assert orchestrator.scheduled_auditors("standard") == AUDITORS
    assert {r.status for r in orchestrator.auditor_results("standard")} == {"fresh"}


def test_pressure_mode_downsamples_only_suspicion() -> None:
    orchestrator = _orchestrator()

    scheduled = orchestrator.scheduled_auditors("pressure")

    assert "suspicion_auditor" not in scheduled
    assert len(scheduled) == 4
    assert "conversation_access_auditor" in scheduled


def test_shed_auditor_still_yields_a_dimension_object() -> None:
    orchestrator = _orchestrator()
    for _ in range(2):
        orchestrator.ingest_event(_event())
    orchestrator.tick(sim_tick_ts=1.0, world_ts=1.0)

    results = orchestrator.auditor_results("pressure")

    # Shed auditors must report a degraded dimension, not vanish.
    assert len(results) == 5
    degraded = [r for r in results if r.status != "fresh"]
    assert [r.auditor for r in degraded] == ["suspicion_auditor"]
    assert degraded[0].reason == "runtime_pressure"
    assert degraded[0].dimension_id == "suspicion_heat_distribution"


def test_snapshot_marks_shed_dimension_unavailable_not_missing() -> None:
    orchestrator = _orchestrator()
    for _ in range(2):
        orchestrator.ingest_event(_event())
    result = orchestrator.tick(sim_tick_ts=1.0, world_ts=1.0)

    # Rebuild with the mode the cycle actually ran in, not the now-drained queue.
    snapshot = orchestrator.build_fairness_snapshot(mode=result.mode)

    assert snapshot is not None
    dimension = snapshot.dimensions["suspicion_heat_distribution"]
    assert dimension.status == "unavailable"
    assert dimension.reason == "runtime_pressure"


def test_ingest_then_tick_consumes_the_queue_exactly_once() -> None:
    orchestrator = _orchestrator()
    orchestrator.ingest_event(_event())

    first = orchestrator.tick(sim_tick_ts=1.0, world_ts=1.0)
    second = orchestrator.tick(sim_tick_ts=2.0, world_ts=2.0)

    assert first.consumed_events == 1
    assert second.consumed_events == 0
    assert orchestrator.pending_events() == 0


def test_audit_records_mode_and_shedding_for_diagnosis() -> None:
    orchestrator = _orchestrator()
    for _ in range(4):
        orchestrator.ingest_event(_event())

    result = orchestrator.tick(sim_tick_ts=1.0, world_ts=1.0)
    cycle = [a for a in result.audits if a.reason.startswith("orchestrator")][-1]

    assert "mode=survival" in cycle.reason
    assert "degraded_auditors=1" in cycle.reason
    assert "P3" in cycle.reason


def test_read_model_reflects_the_snapshot_after_the_cycle() -> None:
    orchestrator = _orchestrator()
    orchestrator.ingest_event(_event())

    result = orchestrator.tick(sim_tick_ts=1.0, world_ts=1.0)

    assert result.read_model is not None
    assert result.read_model["snapshot_id"] == result.snapshot.snapshot_id
    assert result.read_model["audit_count"] == len(result.audits)


def test_read_model_is_absent_without_a_snapshot() -> None:
    result = _orchestrator().tick(sim_tick_ts=1.0, world_ts=1.0)

    assert result.read_model is None


def test_inverted_thresholds_are_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="survival_threshold_below_pressure_threshold"):
        SimingOrchestrator(pressure_threshold=10, survival_threshold=5)


def test_tick_result_is_a_stable_contract_object() -> None:
    result = _orchestrator().tick(sim_tick_ts=1.0, world_ts=1.0)

    assert isinstance(result, OrchestratorTick)
    assert set(result.model_dump()) == {
        "mode",
        "consumed_events",
        "snapshot",
        "candidate_outputs",
        "decision_outputs",
        "dispatch_outputs",
        "audits",
        "read_model",
        "auditor_results",
        "shed_priorities",
        "budget_overruns",
    }


def test_nine_contract_methods_are_present() -> None:
    orchestrator = _orchestrator()
    required = (
        "ingest_event",
        "build_fairness_snapshot",
        "generate_intervention_candidates",
        "evaluate_candidates",
        "select_intervention",
        "dispatch_intervention",
        "audit_cycle",
        "refresh_read_model",
        "tick",
    )

    for name in required:
        assert callable(getattr(orchestrator, name)), name


def test_stage_methods_partition_the_runtime_outputs() -> None:
    orchestrator = _orchestrator()
    orchestrator.ingest_event(_event())
    result = orchestrator.tick(sim_tick_ts=1.0, world_ts=1.0)
    outputs = result.candidate_outputs + result.decision_outputs + result.dispatch_outputs

    if outputs:
        # The three stage views must not overlap.
        assert len({o.output_type for o in outputs}) == len(outputs)
    assert orchestrator.dispatch_intervention(result.dispatch_outputs) == result.dispatch_outputs
    assert orchestrator.select_intervention(result.decision_outputs) == result.decision_outputs


def _event():
    from app.models.authority_event import AuthorityEvent
    from app.models.siming_event import SimingInput

    return SimingInput(
        input_type="world_fact_event",
        source_event=AuthorityEvent(
            event_id="world_fact:1",
            event_type="world_fact_event",
            producer_ts=1,
            room_id="room:1",
            scene_id="scene:1",
            zone_id="zone:1",
            source={"layer": "L1", "system": "world_fact", "actor_id": "char_a"},
            routing={"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
            priority="p2",
            ttl=5000,
            durability="replayable",
            causation_id="cause:1",
            correlation_id="corr:1",
            payload={"fact_type": "light_level_drop"},
        ),
    )
