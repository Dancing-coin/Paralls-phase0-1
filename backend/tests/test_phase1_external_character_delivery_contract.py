from __future__ import annotations

import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTIVE = ROOT / "assets" / "active"
REPORTS = ROOT / "assets" / "characters" / "qualification_reports"


def _manifest(package_id: str) -> dict:
    path = ACTIVE / package_id / "manifest.json"
    assert path.is_file(), f"missing package manifest: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_two_external_packages_declare_provenance_and_runtime_contract() -> None:
    manifests = [_manifest("crusader_knight"), _manifest("external_character_b")]
    assert {m["package_id"] for m in manifests} == {"crusader_knight", "external_character_b"}
    for manifest in manifests:
        assert manifest["source"]["model_path"]
        assert len(manifest["source"]["digest_sha256"]) == 64
        assert manifest["provenance"]["source_uri"]
        assert manifest["provenance"]["qualification_report_ref"]
        assert manifest["canonical_mapping"]["profile_id"] == "humanoid.v1"
        assert manifest["rest_pose"]["import_policy"] == "applied_transforms"
        assert manifest["slots"]
        assert manifest["locomotion_map"]
        assert manifest["root_motion_profile"]["policy"] in {"hold", "bounded_continue", "reversible_continue"}
        assert manifest["physical_profile"]["collision_shape"]
        assert manifest["fallback"]["mode"]
        assert manifest["report_path"].startswith(".harness/verification/")


def test_delivery_timing_sheets_use_semantic_ids_and_empty_atomic_sequences() -> None:
    for package_id in ("crusader_knight", "external_character_b"):
        timing_path = ACTIVE / package_id / "docs" / "action-timing.json"
        timing = json.loads(timing_path.read_text(encoding="utf-8"))
        actions = timing["actions"]
        assert {a["action_id"] for a in actions} >= {"Idle", "Walk", "Run", "Jump", "Turn"}
        for action in actions:
            assert action["action_id"] != action["clip"]
            assert action["atomic_sequence"] == []
            assert action["timing"]["duration_seconds"] > 0


def test_qualification_matrix_keeps_rejected_candidates_rejected() -> None:
    matrix = json.loads((REPORTS / "qualification-matrix.json").read_text(encoding="utf-8"))
    by_id = {entry["candidate_id"]: entry for entry in matrix["candidates"]}
    assert by_id["crusader_knight"]["status"] in {"qualified", "qualified_with_fallback"}
    assert by_id["external_character_b"]["status"] == "rejected"
    assert by_id["npc_candidate"]["status"] == "rejected"
    assert by_id["female_trio_opt_in"]["status"] == "rejected"
    assert by_id["female_trio_opt_in"]["opt_in"] is True
    assert by_id["female_trio_opt_in"]["reasons"]
    assert all(entry["delivery_level"] in {"minimum_movement", "full_body_action", "concurrent_action", "presentation_extension"} for entry in by_id.values())


def test_task8_primary_roles_include_female_jk_female_t_and_bandage() -> None:
    matrix = json.loads((REPORTS / "qualification-matrix.json").read_text(encoding="utf-8"))
    by_id = {entry["candidate_id"]: entry for entry in matrix["candidates"]}
    assert {candidate_id for candidate_id, entry in by_id.items() if entry.get("task8_primary")} == {
        "female_jk_external",
        "female_t_external",
        "female_bandage_external",
    }
    assert by_id["female_jk_external"]["status"] in {"qualified", "qualified_with_fallback"}
    assert by_id["female_t_external"]["status"] in {"qualified", "qualified_with_fallback"}
    assert by_id["crusader_knight"].get("task8_primary") is False
    assert by_id["female_bandage_external"]["status"] in {"qualified", "qualified_with_fallback", "rejected"}
    assert by_id["female_bandage_external"]["runtime_admission"] in {
        "qualified",
        "blocked_pending_qualification",
    }


