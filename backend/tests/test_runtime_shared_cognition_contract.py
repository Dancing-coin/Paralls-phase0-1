from copy import deepcopy

import pytest

from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from test_character_agent_l2_reasoning import _LocalGateway


@pytest.mark.parametrize("source", ["perceived", "self_body", "siming", "background"])
def test_entry_l2_and_l3_share_pre_interpretation_contract(tmp_path, monkeypatch, source):
    class Gateway(_LocalGateway):
        def __init__(self):
            super().__init__()
            self.contexts = []

        def prepare_run_request(self, *, task_kind, context, **kwargs):
            self.contexts.append((task_kind, deepcopy(context)))
            return super().prepare_run_request(task_kind=task_kind, context=context, **kwargs)

    gateway = Gateway()
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    runtime._l2 = CharacterAgentL2Service(gateway=gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=gateway)
    compiled = []
    compile_stable = runtime._skill_service.compile_stable_snapshot

    def record_compile(**kwargs):
        compiled.append(kwargs)
        return compile_stable(**kwargs)

    monkeypatch.setattr(runtime._skill_service, "compile_stable_snapshot", record_compile)
    def reject_fallback(**kwargs):
        raise kwargs["error"]

    monkeypatch.setattr(runtime, "_continuity_floor_decision", reject_fallback)
    try:
        common = dict(actor_id="char_b", producer_ts=320, room_id="room_demo",
                      scene_id="scene_demo", zone_id="zone_focus")
        if source == "perceived":
            runtime.ingest_character_perceived_event(CharacterPerceivedEvent(
                **common, percept_channel="visual", perceived_summary="A door is open",
                source_candidate_event_id="evt:door:320"))
        elif source == "self_body":
            runtime.ingest_self_body_perceived_event(SelfBodyPerceivedEvent(
                **common, body_state_class="interaction_strain", perceived_summary="engaged",
                source_body_result_id="body:320"))
        else:
            runtime.ingest_siming_output(dict(
                common, target_actor_id="char_b", message_id="siming:320",
                delivery_id="delivery:320", input_type="siming_high_level_message", band="fact_reveal",
                causation_id="siming:320", correlation_id="siming:320", presentation_hint="Notice the door"))
            if source == "background":
                gateway.contexts.clear()
                compiled.clear()
                runtime.set_background_cognition_enabled(True)
                runtime.set_background_mode("char_b", "active")
                runtime._refresh_weak_supervision_state(
                    actor_id="char_b", producer_ts=9999, reason_summary="background enabled")
                assert runtime.run_background_cognition_tick(actor_id="char_b", producer_ts=10000).ran
        l2 = next(context for kind, context in gateway.contexts if kind == "l2_reasoning")
        l3 = next(context for kind, context in gateway.contexts if kind == "l3_planning")
        assert "capability_envelope" in l2
        assert l2["capability_envelope"] == l3["capability_envelope"]
        assert l2["cognition_policy"] == l3["cognition_policy"]
        assert l2["turn_id"] == l2["capability_envelope"]["turn_id"]
        assert len(compiled) == 1
        assert l2["frame"] == l3["frame"]
        assert l2["frame"]["turn_id"] == l2["turn_id"]
        assert l2["frame"]["frame_digest"]

    finally:
        runtime.close()
