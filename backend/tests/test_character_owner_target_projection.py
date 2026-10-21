"""Real private L1 input reaches the existing owner-scoped candidate compiler."""

import pytest

from app.character_agent.cognition.capability_envelope import CapabilityEnvelope
from app.character_agent.cognition.cognition_policy import CognitionPolicy
from app.character_agent.planning.l3_planner import CandidateCompiler, CharacterAgentL3Service
from app.character_agent.reasoning.l1_perception import CharacterAgentL1Service
from app.models.character_agent_runtime import CharacterInterpretation, CharacterPrivateWorldSnapshot
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.esm_service import ESMService


def _event(**updates):
    values = dict(actor_id="char_a", percept_channel="visual", producer_ts=200,
                  room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                  perceived_summary="a visible registered object", target_object_id="obj_letter",
                  source_candidate_event_id="perceived:letter:200")
    values.update(updates)
    return CharacterPerceivedEvent(**values)


def _compile(snapshot, *, skill_affordance_summary=None):
    envelope = CapabilityEnvelope.compile(actor_id=snapshot.actor_id, turn_id="turn:targets")
    policy = CognitionPolicy.resolve(envelope=envelope)
    records = CharacterAgentL3Service()._candidate_records(
        intents=["inspect_object", "short_punch", "speak_private"],
        interpretation=CharacterInterpretation(
            actor_id=snapshot.actor_id, interpreted_summary="visible object",
            interpretation_type="observation", salience_score=0.5, ambiguity_level="low",
            risk_level="low", opportunity_level="low"),
        snapshot=snapshot.model_dump(mode="json"), envelope=envelope, policy=policy,
        frame=None, skill_affordance_summary=skill_affordance_summary or {},
    )
    return CandidateCompiler().compile(candidates=records, envelope=envelope, policy=policy,
                                       visible_targets=snapshot.visible_target_refs)


def test_received_visual_target_reaches_typed_snapshot_and_action_specific_candidates():
    owner = ESMService()
    l1 = CharacterAgentL1Service(target_catalog_resolver=owner.project_character_targets)
    snapshot = l1.apply_character_perceived_event(_event())
    restored = CharacterPrivateWorldSnapshot.model_validate_json(snapshot.model_dump_json())
    assert restored.visible_target_refs == ["obj_letter"]
    assert restored.visible_target_sources == {"obj_letter": ["perceived:letter:200"]}
    descriptor, = restored.target_catalog
    assert descriptor["owner_route"] == "esm.interaction"
    assert descriptor["supported_intents"] == ["inspect_object"]
    assert "perceived:letter:200" in descriptor["target_provenance"]
    result = _compile(restored)
    assert result.wire_labels == ["inspect_object:obj_letter"]
    assert result.presented[0]["revision_pins"]["target_admission_digest"].startswith("sha256:")
    assert result.presented[0]["execution_contract"]["revision_pins"]["target_admission_digest"] == descriptor["target_admission_digest"]
    # Visibility and attention do not grant unrelated action families.  The
    # owner catalog is action-specific, so unsupported actions are rejected
    # rather than retained as diagnostic candidates.
    assert all(row["candidate_id"] not in {
        "short_punch:obj_letter", "speak_private:obj_letter"
    } for row in result.diagnostics)


def test_no_resolver_unknown_target_and_auditory_target_grant_no_action():
    plain = CharacterAgentL1Service().apply_character_perceived_event(_event())
    assert plain.target_catalog == []
    owner = ESMService()
    l1 = CharacterAgentL1Service(target_catalog_resolver=owner.project_character_targets)
    unknown = l1.apply_character_perceived_event(_event(target_object_id="obj_unregistered"))
    assert unknown.target_catalog == []
    heard = l1.apply_character_perceived_event(_event(percept_channel="auditory"))
    assert "obj_letter" not in heard.visible_target_refs
    assert _compile(heard).presented == []
    assert l1.get_snapshot("char_b") is None


def test_latest_visual_slice_and_scope_change_do_not_retain_old_target_permission():
    owner = ESMService()
    l1 = CharacterAgentL1Service(target_catalog_resolver=owner.project_character_targets)
    l1.apply_character_perceived_event(_event())
    empty = l1.apply_character_perceived_event(_event(target_object_id="", producer_ts=201))
    assert empty.visible_target_refs == [] and empty.target_catalog == []
    l1.apply_character_perceived_event(_event(producer_ts=202))
    other = l1.apply_character_perceived_event(_event(
        scene_id="scene_elsewhere", percept_channel="auditory", producer_ts=203))
    assert other.scene_id == "scene_elsewhere"
    assert other.visible_target_refs == [] and other.target_catalog == []


