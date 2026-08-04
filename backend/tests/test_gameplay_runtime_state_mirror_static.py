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
    assert "func _apply_delta_delivery(" in source
    assert "base_snapshot_checksum" in source
    assert "removed_group_ids" in source
    snapshot_consumer = source.split("func consume_projection(payload: Dictionary)", 1)[1].split("func clear_projection", 1)[0]
    assert "resync_required = false" in snapshot_consumer


def test_gameplay_runtime_state_mirror_exposes_bounded_prediction_overlay_api() -> None:
    source = (ROOT / "scripts" / "interaction" / "GameplayRuntimeStateMirrorConsumer.gd").read_text(encoding="utf-8")

    assert "var pending_predictions: Dictionary = {}" in source
    assert "func begin_stamina_prediction(" in source
    assert "func get_predicted_resource_current(" in source
    assert "func _apply_prediction_resolutions(" in source
    assert "prediction_confirmation_projection_required" in source
    assert "pending_predictions.clear()" in source
    assert "world_truth_claim" in source


def test_backend_bridge_and_presentation_bus_expose_only_projection_signal() -> None:
    bridge = (ROOT / "scripts" / "autoload" / "BackendBridge.gd").read_text(encoding="utf-8")
    bus = (ROOT / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(encoding="utf-8")
    assert '"gameplay_runtime_state_projection"' in bridge
    assert '"gameplay_runtime_state_projection_received"' in bridge
    assert 'projection.erase("message_type")' in bridge
    assert '_bus_emit("gameplay_runtime_state_projection_received", [projection])' in bridge
    assert "signal gameplay_runtime_state_projection_received(payload)" in bus
    assert '"gameplay_mirror_delivery"' in bridge
    assert "signal gameplay_mirror_delivery_received(payload)" in bus
    assert '"gameplay_mirror_resync_required"' in bridge
    assert "signal gameplay_mirror_resync_required_received(payload)" in bus


def test_gameplay_mirror_bridge_is_scope_limited_and_presentation_only() -> None:
    source = (ROOT / "scripts" / "interaction" / "GameplayMirrorBridge.gd").read_text(encoding="utf-8")

    assert '"websocket_session_bind"' in source
    assert '"gameplay_mirror_subscribe"' in source
    assert "_allowed_actor_refs.has(actor_ref)" in source
    assert "consumer.consume_projection(payload)" in source
    assert "consumer.consume_delivery(payload)" in source
    assert "if consumer.resync_required:" in source
    assert "request_snapshot(actor_ref)" in source
    assert "consumer.mark_resync_required()" in source
    assert "backend_disconnected.connect(_on_backend_disconnected)" in source
    assert "_allowed_actor_refs.clear()" in source
    assert "clear_projection()" in source
    assert "world_truth_claim" not in source
    assert "authority_command" not in source


def test_gameplay_mirror_bridge_requires_a_new_handoff_enrollment_after_disconnect() -> None:
    source = (ROOT / "scripts" / "interaction" / "GameplayMirrorBridge.gd").read_text(encoding="utf-8")

    assert "func has_pending_enrollment() -> bool:" in source
    assert "return not _session_enrollment.is_empty()" in source
    assert "if _session_enrollment.is_empty():\n\t\treturn ERR_UNCONFIGURED" in source
    assert "_session_enrollment.clear()" in source


def test_live_mirror_verifier_covers_authority_prediction_confirmation_and_rejection() -> None:
    verifier = (ROOT / "scripts" / "verification" / "verify_live_gameplay_mirror_delivery.py").read_text(encoding="utf-8")
    probe = (ROOT / "scripts" / "verification" / "LiveGameplayMirrorDeliveryProbe.gd").read_text(encoding="utf-8")

    assert '"prediction"' in verifier
    assert "_post_prediction_confirm" in verifier
    assert "_post_prediction_reject" in verifier
    assert "prediction:live:stamina-confirm" in probe
    assert "prediction:live:stamina-reject" in probe
    assert "live_prediction_confirm_reject_rollback_verified" in probe
    assert "live-gameplay-mirror-prediction-backend.json" in verifier
    assert 'str(prediction_rejection.get("error_code", "")) == "revision_conflict"' in verifier
    assert '"mutation_count": 0' in (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
