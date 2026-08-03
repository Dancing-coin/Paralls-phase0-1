from __future__ import annotations

from pathlib import Path


def test_second_scene_capture_probe_targets_independent_scene_and_camera() -> None:
    root = Path(__file__).resolve().parents[2]
    probe = (root / "scripts/verification/VLAReplaySecondSceneCaptureProbe.gd").read_text(encoding="utf-8")
    verifier = (root / "scripts/verification/verify_vla_replay_second_scene_capture.py").read_text(encoding="utf-8")

    assert "ThroneHallWalkPreview.tscn" in probe
    assert "camera.make_current()" in probe
    assert "vla-replay-thronehall-walk-preview.png" in probe
    assert "_has_meaningful_pixels" in probe
    assert "render_status" in verifier
    assert "overall_vla_replay_second_scene_capture_passed" in verifier
