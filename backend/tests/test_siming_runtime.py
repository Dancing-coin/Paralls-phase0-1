from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingInput
from app.services.siming_runtime import SimingRuntime

from tests.test_authority_event import valid_event_dict


def make_input(event_type: str, payload_override: dict[str, object] | None = None) -> SimingInput:
    payload = valid_event_dict()
    payload["event_type"] = event_type
    payload["payload"] = payload_override or payload["payload"]
    event = AuthorityEvent.model_validate(payload)
    return SimingInput(input_type=event_type, source_event=event)


def test_runtime_emits_fairness_snapshot_for_consumed_event() -> None:
    runtime = SimingRuntime()

    result = runtime.tick([make_input("visual_fact_event")])

    assert result.outputs[0].output_type == "fairness_snapshot"
    assert result.outputs[0].causation_id == "evt_visual_1"


def test_runtime_emits_visual_observability_dispatch_for_light_drop() -> None:
    runtime = SimingRuntime()

    result = runtime.tick([make_input("visual_fact_event")])

    dispatches = [output for output in result.outputs if output.output_type == "dispatch_intent"]
    assert len(dispatches) == 1
    assert dispatches[0].selected_path == "visual_fact_path"
    assert dispatches[0].intervention_band == "fact_reveal"
    assert dispatches[0].payload["established_fact_id"] == "evt_visual_1"


def test_runtime_records_no_action_for_irrelevant_visual_fact() -> None:
    runtime = SimingRuntime()

    result = runtime.tick(
        [
            make_input(
                "visual_fact_event",
                {
                    "fact_type": "fixed_gaze_on_target",
                    "target_actor_id": "char_a",
                },
            )
        ]
    )

    assert [output.output_type for output in result.outputs] == ["fairness_snapshot", "no_action"]
    assert result.audit_records[0].status == "no_action"
    assert result.audit_records[0].reason == "no eligible intervention"


def test_runtime_records_esm_rejection_for_constraint_state_event() -> None:
    runtime = SimingRuntime()

    result = runtime.tick(
        [
            make_input(
                "constraint_state_event",
                {
                    "result_type": "constraint_state_result",
                    "constraint_type": "distance",
                    "constraint_summary": "target is too far away",
                },
            )
        ]
    )

    assert result.audit_records[0].status == "esm_rejected"
    assert result.audit_records[0].reason == "target is too far away"
