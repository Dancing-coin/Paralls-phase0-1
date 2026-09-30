from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
GODOT = os.environ.get("GODOT_EXE", r"D:\godot\Godot_v4.6.3-stable_win64.exe")


def test_root_motion_probe_reports_imported_measurements_for_primary_packages() -> None:
    completed = subprocess.run(
        [
            GODOT,
            "--headless",
            "--path",
            str(ROOT),
            "--scene",
            "res://scenes/phase0/RootMotionQualificationProbe.tscn",
            "--quit-after",
            "300",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    lines = [line for line in completed.stdout.splitlines() if line.startswith("root_motion_qualification:")]
    assert lines, completed.stdout + completed.stderr
    result = json.loads(lines[-1].split(":", 1)[1])
    assert result["contract"] == "root_motion_qualification.v1"
    packages = result["packages"]
    assert set(packages) == {"female_bandage_external", "female_jk_external", "female_t_external"}
    for package_id, package in packages.items():
        assert package["source_digest_sha256"]
        assert package["manifest_source_digest_sha256"]
        assert package["source_digest_sha256"] == package["manifest_source_digest_sha256"]
        assert package["axis"]["forward"] == "-z"
        assert package["axis"]["up"] == "+y"
        assert package["unit_scale"] == 1.0
        assert package["clips"]
        for clip in package["clips"].values():
            assert clip["duration_seconds"] > 0.0
            assert clip["cadence"]["sample_count"] >= 1
            assert "envelope" in clip
            assert clip["policy"] == "hold"
            assert clip["qualified"] is False
    jk_walk = packages["female_jk_external"]["clips"]["walk_forward"]
    assert jk_walk["classification"] in {"in_place", "root_motion_candidate"}
    if jk_walk["classification"] == "root_motion_candidate":
        assert jk_walk["envelope"]["net_displacement_magnitude"] > 0.0001

