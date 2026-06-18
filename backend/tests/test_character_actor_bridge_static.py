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
    assert 'character_agent_output_received.connect(_on_character_agent_output_received)' not in replica_source
    assert 'func _on_character_agent_output_received(payload: Dictionary) -> void:' not in replica_source


def test_backend_bridge_and_replica_accept_actor_execution_ingress_payload() -> None:
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

    assert 'signal character_agent_execution_received(payload)' in bus_source
    assert '"character_agent_execution":' in bridge_source
    assert '_bus_emit("character_agent_execution_received", [payload])' in bridge_source
    assert 'character_agent_execution_received.connect(_on_character_agent_execution_received)' in replica_source
    assert 'func _on_character_agent_execution_received(payload: Dictionary) -> void:' in replica_source
    assert 'runtime_state.get_execution_payload_intent_frame(payload, actor_id)' in replica_source
    assert 'actor_control_frames' in (project_root / "scripts" / "character" / "CharacterRuntimeState.gd").read_text(
        encoding="utf-8"
    )
    assert 'presentation_plan' in replica_source


def test_character_replica_execution_handler_preserves_payload_string_values() -> None:
    project_root = Path(__file__).resolve().parents[2]
    replica_source = (project_root / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert 'str(frame.get("target_ref", "") or "")' not in replica_source
    assert 'str(presentation_plan.get("expression_hint", "") or "")' not in replica_source
    assert 'str(presentation_plan.get("physiology_hint", "") or "")' not in replica_source
    assert 'str(payload.get("command_type", "idle") or "idle")' not in replica_source


def test_local_presentation_bus_exposes_explicit_debug_logging_toggle() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bus_source = (project_root / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(
        encoding="utf-8"
    )

    assert 'OS.get_environment("PHASE0_AUTOTEST") == "1"' in bus_source
    assert 'OS.get_environment("PHASE0_FOCUS_AUTOTEST") == "1"' in bus_source
    assert 'OS.get_environment("PHASE0_DEBUG_LOGGING") == "1"' in bus_source
    assert "var debug_logging_enabled := false" in bus_source
    assert "func set_debug_logging_enabled(enabled: bool) -> void:" in bus_source
    assert "func is_debug_logging_enabled() -> bool:" in bus_source
    assert "if not debug_logging_enabled:" in bus_source
    assert "func _apply_debug_logging_mode() -> void:" in bus_source
    assert "set_process_input(debug_logging_enabled)" in bus_source
    assert "set_process_unhandled_input(debug_logging_enabled)" in bus_source


def test_main_execution_envelope_builder_does_not_inline_legacy_reconstruction() -> None:
    project_root = Path(__file__).resolve().parents[2]
    main_source = (project_root / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    builder_slice = main_source.split("def _as_character_agent_execution_envelopes(", 1)[1].split(
        "def _as_character_agent_action_request_envelopes(", 1
    )[0]

    assert "CharacterPrivateWorldSnapshot(" not in builder_slice
    assert "CharacterInterpretation(" not in builder_slice
    assert "CharacterIntentDecision(" not in builder_slice
