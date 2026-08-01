from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_carry_place_mirror_consumer_is_authority_only_and_does_not_write_world_truth() -> None:
    source = (ROOT / "scripts" / "interaction" / "CarryPlaceMirrorConsumer.gd").read_text(encoding="utf-8")

    assert "class_name CarryPlaceMirrorConsumer" in source
    assert "authority_only" in source
    assert "presentation_hint_only" in source
    assert "world_truth_claim" in source
    assert "character_actor_status" in source
    assert "authority_mutation\": false" in source
    assert "custody_holder_ref = str(payload.get(\"custody_holder_ref\"" in source
    assert "drop_target_ref = str(payload.get(\"drop_target_ref\"" in source


def test_carry_place_backend_bridge_route_and_probe_scene_are_wired_without_legacy_status_channel() -> None:
    bridge = (ROOT / "scripts" / "autoload" / "BackendBridge.gd").read_text(encoding="utf-8")
    bus = (ROOT / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(encoding="utf-8")
    probe = (ROOT / "scripts" / "verification" / "EmbodiedCarryPlaceProbe.gd").read_text(encoding="utf-8")
    scene = (ROOT / "scenes" / "phase0" / "EmbodiedCarryPlaceProbe.tscn").read_text(encoding="utf-8")

    assert "embodied_carry_place_event_received" in bus
    assert "\"embodied_carry_place_event\"" in bridge
    assert "_bus_emit(\"embodied_carry_place_event_received\"" in bridge
    route_index = bridge.find("_bus_emit(\"embodied_carry_place_event_received\"")
    assert "character_actor_status" not in bridge[route_index : route_index + 100]
    assert "CarryPlaceMirrorConsumer.gd" in probe
    assert "EMBODIED_CARRY_PLACE_BACKEND_URL" in probe
    assert "res://scripts/verification/EmbodiedCarryPlaceProbe.gd" in scene
