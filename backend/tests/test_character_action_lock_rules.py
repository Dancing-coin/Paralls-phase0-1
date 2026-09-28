from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_character_actor_exposes_semantic_action_intent_admission():
    source = (ROOT / "scripts" / "character" / "CharacterActor.gd").read_text(encoding="utf-8")
    assert "func submit_action_intent(" in source
    assert "ActorActionArbiterRef.resolve" in source
    assert "semantic_action_id" in source
    assert "claims" in source


def test_street_coordinator_routes_actions_through_actor_arbiter_before_authority_attempt():
    source = (ROOT / "scripts" / "street_combat" / "StreetCombatCoordinator.gd").read_text(encoding="utf-8")
    assert "submit_action_intent" in source
    assert '"semantic_action_id": semantic_action_id' in source
    assert '"authority_route": "esm"' in source
    assert '"damage"' not in source
    assert '"hit"' not in source


def test_action_attempt_keeps_authority_projection_only_for_damage_and_recovery():
    source = (ROOT / "scripts" / "street_combat" / "StreetCombatCoordinator.gd").read_text(encoding="utf-8")
    result_source = (ROOT / "scripts" / "street_combat" / "StreetCombatCoordinator.gd").read_text(encoding="utf-8")
    assert "committed_projection" in result_source
    assert "play_recoil" in result_source
    assert "actor_hp[target_id]" in result_source
    assert "damage =" not in source
