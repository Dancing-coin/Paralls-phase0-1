from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_character_agent_execution_probe_scene_exists_and_uses_main_demo() -> None:
    scene_text = (ROOT / "scenes" / "phase0" / "CharacterAgentExecutionProbe.tscn").read_text(
        encoding="utf-8"
    )

    assert 'path="res://scenes/phase0/MainDemo.tscn"' in scene_text
    assert '[node name="CharacterAgentExecutionProbe" type="Node"]' in scene_text


def test_character_agent_execution_probe_script_targets_execution_contract() -> None:
    script_text = (
        ROOT / "scripts" / "verification" / "CharacterAgentExecutionProbe.gd"
    ).read_text(encoding="utf-8")

    assert 'backend_message_type:character_agent_execution' in script_text
    assert '"controller_source":"agent"' in script_text
    assert '"control_mode":"agent_controlled"' in script_text
    assert '"focus_state":{' in script_text
    assert '"action_state":{' in script_text
    assert '"speech_state":{' in script_text
    assert '_observed_execution_actor_id = actor_id_value' in script_text
    assert 'var raw_prefix := "backend_message_raw:"' in script_text
    assert 'var raw_index := message.find(raw_prefix)' in script_text
    assert 'var applied_prefix := "character_agent_execution_applied:"' in script_text
    assert 'var applied_index := message.find(applied_prefix)' in script_text
    assert 'var target_actor_id := _execution_applied_actor_id' in script_text
    assert 'target_actor_id = _observed_execution_actor_id' in script_text
    assert "func _resolve_consumer_node(main_demo: Node) -> Node:" in script_text
    assert '_legacy_output_seen = true' in script_text
    assert 'CharacterA' in script_text
    assert 'character_agent_execution_applied:' in script_text
    assert 'CharacterReplica' in script_text
    assert 'get_node_or_null("MainDemo")' in script_text
    assert 'MAIN_DEMO_SCENE.instantiate()' not in script_text
    assert 'bus.set_debug_logging_enabled(true)' in script_text
    assert 'if bus.has_method("set_debug_logging_enabled"):' in script_text
    assert 'print("character_agent_execution_probe:execution_payload_direct=%s" % _execution_payload_direct)' in script_text
    assert '_execution_payload_direct = true' in script_text
    assert 'character_agent_execution_probe:consumer_node_is_character_replica=%s' in script_text


def test_l1_runtime_probe_enables_explicit_debug_logging_mode() -> None:
    script_text = (
        ROOT / "scripts" / "verification" / "L1RuntimeProbe.gd"
    ).read_text(encoding="utf-8")

    assert 'bus.set_debug_logging_enabled(true)' in script_text
    assert 'if bus.has_method("set_debug_logging_enabled"):' in script_text
    assert 'var backend_connected_ok := await _wait_for_backend_connected(10000)' in script_text
    assert 'main_demo.call("_emit_spatial_access_zone_entry")' in script_text or 'main_demo.call("_sample_privacy_boundary_fact")' in script_text
