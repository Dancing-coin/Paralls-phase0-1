from pathlib import Path


def test_backend_bridge_exposes_character_agent_output_signal_chain() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bus_source = (project_root / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(
        encoding="utf-8"
    )
    bridge_source = (project_root / "scripts" / "autoload" / "BackendBridge.gd").read_text(
        encoding="utf-8"
    )
    replica_source = (project_root / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert 'signal character_agent_output_received(payload)' in bus_source
    assert '"character_agent_output":' in bridge_source
    assert '_bus_emit("character_agent_output_received", [payload])' in bridge_source
    assert 'func _on_character_agent_output_received(payload: Dictionary) -> void:' in replica_source
    assert 'command_type' in replica_source
