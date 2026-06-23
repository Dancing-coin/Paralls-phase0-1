from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingInput
from app.models.siming_runtime_state import ProjectionRunSnapshot
from app.services.siming_runtime import SimingRuntime


def make_visual_fact_event(
    *,
    event_type: str = "visual_fact_event",
    payload_overrides: dict[str, object] | None = None,
    **event_overrides: object,
) -> AuthorityEvent:
    payload = {
        "event_id": "visual_fact:300:char_c:light_level_drop",
        "event_type": event_type,
        "producer_ts": 300,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
        "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
        "priority": "p2",
        "ttl": 5000,
        "durability": "replayable",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "payload": {
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:char_c:light_level_drop",
            "target_environment_id": "env_lamp",
            "target_actor_id": "char_b",
        },
    }
    payload["payload"].update(payload_overrides or {})  # type: ignore[index, union-attr]
    payload.update(event_overrides)
    return AuthorityEvent.model_validate(payload)


class StubProjection:
    def project(self, *, state_tree, fairness, storyline, ledger) -> ProjectionRunSnapshot:  # type: ignore[no-untyped-def]
        return ProjectionRunSnapshot(
            projection_id=f"projection:{state_tree.room_id}:{state_tree.sim_tick_ts}",
            schema_version=1,
            producer_system="siming.projection.stub",
            room_id=state_tree.room_id,
            world_ts=state_tree.world_ts,
            sim_tick_ts=state_tree.sim_tick_ts,
            causation_id=state_tree.causation_id,
            correlation_id=state_tree.correlation_id,
            status="fresh",
            basis_state_tree_ref=state_tree.snapshot_id,
            basis_fairness_snapshot_ref=fairness.snapshot_id,
            candidate_hints=[],
            summary={"mode": "stubbed"},
        )


def test_tick_returns_state_tree_storyline_checkpoint_and_read_model() -> None:
    runtime = SimingRuntime()

    result = runtime.tick(
        [SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())]
    )

    assert result.checkpoints
    assert result.read_model is not None
    assert result.checkpoints[0].state_tree_snapshot_ref is not None
    assert result.checkpoints[0].storyline_snapshot_ref is not None
    assert result.read_model.derived_from_snapshot_ref is not None
    assert result.read_model.derived_from_snapshot_ref.startswith("fairness:")
    assert any(output.output_type == "fairness_snapshot" for output in result.outputs)
    assert any(output.output_type == "intervention_candidate" for output in result.outputs)
    assert any(output.output_type == "intervention_decision" for output in result.outputs)
    assert any(output.output_type == "dispatch_intent" for output in result.outputs)


def test_tick_falls_back_to_minimum_fairness_chain_when_projection_is_stubbed() -> None:
    runtime = SimingRuntime(storyline_projection=StubProjection())

    result = runtime.tick(
        [SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())]
    )

    assert result.read_model is not None
    assert result.read_model.narrative_surface["projection_status"] == "fresh"
    assert any(audit.status == "recorded" for audit in result.audit_records)


def test_no_action_still_has_audit_checkpoint_and_read_model() -> None:
    runtime = SimingRuntime()
    event = make_visual_fact_event(
        event_type="world_fact_event",
        payload_overrides={"fact_type": "unrelated", "established_fact_id": None},
    )

    result = runtime.tick([SimingInput(input_type="world_fact_event", source_event=event)])

    assert any(output.output_type == "no_action" for output in result.outputs)
    assert any(audit.status == "no_action" for audit in result.audit_records)
    assert result.checkpoints
    assert result.read_model is not None


def test_fact_veto_returns_no_action_audit_and_no_runtime_finalize() -> None:
    runtime = SimingRuntime()
    event = make_visual_fact_event(payload_overrides={"locked_fact_conflict": True})

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=event)])

    assert any(output.output_type == "no_action" for output in result.outputs)
    assert any(audit.reason == "fact_veto:locked_fact_conflict" for audit in result.audit_records)
    assert result.checkpoints == []
    assert result.read_model is None
