from pathlib import Path


def test_removed_letter_hides_visual_label_and_collision() -> None:
    source = Path("scripts/object/InteractiveObject.gd").read_text(encoding="utf-8")

    assert 'current_state == "removed_from_surface"' in source
    assert "visual_root.visible = not removed" in source
    assert "label_3d.visible = not removed" in source
    assert "collision_shape.disabled = removed" in source


def test_main_demo_contains_heavenly_runtime_probe() -> None:
    scene = Path("scenes/phase0/MainDemo.tscn").read_text(encoding="utf-8")

    assert "SimingHeavenlyRuntimeProbe.gd" in scene


def test_staging_request_reaches_the_opt_in_godot_probe() -> None:
    bridge = Path("scripts/autoload/BackendBridge.gd").read_text(encoding="utf-8")
    bus = Path("scripts/autoload/LocalPresentationBus.gd").read_text(encoding="utf-8")
    probe = Path("scripts/verification/SimingHeavenlyRuntimeProbe.gd").read_text(
        encoding="utf-8"
    )

    assert '"siming.staging_request"' in bridge
    assert "siming_staging_requested" in bridge
    assert "signal siming_staging_requested(payload)" in bus
    assert 'SIMING_HEAVENLY_AUTOTEST") == "1"' in probe
    assert "siming-heavenly-before-destruction.png" in probe
    assert "siming-heavenly-after-destruction.png" in probe
    assert "siming-heavenly-char-b-reaction.png" in probe
    assert "character_agent_execution_received" in probe
    assert "_char_b_reacted" in probe
    assert "actor_observes_object_removal" in probe
    assert "source_ref_lineage" in probe
    assert "siming_heavenly_restart_ready" in probe
    assert "siming_heavenly_godot_complete" in probe


def test_probe_waits_for_backend_reconnect_before_triggering_the_post_restart_tick() -> None:
    probe = Path("scripts/verification/SimingHeavenlyRuntimeProbe.gd").read_text(
        encoding="utf-8"
    )

    assert "backend_connected.connect(_on_backend_connected)" in probe
    assert 'Callable(self, "_backend_reconnected")' in probe
    assert '_controller._emit_dialogue_request("char_b", "The letter is gone.")' in probe
