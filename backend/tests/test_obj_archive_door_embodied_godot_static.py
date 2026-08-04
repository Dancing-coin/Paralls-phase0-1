from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_archive_door_physical_presentation_consumes_only_applied_open_results() -> None:
    scene = (ROOT / "scenes" / "phase0" / "ArchiveDoorPhysical.tscn").read_text(encoding="utf-8")
    presentation = (ROOT / "scripts" / "object" / "ArchiveDoorPhysicalPresentation.gd").read_text(encoding="utf-8")

    assert 'node name="ApproachStance" type="Marker3D"' in scene
    assert 'node name="ContactAnchor" type="Marker3D"' in scene
    assert 'node name="HingePivot" type="Node3D"' in scene
    assert 'node name="DoorLeaf" type="MeshInstance3D"' in scene
    assert 'node name="ClosedPassageBlocker" type="StaticBody3D"' in scene
    assert 'node name="ArchiveDoorPhysicalPresentation" type="Node"' in scene
    assert 'if str(payload.get("settlement_status", "")) != "applied":' in presentation
    assert 'if str(payload.get("current_state", "")) != "open":' in presentation
    assert 'closed_passage_blocker.set_deferred("disabled", true)' in presentation
    assert 'hinge_pivot.transform = open_transform' in presentation
    assert 'world_truth' not in presentation


def test_archive_door_physical_presentation_keeps_closed_snapshot_for_non_applied_results() -> None:
    presentation = (ROOT / "scripts" / "object" / "ArchiveDoorPhysicalPresentation.gd").read_text(encoding="utf-8")

    assert 'func snapshot() -> Dictionary:' in presentation
    assert '"closed_blocker_enabled": not closed_passage_blocker.disabled' in presentation
    assert '"passage_occlusion_state": passage_occlusion_state' in presentation
    assert 'func apply_result(payload: Dictionary) -> bool:' in presentation


def test_applied_door_presentation_reports_only_a_bounded_post_apply_receipt() -> None:
    presentation = (ROOT / "scripts" / "object" / "ArchiveDoorPhysicalPresentation.gd").read_text(encoding="utf-8")
    bus = (ROOT / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(encoding="utf-8")
    backend_bridge = (ROOT / "scripts" / "autoload" / "BackendBridge.gd").read_text(encoding="utf-8")

    assert "embodied_presentation_observed_emitted" in presentation
    assert '"interaction_attempt_id": str(payload.get("interaction_attempt_id", ""))' in presentation
    assert '"settlement_id": applied_settlement_id' in presentation
    assert '"snapshot_digest"' in presentation
    assert "embodied_presentation_observed_emitted" in bus
    assert "_on_embodied_presentation_observed_emitted" in backend_bridge
    assert '"message_type": "embodied_presentation_observed"' in backend_bridge
