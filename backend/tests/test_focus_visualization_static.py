from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_main_demo_exposes_focus_rule_hint_and_f11_perception_toggle() -> None:
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert "KEY_F11" in controller_source
    assert "perception_debug_enabled" in controller_source
    assert "_apply_perception_debug_visibility()" in controller_source
    assert "判定规则：距离不超过" in controller_source
    assert "按 F11 可以显示所有角色的视线锥体" in controller_source
    assert "get_focus_anchor_position" in controller_source


def test_main_demo_separates_visible_targets_from_precise_lock() -> None:
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert "var visible_focus_targets" in controller_source
    assert "var current_precise_focus_target" in controller_source
    assert "focus_precision_alignment_threshold" in controller_source
    assert "_collect_visible_focus_targets()" in controller_source
    assert "_pick_precise_focus_target(" in controller_source
    assert "screen_offset > focus_screen_center_threshold_px" not in controller_source
    assert "只有镜头真正对准目标，才会精确锁定" in controller_source
    assert "相对坐标" in controller_source
    assert "水平" in controller_source and "垂直" in controller_source


def test_main_demo_focus_chain_uses_observatory_selected_actor_as_view_origin() -> None:
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert "var observatory_view_actor_id" in controller_source
    assert "_sync_observatory_view_actor()" in controller_source
    assert "_get_observatory_state()" in controller_source
    assert "_get_view_origin_actor_node()" in controller_source
    assert "state.selected_actor_id" in controller_source
    assert "当前观察角色：" in controller_source


def test_main_demo_visible_focus_targets_require_line_of_sight() -> None:
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert "_has_focus_line_of_sight(" in controller_source
    assert "PhysicsRayQueryParameters3D.create" in controller_source
    assert "intersect_ray" in controller_source
    assert "if not _has_focus_line_of_sight(candidate):" in controller_source


def test_main_demo_focus_candidates_include_player_replica_for_other_actors() -> None:
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert "_get_focus_candidates()" in controller_source
    assert 'get_node_or_null("PlayerCharacter/CharacterReplica")' in controller_source
    assert "if candidate == view_actor:" in controller_source
    assert "if candidate == current_view_actor:" not in controller_source


def test_perception_toggle_restores_all_character_cones() -> None:
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert "actor.set_perception_debug_visible(perception_debug_enabled)" in controller_source
    assert "actor == current_focus_target" not in controller_source


def test_character_replica_has_perception_cone_debug_surface() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    scene_source = (ROOT / "scenes" / "phase0" / "CharacterReplica.tscn").read_text(
        encoding="utf-8"
    )
    debug_source = (ROOT / "scripts" / "character" / "PerceptionConeDebug.gd").read_text(
        encoding="utf-8"
    )

    assert "func set_perception_debug_visible(" in replica_source
    assert "func configure_perception_debug(" in replica_source
    assert "func get_focus_anchor_position() -> Vector3:" in replica_source
    assert '[node name="PerceptionConeDebug"' in scene_source
    assert "set_debug_visible" in debug_source
    assert "set_parameters" in debug_source


def test_character_replica_forward_vector_comes_from_replica_root_not_role_asset_scene() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert "func get_embodied_forward_vector() -> Vector3:" in replica_source
    assert "return global_basis.z.normalized()" in replica_source
    assert "role_asset_scene as Node3D" not in replica_source.split("func get_embodied_forward_vector() -> Vector3:")[1].split("func ", 1)[0]


def test_main_demo_non_player_focus_forward_uses_actor_visual_front_instead_of_negative_z() -> None:
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert "return view_actor.global_basis.z.normalized()" in controller_source
    assert "return -view_actor.global_basis.z.normalized()" not in controller_source
