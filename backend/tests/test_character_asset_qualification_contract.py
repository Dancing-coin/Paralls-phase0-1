from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
GODOT_CANDIDATES = (
    Path(r"D:\godot\Godot_v4.6.3-stable_win64.exe"),
    Path(r"E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe"),
)


def _godot() -> Path | None:
    configured = os.environ.get("GODOT_EXE")
    candidates = (Path(configured),) if configured else GODOT_CANDIDATES
    return next((candidate for candidate in candidates if candidate.exists()), None)


def test_character_asset_qualification_schemas_define_closed_statuses_and_contracts() -> None:
    manifest_schema = json.loads(
        (ROOT / "assets/validation/schemas/character-action-asset-manifest.v1.json").read_text(encoding="utf-8")
    )
    report_schema = json.loads(
        (ROOT / "assets/validation/schemas/character-qualification-report.v1.json").read_text(encoding="utf-8")
    )

    assert manifest_schema["properties"]["canonical_mapping"]["required"] == ["profile_id", "bones"]
    assert manifest_schema["properties"]["locomotion_map"]["type"] == "object"
    assert report_schema["properties"]["status"]["enum"] == [
        "qualified",
        "qualified_with_fallback",
        "rejected",
    ]
    assert "clip_audits" in report_schema["properties"]


@pytest.mark.skipif(_godot() is None, reason="Godot executable is unavailable")
def test_character_asset_qualification_reports_explicit_mapping_outcomes() -> None:
    """Rejecting a required body contract must not be masked by source names."""
    executable = _godot()
    assert executable is not None
    result = subprocess.run(
        [
            str(executable),
            "--headless",
            "--path",
            str(ROOT),
            "--script",
            "res://scripts/verification/tests/test_character_asset_qualification_runtime.gd",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])

    assert report["valid_humanoid"] == "qualified"
    assert report["invalid_rest_pose"] == "rejected"
    assert report["missing_root_bone"] == "rejected"
    assert report["unmapped_required_locomotion_tag"] == "rejected"
    assert report["missing_required_clip"] == "rejected"
    assert report["full_body_as_upper_body"] == "rejected"
    assert report["required_slot_incompatible"] == "rejected"
    assert report["missing_optional_finger_facial"] == "qualified"
    assert report["explicit_fallback"] == "qualified_with_fallback"
    assert report["rejected_without_fallback"] == "rejected"

    assert "optional:left_finger_1" in report["optional_bones"]
    assert "optional:facial_jaw" in report["optional_bones"]
    assert "root_bone_missing" in report["missing_root_reasons"]
    assert "upper_body_lower_body_motion" in report["full_body_reasons"]
    assert "slot_incompatible:weapon_hand" in report["slot_reasons"]
    assert report["valid_wave_audit"]["bone_impact"] == ["left_hand"]
    assert report["full_body_wave_audit"]["lower_body_impact"] == ["left_upper_leg"]
