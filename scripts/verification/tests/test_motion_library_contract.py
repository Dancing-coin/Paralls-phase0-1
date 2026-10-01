from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_humanoid_v1_manifest_declares_six_canonical_states():
    manifest = load_json(
        ROOT / "assets/motion_library/approved/humanoid.v1/street_locomotion.manifest.json"
    )
    assert manifest["motion_library_id"] == "motionlib:humanoid.v1.core@1"
    assert manifest["skeleton_profile_id"] == "humanoid.v1"
    assert manifest["semantic_actions"]["action:locomotion.walk"]["clip_ref"] == "walking2"
    assert set(manifest["semantic_actions"]) == {
        "action:locomotion.idle",
        "action:locomotion.walk",
        "action:locomotion.run",
        "action:locomotion.jump",
        "action:melee.boxing",
        "action:melee.sword_attack",
    }


def test_skeleton_profile_and_motion_manifest_have_complete_contract_fields():
    profile = load_json(ROOT / "assets/skeleton_profiles/humanoid.v1.json")
    manifest = load_json(
        ROOT / "assets/motion_library/approved/humanoid.v1/street_locomotion.manifest.json"
    )
    assert {
        "skeleton_profile_id",
        "version",
        "canonical_bones",
        "hierarchy_digest",
        "rest_pose",
        "unit_scale",
        "forward_axis",
        "root_motion_policy",
        "socket_profile",
    } <= profile.keys()
    assert len(profile["canonical_bones"]) == 68
    assert {
        "motion_library_id",
        "skeleton_profile_id",
        "animation_library_ref",
        "clips",
        "semantic_actions",
        "source_digest",
        "qualification_report_ref",
        "qualification_status",
    } <= manifest.keys()
    for clip in manifest["clips"].values():
        assert {"clip_ref", "duration_seconds", "track_count", "canonical_bone_ids", "loop_mode"} <= clip.keys()
