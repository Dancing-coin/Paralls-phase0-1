from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_gameplay_runtime_state_mirror_is_presentation_only_and_fail_closed() -> None:
    source = (ROOT / "scripts" / "interaction" / "GameplayRuntimeStateMirrorConsumer.gd").read_text(encoding="utf-8")
    assert "gameplay_runtime_state.godot.v1" in source
    assert "authority_mutation\": false" in source
    assert "forbidden_projection_field" in source
    assert "world_truth_claim" in source
    assert "private_mind_state" in source
    assert "_find_forbidden_field" in source


def test_backend_bridge_and_presentation_bus_expose_only_projection_signal() -> None:
    bridge = (ROOT / "scripts" / "autoload" / "BackendBridge.gd").read_text(encoding="utf-8")
    bus = (ROOT / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(encoding="utf-8")
    assert '"gameplay_runtime_state_projection"' in bridge
    assert '"gameplay_runtime_state_projection_received"' in bridge
    assert 'projection.erase("message_type")' in bridge
    assert '_bus_emit("gameplay_runtime_state_projection_received", [projection])' in bridge
    assert "signal gameplay_runtime_state_projection_received(payload)" in bus


def test_gameplay_mirror_bridge_is_scope_limited_and_presentation_only() -> None:
    source = (ROOT / "scripts" / "interaction" / "GameplayMirrorBridge.gd").read_text(encoding="utf-8")

    assert '"websocket_session_bind"' in source
    assert '"gameplay_mirror_subscribe"' in source
    assert "_allowed_actor_refs.has(actor_ref)" in source
    assert "consumer.consume_projection(payload)" in source
    assert "backend_disconnected.connect(_on_backend_disconnected)" in source
    assert "_allowed_actor_refs.clear()" in source
    assert "clear_projection()" in source
    assert "world_truth_claim" not in source
    assert "authority_command" not in source
