"""Private target input is produced by the current backend ESM instance."""

import asyncio

import pytest

from app.character_agent.reasoning.l1_perception import CharacterAgentL1Service
from app.models.character_agent_runtime import CharacterPrivateWorldSnapshot
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.esm_service import ESMService


def _event(**updates):
    values = dict(actor_id="char_a", percept_channel="visual", producer_ts=200,
                  room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                  perceived_summary="visible object", target_object_id="obj_letter",
                  source_candidate_event_id="perceived:letter:200")
    return CharacterPerceivedEvent(**dict(values, **updates))


def test_private_catalog_roundtrip_preserves_explicit_visibility_and_owner_source():
    owner = ESMService()
    l1 = CharacterAgentL1Service(target_catalog_resolver=owner.project_character_targets)
    snapshot = l1.apply_character_perceived_event(_event())
    restored = CharacterPrivateWorldSnapshot.model_validate_json(snapshot.model_dump_json())
    assert restored.visible_target_refs == ["obj_letter"]
    descriptor, = restored.target_catalog
    assert descriptor["supported_intents"] == ["inspect_object"]
    assert descriptor["owner_route"] == "esm.interaction"
    assert descriptor["target_provenance"] == ["perceived:letter:200"]
    assert descriptor["target_admission_digest"].startswith("sha256:")
    assert l1.get_snapshot("char_b") is None
    frozen = l1.plan_siming_output(dict(target_actor_id="char_a", scene_id="another_scene"))
    assert frozen.visible_target_refs == [] and frozen.target_catalog == []
    assert snapshot.visible_target_refs == ["obj_letter"]


def test_unobserved_or_unknown_target_has_no_esm_permission():
    owner = ESMService()
    l1 = CharacterAgentL1Service(target_catalog_resolver=owner.project_character_targets)
    assert l1.apply_character_perceived_event(_event(percept_channel="auditory")).target_catalog == []
    assert l1.apply_character_perceived_event(_event(target_object_id="obj_unknown")).target_catalog == []
    assert CharacterAgentL1Service().apply_character_perceived_event(_event()).target_catalog == []


def test_worktable_catalog_projects_use_and_finish_use_as_distinct_stateful_actions():
    owner = ESMService()
    snapshot = CharacterPrivateWorldSnapshot(actor_id="char_a", room_id="r", scene_id="s", zone_id="z",
        producer_ts=1, updated_at=1, visible_target_refs=["obj_worktable"])

    ready = {item["supported_intents"][0]: item for item in owner.project_character_targets(snapshot)}
    assert set(ready) == {"use_object", "finish_use"}
    assert ready["use_object"]["affordance_result"]["status"] == "available"
    assert ready["finish_use"]["affordance_result"]["status"] == "blocked"
    assert ready["use_object"]["target_admission_digest"].startswith("sha256:")

    owner.commit_interaction_state(room_id="r", scene_id="s", zone_id="z",
        target_object_id="obj_worktable", current_state="engaged")
    engaged = {item["supported_intents"][0]: item for item in owner.project_character_targets(snapshot)}
    assert set(engaged) == {"use_object", "finish_use"}
    assert engaged["use_object"]["affordance_result"]["status"] == "blocked"
    assert engaged["finish_use"]["affordance_result"]["status"] == "available"
    assert engaged["finish_use"]["target_admission_digest"] != ready["use_object"]["target_admission_digest"]


@pytest.mark.asyncio
async def test_backend_restarts_bind_new_owner_and_refresh_its_state(tmp_path, monkeypatch):
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
                assert l1._target_catalog_resolver.__self__ is main.character_object_execution
                assert main.character_object_execution._owner is main.esm_service
                assert main.character_object_execution._source is main.embodied_spatial_source
                first = l1.apply_character_perceived_event(_event()).model_copy(deep=True)
                main.esm_service.commit_interaction_state(
                    room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                    target_object_id="obj_letter", current_state="visible")
                after = l1.plan_siming_output(dict(target_actor_id="char_a", producer_ts=210))
                assert first.target_catalog[0]["affordance_result"]["status"] == "available"
                assert after.target_catalog[0]["affordance_result"]["status"] == "blocked"
                assert first.target_catalog[0]["target_admission_digest"] != after.target_catalog[0]["target_admission_digest"]

            await asyncio.wrap_future(main.runtime_execution.submit(observe))
        finally:
            await main._stop_population_runtime_on_shutdown()
    assert owners[0] is not owners[1]
