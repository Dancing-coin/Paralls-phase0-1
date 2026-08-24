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
    assert '[node name="SimingHeavenlyRuntimeProbe" type="Node" parent="."]' in scene


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
    assert "var source_ref_lineage: Array[String]" in probe
    assert "siming_heavenly_restart_ready" in probe
    assert "siming_heavenly_godot_complete" in probe
    assert "_post_restart_reaction_window" in probe


def test_probe_waits_for_backend_reconnect_before_triggering_the_post_restart_tick() -> None:
    probe = Path("scripts/verification/SimingHeavenlyRuntimeProbe.gd").read_text(
        encoding="utf-8"
    )

    assert "backend_connected.connect(_on_backend_connected)" in probe
    assert 'Callable(self, "_backend_reconnected")' in probe
    assert '_controller._emit_dialogue_request("char_b", "The letter is gone.")' in probe


def test_probe_marks_restart_only_after_staging_request_is_observed() -> None:
    probe = Path("scripts/verification/SimingHeavenlyRuntimeProbe.gd").read_text(
        encoding="utf-8"
    )
    run = probe.split("func _run() -> void:", 1)[1].split("func _backend_ready", 1)[0]

    assert run.index('Callable(self, "_has_staging_request")') < run.index(
        'print("siming_heavenly_restart_ready")'
    )


def test_character_perception_forward_matches_godot_negative_z_front() -> None:
    source = Path("scripts/character/CharacterReplica.gd").read_text(encoding="utf-8")

    forward_helper = source.split("func get_embodied_forward_vector() -> Vector3:", 1)[1].split(
        "\nfunc ", 1
    )[0]
    assert "return -global_basis.z.normalized()" in forward_helper


def test_headless_autotest_capture_advances_a_scene_frame() -> None:
    source = Path("scripts/phase0/MainDemoController.gd").read_text(encoding="utf-8")

    capture_helper = source.split("func _capture_autotest_screenshot", 1)[1].split(
        "\nfunc ", 1
    )[0]
    assert "await get_tree().process_frame" in capture_helper


def test_heavenly_probe_syncs_player_to_authoritative_interaction_range() -> None:
    probe = Path("scripts/verification/SimingHeavenlyRuntimeProbe.gd").read_text(
        encoding="utf-8"
    )

    assert "_move_player_to_interact_position()" in probe
    assert "_emit_move_intent_request" in probe
    assert "_move_request_acknowledged" in probe
    assert "suspend_near_object_visual_fact = true" in probe
    assert "suspend_spatial_access_fact = true" in probe


def test_heavenly_probe_allows_online_decision_latency() -> None:
    probe = Path("scripts/verification/SimingHeavenlyRuntimeProbe.gd").read_text(
        encoding="utf-8"
    )

    assert "RUNTIME_EVENT_TIMEOUT_MS := 180000" in probe
    assert '"_destruction_applied"), RUNTIME_EVENT_TIMEOUT_MS' in probe


def test_heavenly_probe_requires_authoritative_destruction_and_one_matched_reaction() -> None:
    bridge = Path("scripts/interaction/DefaultSceneLetterAffordanceBridge.gd").read_text(
        encoding="utf-8"
    )
    probe = Path("scripts/verification/SimingHeavenlyRuntimeProbe.gd").read_text(
        encoding="utf-8"
    )
    affordance_probe = Path("scripts/verification/DefaultSceneLetterAffordanceProbe.gd").read_text(
        encoding="utf-8"
    )

    assert 'PackedStringArray(["inspect", "read", "destroy"])' in bridge
    assert '"destroy"' in affordance_probe
    assert "letter_destroy_resolution" in affordance_probe
    assert "_destroyed = true" in probe
    assert "_char_b_reaction_count == 1" in probe
    assert "_staging_correlation_id()" in probe
    assert "VLAReplayCoverageCaptureProbe.gd" in probe
    assert "checker._has_meaningful_pixels(image)" in probe
    assert "_has_meaningful_pixels" in probe


def test_heavenly_probe_binds_the_explicit_observation_to_char_b() -> None:
    probe = Path("scripts/verification/SimingHeavenlyRuntimeProbe.gd").read_text(
        encoding="utf-8"
    )

    observation = probe.split("func _emit_char_b_observation() -> void:", 1)[1].split(
        "\nfunc _send_staging_ack", 1
    )[0]

    assert 'emitter.set("actor_id", "char_b")' in observation
    assert "_destruction_correlation_id" in observation
