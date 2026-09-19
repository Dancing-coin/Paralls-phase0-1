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
    assert "consumer.consume_validated_delivery(payload)" in source
    assert "func _accept_transport(payload: Dictionary)" in source
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


def test_government_drought_advisory_presentation_is_jurisdiction_scoped_and_read_only() -> None:
    bridge = (ROOT / "scripts" / "interaction" / "GameplayMirrorBridge.gd").read_text(encoding="utf-8")
    consumer = (ROOT / "scripts" / "interaction" / "GovernmentDroughtAdvisoryPresentationConsumer.gd").read_text(encoding="utf-8")
    bus = (ROOT / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(encoding="utf-8")

    assert "allowed_government_drought_advisory_jurisdiction_refs" in bridge
    assert '"gameplay_government_drought_advisory_subscribe"' in bridge
    assert "government_drought_advisory_delivery_received" in bridge
    assert "signal government_drought_advisory_projection_received(payload)" in bus
    assert "government_drought_advisory.project.v1" in consumer
    assert "jurisdiction_ref_mismatch" in consumer
    assert "authority_mutation\": false" in consumer
    assert "actor_ref" not in consumer
    assert "authority_command" not in consumer


def test_godot_mirror_probe_executes_the_government_advisory_scope_boundary() -> None:
    probe = (ROOT / "scripts" / "verification" / "GameplayMirrorBridgeProbe.gd").read_text(encoding="utf-8")

    assert "GovernmentDroughtAdvisoryPresentationConsumer.gd" in probe
    assert "allowed_government_drought_advisory_jurisdiction_refs" in probe
    assert "government_drought_advisory_projection_received" in probe
    assert "government_drought_advisory_delivery_received" in probe
    assert "jurisdiction:hidden" in probe
    assert "advisory_consumer.last_delivery_sequence == 1" in probe


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


def test_rebound_projection_removal_preserves_authorized_consumer():
    source = (ROOT / 'scripts/interaction/GameplayMirrorBridge.gd').read_text(encoding='utf-8')
    bound = source.split('func _on_session_bound(', 1)[1].split('\n\nfunc ', 1)[0]
    retained = bound.split('\t\telse:', 1)[1].split('\n\tfor jurisdiction_ref', 1)[0]
    assert 'clear_projection()' in retained
    assert 'projection_removed.emit(actor_ref)' in retained
    assert 'unregister_consumer' not in retained


def test_population_lod_demotes_before_promoting_and_probe_measures_transient_peak():
    presenter = (ROOT / 'scripts/phase0/PopulationPresenter.gd').read_text(encoding='utf-8')
    process = presenter.split('func _process(', 1)[1].split('\n\nfunc ', 1)[0]
    assert process.index('for actor_ref: String in _near_labels.keys():') < process.index('marker.mesh = _near_mesh')
    probe = (ROOT / 'scripts/verification/GameplayMirrorBridgeProbe.gd').read_text(encoding='utf-8')
    assert 'node_added.connect' in probe and 'node_removed.connect' in probe
    assert 'peak_labels' in probe and 'peak_meshes' in probe
    assert '_verify_population_near_swap()' in probe


def test_population_screenshot_finishes_before_rotation_and_uses_verified_anchor():
    probe = (ROOT / 'scripts/phase0/PopulationProbe.gd').read_text(encoding='utf-8')
    sample_end = probe.split('if now - _sample_start_us >= SAMPLE_US:', 1)[1].split('elif _stage == "rotating"', 1)[0]
    assert sample_end.index('_write_stage("capturing_after")') < sample_end.index('await _capture("after.png")')
    assert sample_end.index('await _capture("after.png")') < sample_end.index('adapter.set_interest_window(32)')
    capture = probe.split('func _capture(', 1)[1].split('\n\nfunc ', 1)[0]
    assert '_last_wire' not in capture
    assert '_last_verified_anchor.duplicate(true)' in capture
    assert 'frame_pre_draw' in capture and 'frame_post_draw' in capture
    assert '"warmup_us"' in probe and '"sample_duration_us"' in probe