def test_female_bandage_source_is_staged_as_a_non_promoted_task7_candidate() -> None:
    package = ACTIVE / "female_bandage_external"
    manifest_path = package / "manifest.json"
    report_path = REPORTS / "female_bandage_external.json"
    working_copy_manifest = Path(
        r"D:/Users/User/Documents/paralls-art-assets/production-assets/characters/female_bandage_external/source/working-copy-manifest.json"
    )
    assert manifest_path.is_file()
    assert report_path.is_file()
    assert working_copy_manifest.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    copy_manifest = json.loads(working_copy_manifest.read_text(encoding="utf-8"))
    assert manifest["package_id"] == "female_bandage_external"
    assert manifest["candidate_status"] == "source_only"
    assert manifest["source"]["format"] == "blend"
    assert len(manifest["source"]["digest_sha256"]) == 64
    assert manifest["actions"] == []
    assert report["status"] == "rejected"
    assert "blender_export_unverified" in report["reasons"]
    assert "godot_import_unverified" in report["reasons"]
    assert copy_manifest["copy_policy"] == "new_file_only"
    assert copy_manifest["original_source"] == r"E:\下载\建模1 绷带血迹黑长直 T字版本 多动作版本.blend"


def test_reports_are_machine_readable_and_expose_fallback_and_concurrency_claims() -> None:
    for package_id, expected_status in (("crusader_knight", {"qualified", "qualified_with_fallback"}), ("external_character_b", {"rejected"})):
        report = json.loads((REPORTS / f"{package_id}.json").read_text(encoding="utf-8"))
        assert report["contract"] == "character_qualification_report.v1"
        assert report["package_id"] == package_id
        assert report["status"] in expected_status
        assert report["delivery_level"] in {"minimum_movement", "full_body_action", "concurrent_action", "presentation_extension"}
        assert report["fallback"]
        assert report["locomotion_compatibility"]
        assert report["provenance"]["package_digest"]
        assert report["actions"]
        assert any(a.get("semantic_action_id") for a in report["actions"])


def test_knight_actions_are_explicitly_unavailable_during_replacement_attempt() -> None:
    manifest = _manifest("crusader_knight")
    assert manifest["runtime_action_status"] == "unavailable"
    assert manifest["runtime_action_status_reason"]
    timing = json.loads((ACTIVE / "crusader_knight" / "docs" / "action-timing.json").read_text(encoding="utf-8"))
    assert timing["runtime_action_status"] == "unavailable"


def test_working_copies_are_declared_without_replacing_original_sources() -> None:
    art_root = Path(r"D:/Users/User/Documents/paralls-art-assets")
    for package_id in ("crusader_knight", "external_character_b"):
        manifest_path = art_root / "production-assets" / "characters" / package_id / "source" / "working-copy-manifest.json"
        assert manifest_path.is_file(), f"missing working-copy manifest: {manifest_path}"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["package_id"] == package_id
        assert manifest["copy_policy"] == "new_file_only"
        assert (art_root / manifest["working_copy"]).is_file()
        assert manifest["original_source"]


def test_female_t_source_package_is_staged_with_qualified_action_contract() -> None:
    package = ACTIVE / "female_t_external"
    manifest_path = package / "manifest.json"
    assert manifest_path.is_file(), f"missing female T package manifest: {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"]["format"] == "glb"
    assert len(manifest["source"]["digest_sha256"]) == 64
    assert manifest["canonical_mapping"]["deform_skeleton_ref"]
    assert manifest["rest_pose"]["pose"]
    assert set(manifest["locomotion_map"]) >= {"idle", "walk_forward", "run_forward", "jump_start", "jump_land", "turn_left", "turn_right"}
    assert manifest["actions_qualification_status"] in {"qualified", "qualified_with_fallback", "rejected"}


def test_female_t_receives_copied_short_punch_and_weapon_slot_contract() -> None:
    manifest = _manifest("female_t_external")
    actions = {action["semantic_action_id"]: action for action in manifest["actions"]}
    short_punch = actions["action:melee.short_punch"]
    assert short_punch["clip_ref"] == "short punch"
    assert short_punch["derived_from_package"] == "female_jk_external"
    assert short_punch["derived_from_clip_ref"] == "short punch"
    assert short_punch["mode"] == "derived_upper_body"
    assert short_punch["locomotion_compatibility"] == "coexist"
    assert set(manifest["required_slots"]) >= {"weapon_hand", "weapon_slot:sword", "weapon_hit_volume:sword"}
    assert manifest["slots"]["weapon_hand"]["canonical_bone"] == "right_hand"
    assert manifest["actions_qualification_status"] in {"qualified", "qualified_with_fallback"}


