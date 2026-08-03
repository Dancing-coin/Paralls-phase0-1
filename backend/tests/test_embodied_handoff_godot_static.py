from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_handoff_mirror_consumer_is_authority_only_and_does_not_write_world_truth() -> None:
    source = (ROOT / "scripts" / "interaction" / "HandoffMirrorConsumer.gd").read_text(encoding="utf-8")

    assert "class_name HandoffMirrorConsumer" in source
    assert "authority_only" in source
    assert "presentation_hint_only" in source
    assert "world_truth_claim" in source
    assert "character_actor_status" in source
    assert "authority_mutation\": false" in source
    assert "owner_ref = str(payload.get(\"owner_ref\"" in source
    assert "custody_holder_ref = str(payload.get(\"custody_holder_ref\"" in source


def test_handoff_backend_bridge_route_and_probe_scene_are_wired_without_legacy_status_channel() -> None:
    bridge = (ROOT / "scripts" / "autoload" / "BackendBridge.gd").read_text(encoding="utf-8")
    bus = (ROOT / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(encoding="utf-8")
    probe = (ROOT / "scripts" / "verification" / "EmbodiedHandoffProbe.gd").read_text(encoding="utf-8")
    scene = (ROOT / "scenes" / "phase0" / "EmbodiedHandoffProbe.tscn").read_text(encoding="utf-8")

    assert "embodied_handoff_event_received" in bus
    assert "\"embodied_handoff_event\"" in bridge
    assert "_bus_emit(\"embodied_handoff_event_received\"" in bridge
    route_index = bridge.find("_bus_emit(\"embodied_handoff_event_received\"")
    assert "character_actor_status" not in bridge[route_index : route_index + 100]
    assert "HandoffMirrorConsumer.gd" in probe
    assert "EMBODIED_HANDOFF_BACKEND_URL" in probe
    assert "res://scripts/verification/EmbodiedHandoffProbe.gd" in scene
