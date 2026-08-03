from __future__ import annotations

import json
from pathlib import Path

from scripts.verification.vla_live_proof_artifact import (
    GODOT_RUNTIME_CAPTURE,
    GODOT_RUNTIME_REPORT,
    redact_inline_image_payloads,
    resolve_live_proof_image,
    resolve_annotation_sample_capture,
)


def _write_runtime_capture(root: Path, *, artifact_ref: str | None = None) -> None:
    capture = root / GODOT_RUNTIME_CAPTURE
    capture.parent.mkdir(parents=True, exist_ok=True)
    capture.write_bytes(b"\x89PNG\r\n\x1a\n")
    expected_ref = "runtime://artifact/" + capture.resolve().as_posix()
    report = root / GODOT_RUNTIME_REPORT
    report.write_text(
        json.dumps(
            {
                "status": "godot-runtime-sampling-verified",
                "provider_refs": {"visual_inputs": [{"artifact_ref": artifact_ref or expected_ref, "ref_id": "runtime://camera/test/frame/1"}]},
            }
        ),
        encoding="utf-8",
    )


def test_godot_runtime_capture_requires_matching_runtime_report(tmp_path: Path) -> None:
    _write_runtime_capture(tmp_path)

    image = resolve_live_proof_image(
        tmp_path,
        configured_url="",
        configured_path="",
        use_godot_runtime_capture=True,
        max_godot_capture_age_seconds=60,
    )

    assert image.origin == "godot_runtime_capture"
    assert image.source.startswith("data:image/png;base64,")
    assert str(GODOT_RUNTIME_REPORT) in image.evidence_refs


def test_godot_runtime_capture_rejects_unmatched_artifact_ref(tmp_path: Path) -> None:
    _write_runtime_capture(tmp_path, artifact_ref="runtime://artifact/not-the-capture.png")

    image = resolve_live_proof_image(
        tmp_path,
        configured_url="",
        configured_path="",
        use_godot_runtime_capture=True,
        max_godot_capture_age_seconds=60,
    )

    assert image.source == ""
    assert image.failure_reason == "godot_capture_artifact_ref_mismatch"


def test_live_proof_report_redacts_inline_image_payloads_recursively() -> None:
    redacted = redact_inline_image_payloads(
        {"source_ref_lineage": ["data:image/png;base64,secret-payload"], "nested": {"value": "safe"}}
    )

    assert redacted == {"source_ref_lineage": ["redacted_data_image"], "nested": {"value": "safe"}}


def test_annotation_sample_capture_uses_its_own_scope_and_runtime_report(tmp_path: Path) -> None:
    capture = tmp_path / "capture.png"
    capture.write_bytes(b"\x89PNG\r\n\x1a\n")
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "status": "verified",
                "artifact_ref": "runtime://artifact/" + capture.resolve().as_posix(),
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "docs/verification/vla-advisory-replay-annotation-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "sample_id": "second-scene",
                        "room_id": "room_second",
                        "scene_id": "scene_second",
                        "zone_id": "zone_second",
                        "subject_id": "char_c",
                        "target_ref": "",
                        "runtime_capture": {"report_path": "report.json", "capture_path": "capture.png", "expected_status": "verified"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    image = resolve_annotation_sample_capture(tmp_path, sample_id="second-scene", max_age_seconds=60)

    assert image.source.startswith("data:image/png;base64,")
    assert image.origin == "annotation_runtime_capture"
    assert image.sample_scope["scene_id"] == "scene_second"
