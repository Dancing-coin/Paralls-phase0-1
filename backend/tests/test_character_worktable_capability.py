"""Worktable candidates use the registered procedural capability taxonomy."""
import pytest

from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.skills.catalog import create_runtime_skill_registry
from app.character_agent.skills.service import CharacterSkillService
from app.models.character_agent_runtime import CharacterInterpretation, CharacterPrivateWorldSnapshot
from app.services.esm_service import ESMService


@pytest.mark.parametrize("procedural", [True, False])
def test_worktable_candidate_admission_uses_real_stable_capability(procedural):
    service = CharacterSkillService(registry=create_runtime_skill_registry())
    profile = {"capability_constraint_layer": {
        "skills": ["observation", *(["procedural recall"] if procedural else [])]}}
    stable = service.compile_stable_snapshot(actor_id="char_a",
        skill_states=service.initial_skill_states(actor_id="char_a", profile=profile))
    snapshot = CharacterPrivateWorldSnapshot(actor_id="char_a", room_id="r", scene_id="s", zone_id="z",
        producer_ts=1, updated_at=1, visible_target_refs=["obj_worktable"])
    snapshot.target_catalog = ESMService().project_character_targets(snapshot)
    interpretation = CharacterInterpretation(actor_id="char_a", interpreted_summary="visible worktable",
        interpretation_type="object", salience_score=0.5, ambiguity_level="low", risk_level="low",
        opportunity_level="medium", attention_target="obj_worktable")
    prepared = CharacterAgentL3Service().prepare_intent_plan(interpretation=interpretation,
        control_mode="agent_full_auto", profile=profile, snapshot=snapshot.model_dump(mode="json"),
        skill_affordance_summary={"stable_ability_snapshot": stable.model_dump(mode="json")})

    assert ("use_object:obj_worktable" in prepared.candidate_mapping) is procedural
    assert "finish_use:obj_worktable" not in prepared.candidate_mapping
    if procedural:
        selected = prepared.candidate_mapping["use_object:obj_worktable"]
        assert selected["action_family"] == "procedure"
        assert selected["target_refs"] == {"object": "obj_worktable"}
        assert selected["source_refs"]
        assert selected["revision_pins"]["target_admission_digest"]
        assert selected["semantic_action_id"] == "action:use"
        assert "use registered object" in selected["description"]
