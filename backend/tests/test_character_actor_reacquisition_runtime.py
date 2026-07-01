from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_boundary_spec_locks_focus_reacquisition_fairness() -> None:
    spec_text = (
        ROOT
        / "docs"
        / "superpowers"
        / "specs"
        / "2026-06-12-character-actor-runtime-boundary-design.md"
    ).read_text(encoding="utf-8")

    assert "FocusState" in spec_text
    assert "target_id is a request, not authority" in spec_text
    for reason in {
        "target_not_visible",
        "target_out_of_range",
        "target_unreachable",
        "target_not_perceived",
    }:
        assert reason in spec_text


def test_character_actor_emits_reacquisition_lifecycle_status() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    bus_source = (ROOT / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(
        encoding="utf-8"
    )
    bridge_source = (ROOT / "scripts" / "autoload" / "BackendBridge.gd").read_text(
        encoding="utf-8"
    )

    assert "Agent target_id is a request, not authority." in replica_source
    assert "func _emit_character_actor_status(" in replica_source
    assert "func _resolve_embodied_target_failure_reason(" in replica_source
    assert "signal character_actor_status_emitted(payload)" in bus_source
    assert '"character_actor_status"' in bridge_source

    for status in {
        "accepted_by_actor_adapter",
        "recovering_approach",
        "recovering_turn",
        "embodied_target_not_visible",
        "embodied_out_of_range",
        "submitted_to_authority",
        "failed",
    }:
        assert status in replica_source

    for reason in {
        "target_not_visible",
        "target_out_of_range",
        "target_unreachable",
        "target_not_perceived",
    }:
        assert reason in replica_source


def test_character_actor_embodied_gates_are_not_unconditional_placeholders() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert "PhysicsRayQueryParameters3D.create" in replica_source
    assert "intersect_ray" in replica_source
    assert "is_inside_tree()" in replica_source
    assert "func _has_line_of_sight_to_target(_target_node: Node3D) -> bool:\n\treturn true" not in replica_source
    assert "func _is_target_reachable(_target_node: Node3D) -> bool:\n\treturn true" not in replica_source


def test_character_replica_wires_actor_perception_sampler() -> None:
    source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(encoding="utf-8")

    assert "ActorPerceptionSampler" in source
    assert "_sample_actor_local_perception" in source