def test_explicit_empty_visibility_never_admits_a_targeted_candidate():
    record = dict(candidate_id="inspect:letter", action_family="observation",
                  target_refs={"target": "obj_letter"}, required_conditions={"visibility": "satisfied"})
    result = CandidateCompiler().compile(candidates=[record], visible_targets=[])
    assert result.presented == []
    assert result.diagnostics[0]["reason"] == "target_not_visible"


def test_siming_freeze_refreshes_esm_state_without_inventing_visibility_or_mutating_l1():
    owner = ESMService()
    l1 = CharacterAgentL1Service(target_catalog_resolver=owner.project_character_targets)
    original = l1.apply_character_perceived_event(_event())
    old_digest = original.target_catalog[0]["target_admission_digest"]
    owner.commit_interaction_state(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                                   target_object_id="obj_letter", current_state="visible", actor_id="char_a")
    frozen = l1.plan_siming_output(dict(target_actor_id="char_a", target_object_id="obj_archive_door",
                                      room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                                      producer_ts=210))
    assert frozen.visible_target_refs == ["obj_letter"]
    assert frozen.target_catalog[0]["target_admission_digest"] != old_digest
    assert _compile(frozen).presented == []
    assert original.target_catalog[0]["target_admission_digest"] == old_digest


def test_durable_siming_scope_change_does_not_copy_previous_scene_visibility():
    owner = ESMService()
    l1 = CharacterAgentL1Service(target_catalog_resolver=owner.project_character_targets)
    original = l1.apply_character_perceived_event(_event())
    frozen = l1.plan_siming_output(dict(target_actor_id="char_a", room_id="room_demo",
                                      scene_id="scene_elsewhere", zone_id="zone_focus", producer_ts=210))
    assert frozen.scene_id == "scene_elsewhere"
    assert frozen.visible_target_refs == [] and frozen.target_catalog == []
    assert original.visible_target_refs == ["obj_letter"]


def test_family_affordance_can_never_restore_owner_blocked_target():
    owner = ESMService()
    l1 = CharacterAgentL1Service(target_catalog_resolver=owner.project_character_targets)
    owner.commit_interaction_state(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                                   target_object_id="obj_letter", current_state="visible")
    snapshot = l1.apply_character_perceived_event(_event())
    assert snapshot.target_catalog[0]["affordance_result"]["status"] == "blocked"
    result = _compile(snapshot, skill_affordance_summary={
        "action_affordances": {"observation": {"status": "available", "reason": "skilled"}}})
    assert result.presented == []


@pytest.mark.asyncio
async def test_real_backend_factory_injects_its_existing_esm_owner(tmp_path, monkeypatch):
    import asyncio
    from app import main

    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(tmp_path / "world.sqlite3"))
    monkeypatch.setattr(main.settings, "character_model_provider_kind", "local")
    monkeypatch.setattr(main.settings, "siming_llm_mode", "disabled")
    idle = asyncio.Event()

    async def pause(_):
        idle.set()
        await asyncio.Future()

    monkeypatch.setattr(main, "_population_runtime_sleep", pause)
    owners = []
    for _ in range(2):
        try:
            idle.clear()
            await main._start_population_runtime_on_startup()
            await asyncio.wait_for(idle.wait(), 5)

            def observe():
                owners.append(main.esm_service)
                l1 = main.character_agent_runtime._l1
                resolver = l1._target_catalog_resolver
                assert resolver.__self__ is main.character_object_execution
                assert resolver.__self__._owner is main.esm_service
                snapshot = l1.apply_character_perceived_event(_event()).model_copy(deep=True)
                main.esm_service.commit_interaction_state(
                    room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                    target_object_id="obj_letter", current_state="visible")
                updated = l1.plan_siming_output(dict(target_actor_id="char_a", producer_ts=210))
                return snapshot, updated

            snapshot, updated = await asyncio.wrap_future(main.runtime_execution.submit(observe))
            assert snapshot.target_catalog[0]["required_conditions"]["range"] == "unknown"
            assert _compile(snapshot).presented == []
            assert snapshot.target_catalog[0]["affordance_result"]["status"] == "available"
            assert updated.target_catalog[0]["affordance_result"]["status"] == "blocked"
            assert updated.target_catalog[0]["target_admission_digest"] != snapshot.target_catalog[0]["target_admission_digest"]
            assert _compile(updated).presented == []
        finally:
            await main._stop_population_runtime_on_shutdown()
    assert owners[0] is not owners[1]