def test_female_t_glb_contains_copied_short_punch_and_weapon_socket_nodes() -> None:
    glb_path = ACTIVE / "female_t_external" / "female_t_external.glb"
    data = glb_path.read_bytes()
    _, _, total_length = struct.unpack_from("<4sII", data, 0)
    offset = 12
    document = None
    while offset < total_length:
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8 : offset + 8 + chunk_length]
        offset += 8 + chunk_length
        if chunk_type == 0x4E4F534A:
            document = json.loads(chunk.decode("utf-8"))
            break
    assert document is not None
    assert any(animation["name"] == "short punch" for animation in document["animations"])
    node_names = {node.get("name") for node in document["nodes"]}
    assert {"weapon_hand", "weapon_slot:sword", "weapon_hit_volume:sword"} <= node_names


def test_female_jk_source_candidate_is_staged_without_promoting_unqualified_actions() -> None:
    package = ACTIVE / "female_jk_external"
    manifest_path = package / "manifest.json"
    assert manifest_path.is_file(), f"missing female JK package manifest: {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"]["format"] == "glb"
    assert len(manifest["source"]["digest_sha256"]) == 64
    assert manifest["canonical_mapping"]["profile_id"] == "humanoid.v1"
    assert manifest["rest_pose"]["pose"]
    assert set(manifest["locomotion_map"]) >= {"idle", "walk_forward", "run_forward", "jump_start", "jump_land", "turn_left", "turn_right"}
    assert manifest["actions"]
    assert manifest["actions_qualification_status"] in {"qualified", "qualified_with_fallback", "rejected"}


def test_female_jk_melee_actions_declare_contact_windows_and_cancel_windows() -> None:
    manifest = _manifest("female_jk_external")
    actions = {action["semantic_action_id"]: action for action in manifest["actions"]}
    for action_id in ("action:melee.unarmed_punch", "action:melee.sword_slash"):
        action = actions[action_id]
        assert action["markers"]
        marker = action["markers"][0]
        assert marker["window_start_seconds"] <= marker["window_end_seconds"]
        assert marker["time_seconds"] >= marker["window_start_seconds"]
        assert marker["time_seconds"] <= marker["window_end_seconds"]
        assert action["cancel_windows"]


def test_female_jk_short_punch_is_a_derived_copy_and_preserves_boxing() -> None:
    manifest = _manifest("female_jk_external")
    actions = {action["semantic_action_id"]: action for action in manifest["actions"]}
    assert "action:melee.unarmed_punch" in actions
    assert actions["action:melee.unarmed_punch"]["clip_ref"] == "boxing"
    short_punch = actions["action:melee.short_punch"]
    assert short_punch["clip_ref"] == "short punch"
    assert short_punch["mode"] == "derived_upper_body"
    assert short_punch["locomotion_compatibility"] == "coexist"
    assert short_punch["derived_from_clip_ref"] == "boxing"


def test_female_jk_short_punch_glb_contains_only_upper_body_targets() -> None:
    glb_path = ACTIVE / "female_jk_external" / "female_jk_external.glb"
    data = glb_path.read_bytes()
    _, _, total_length = struct.unpack_from("<4sII", data, 0)
    offset = 12
    document = None
    while offset < total_length:
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8 : offset + 8 + chunk_length]
        offset += 8 + chunk_length
        if chunk_type == 0x4E4F534A:
            document = json.loads(chunk.decode("utf-8"))
            break
    assert document is not None
    nodes = {index: node.get("name", "") for index, node in enumerate(document["nodes"])}
    short_punch = next(animation for animation in document["animations"] if animation["name"] == "short punch")
    targets = {nodes[channel["target"]["node"]] for channel in short_punch["channels"]}
    assert targets
    assert not any(
        name in {"root.x", "spine_01.x"}
        or name.startswith(("thigh", "leg", "foot", "toes"))
        for name in targets
    )


def test_female_jk_short_punch_qualification_ignores_static_imported_rest_tracks() -> None:
    report = json.loads((REPORTS / "female_jk_external.json").read_text(encoding="utf-8"))
    assert report["status"] == "qualified"
    assert report["delivery_level"] == "concurrent_action"
    action = next(item for item in report["actions"] if item["semantic_action_id"] == "action:melee.short_punch")
    audit = action["audit"]
    assert audit["duration_seconds"] > 1.0
    assert audit["lower_body_impact"] == []
    assert audit["root_motion"] == {"translation": False, "rotation": False}
    assert audit["pelvis_motion"] == {"translation": False, "rotation": False}
