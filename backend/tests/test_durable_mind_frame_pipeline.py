"""Actual durable cognition carries the original bounded frame across restart."""
import json

import pytest

from app.character_agent.models.mind_frame import CharacterMindFrame
from app.character_agent.models.turn_context import CharacterTurnContext
from test_character_cognition_coordinator import setup
from test_durable_cognition_shared_contract import _pending


@pytest.mark.parametrize("background", [False, True])
def test_original_l2_frame_reaches_l3_after_provider_pending_restart(tmp_path, monkeypatch, background):
    rt, _, _, child, _, pending = _pending(tmp_path, background=background)
    try:
        original = json.loads(pending.request_json)["context"]["frame"]
        frozen = rt._cognition_frame_value(pending.frame, "context")
        assert frozen["mind_frame"] == original
        CharacterMindFrame.model_validate(original).validate_turn(
            CharacterTurnContext.model_validate(frozen["turn_context"]))
    finally:
        rt.close()
    rt, _, coordinator, _, handle = setup(tmp_path)
    try:
        if background:
            rt.set_background_cognition_enabled(True)
            rt.set_background_mode("char_a", "active")
            rt._refresh_weak_supervision_state(
                actor_id="char_a", producer_ts=9999, reason_summary="background enabled")
        from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
        monkeypatch.setattr(CharacterMindFrameBuilder, "build_frame",
            lambda **_: pytest.fail("restart must not rebuild the original frame"))
        restored = coordinator.prepare_l2(child.child_key, activation=handle, now=113.)
        assert restored.request_json == pending.request_json
        coordinator.accept_l2(child.child_key, activation=handle, now=114., output={
            "interpreted_summary": "unexpected pressure", "interpretation_type": "observation",
            "ambiguity_level": "high", "risk_level": "high", "salience_score": .9,
        })
        coordinator.freeze_l2(child.child_key, activation=handle, now=115.)
        coordinator.resume_l2(child.child_key, activation=handle, now=116.)
        l3 = coordinator.prepare_l3(child.child_key, activation=handle, now=117.)
        prepared = rt._cognition_frame_value(l3.frame, "l3_prepared")
        wire = json.loads(prepared["prepared"]["request_json"])
        assert wire["context"]["frame"] == original
        for candidate in prepared["prepared"]["candidate_mapping"].values():
            assert candidate["frame_ref"] == original["frame_digest"]
            assert candidate["execution_contract"]["revision_pins"]["frame_digest"] == original["frame_digest"]
        changed = dict(original, producer_ts=original["producer_ts"] + 1)
        context = dict(frozen, mind_frame=changed)
        from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
        from app.models.character_agent_runtime import CharacterInterpretation
        monkeypatch.setattr(rt._l3._gateway, "prepare_run_request",
            lambda **_: pytest.fail("changed frame reached provider"))
        with pytest.raises(ValueError, match="mind frame"):
            rt._prepare_siming_l3_request("char_a",
                CharacterPrivateWorldSnapshot.model_validate(l3.frame["entry_after"]["private_snapshot"]),
                CharacterInterpretation.model_validate(l3.frame["interpretation"]), context)
    finally:
        rt.close()


def test_l2_frame_projects_only_memory_selected_by_existing_recall():
    from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
    from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
    from app.character_agent.services.character_semantic_recall import SemanticRecallResult
    from test_mind_frame_turn_boundary import turn

    class BoundedRecall:
        def select(self, actor_id, context, *, turn_context):
            assert "excluded-secret-memory" in json.dumps(context["memory"])
            return SemanticRecallResult(memory={"event_memories": [
                {"memory_id": "selected-evidence", "summary": "selected visible evidence"}]})

    service = CharacterAgentL2Service(semantic_recall_service=BoundedRecall())
    request = service.prepare_reasoning_request(
        snapshot=CharacterPrivateWorldSnapshot(actor_id="char_a", room_id="room", scene_id="scene",
            zone_id="zone", producer_ts=10, updated_at=10), event={}, turn_context=turn(),
        memory_bundle={"event_memories": [
            {"memory_id": "excluded-secret-memory", "summary": "must not reappear"}]})
    context = request["context"]
    frame = context["frame"]
    assert "selected-evidence" in json.dumps(frame)
    assert "excluded-secret-memory" not in json.dumps(frame)
    assert "must not reappear" not in json.dumps(frame)
    CharacterMindFrame.model_validate(frame).validate_turn(turn())
