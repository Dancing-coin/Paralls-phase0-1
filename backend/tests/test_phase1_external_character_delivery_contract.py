from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTIVE = ROOT / "assets" / "active"
REPORTS = ROOT / "assets" / "characters" / "qualification_reports"


def _manifest(package_id: str) -> dict:
    path = ACTIVE / package_id / "manifest.json"
    assert path.is_file(), f"missing package manifest: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _asset_digest(path: Path) -> str:
    with path.open("rb") as source:
        header = source.read(256)
        if header.startswith(b"version https://git-lfs.github.com/spec/v1"):
            # 静态包合同接受 LFS 身份，不据此声明真实模型已下载或可用于运行时。
            pointer = re.fullmatch(
                rb"version https://git-lfs\.github\.com/spec/v1\r?\noid sha256:([0-9a-f]{64})\r?\nsize [1-9][0-9]*\r?\n?",
                header,
            )
            assert pointer is not None, f"invalid LFS pointer: {path}"
            return pointer.group(1).decode("ascii")
        source.seek(0)
        return hashlib.file_digest(source, "sha256").hexdigest()
def _glb_document(package_id: str) -> dict:
    path = ACTIVE / package_id / f"{package_id}.glb"
    data = path.read_bytes()
    _, _, total_length = struct.unpack_from("<4sII", data, 0)
    offset = 12
    while offset < total_length:
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8 : offset + 8 + chunk_length]
        offset += 8 + chunk_length
        if chunk_type == 0x4E4F534A:
            return json.loads(chunk.rstrip(b" ").decode("utf-8"))
    raise AssertionError(f"missing JSON chunk in {path}")


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


def test_female_bandage_source_provenance_is_preserved_after_runtime_promotion() -> None:
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
    assert manifest["candidate_status"] == "candidate"
    assert manifest["source"]["format"] == "glb"
    assert len(manifest["source"]["digest_sha256"]) == 64
    assert manifest["provenance"]["original_source_digest_sha256"] == copy_manifest["source_digest_sha256"]
    assert report["status"] in {"qualified", "qualified_with_fallback", "rejected"}
    assert copy_manifest["copy_policy"] == "new_file_only"
    assert copy_manifest["original_source"] == r"E:\下载\建模1 绷带血迹黑长直 T字版本 多动作版本.blend"


def test_primary_packages_record_authoring_and_runtime_frame_rates() -> None:
    expected_authoring_rates = {
        "female_jk_external": 60.0,
        "female_t_external": 60.0,
        "female_bandage_external": 30.0,
    }
    for package_id, authoring_rate in expected_authoring_rates.items():
        manifest = _manifest(package_id)
        timing = json.loads(
            (ACTIVE / package_id / "docs" / "action-timing.json").read_text(
                encoding="utf-8"
            )
        )
        provenance = manifest["provenance"]
        assert provenance["authoring_frame_rate"] == authoring_rate
        assert provenance["runtime_export_frame_rate"] == 60.0
        assert timing["authoring_frame_rate"] == authoring_rate
        assert timing["runtime_frame_rate"] == 60.0


def test_primary_role_packages_share_the_same_runtime_action_contract() -> None:
    package_ids = ("female_bandage_external", "female_jk_external", "female_t_external")
    semantic_sets = []
    for package_id in package_ids:
        manifest = _manifest(package_id)
        semantic_sets.append({action["semantic_action_id"] for action in manifest["actions"]})
        assert semantic_sets[-1] == {
            "action:melee.unarmed_punch",
            "action:melee.sword_slash",
        }
        animation_names = {animation["name"] for animation in _glb_document(package_id)["animations"]}
        lowered_names = {name.lower() for name in animation_names}
        assert {"idle", "walking", "running", "jump", "boxing", "sword attack"} <= lowered_names
        assert "short punch" not in lowered_names
    assert semantic_sets[0] == semantic_sets[1] == semantic_sets[2]


def test_female_bandage_is_qualified_third_primary_after_real_blender_export() -> None:
    manifest = _manifest("female_bandage_external")
    report = json.loads((REPORTS / "female_bandage_external.json").read_text(encoding="utf-8"))
    glb_path = ACTIVE / "female_bandage_external" / "female_bandage_external.glb"
    assert glb_path.is_file()
    assert manifest["source"]["format"] == "glb"
    assert manifest["source_model_path"] == "res://assets/active/female_bandage_external/female_bandage_external.glb"
    assert manifest["actions_qualification_status"] in {"qualified", "qualified_with_fallback"}
    assert manifest["runtime_admission"] == "qualified"
    assert report["status"] in {"qualified", "qualified_with_fallback"}
    assert report["delivery_level"] == "concurrent_action"
    assert set(manifest["locomotion_map"]) >= {"idle", "walk_forward", "run_forward", "jump_start", "jump_land"}
    assert "turn_left" not in manifest["locomotion_map"]
    assert "turn_right" not in manifest["locomotion_map"]
    action_ids = {action["semantic_action_id"] for action in manifest["actions"]}
    assert action_ids == {"action:melee.unarmed_punch", "action:melee.sword_slash"}
    assert set(manifest["required_slots"]) >= {"weapon_hand", "weapon_slot:sword", "weapon_hit_volume:sword"}

    data = glb_path.read_bytes()
    _, _, total_length = struct.unpack_from("<4sII", data, 0)
    offset = 12
    document = None
    while offset < total_length:
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8 : offset + 8 + chunk_length]
        offset += 8 + chunk_length
        if chunk_type == 0x4E4F534A:
            document = json.loads(chunk.rstrip(b" ").decode("utf-8"))
            break
    assert document is not None
    assert len(document["skins"][0]["joints"]) == 68
    animation_names = {animation["name"] for animation in document["animations"]}
    assert {"idle", "walking", "running", "jump", "boxing", "SWORD ATTACK"} <= animation_names
    assert "short punch" not in {name.lower() for name in animation_names}
    assert {action["semantic_action_id"] for action in report["actions"]} == {
        "action:melee.unarmed_punch",
        "action:melee.sword_slash",
    }
    assert {node.get("name") for node in document["nodes"]} >= {
        "weapon_hand", "weapon_slot:sword", "weapon_hit_volume:sword"
    }


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


def test_knight_actions_are_available_after_replacement_qualification() -> None:
    manifest = _manifest("crusader_knight")
    assert manifest["runtime_action_status"] == "available"
    assert manifest["runtime_action_status_reason"]
    timing = json.loads((ACTIVE / "crusader_knight" / "docs" / "action-timing.json").read_text(encoding="utf-8"))
    assert timing["runtime_action_status"] == "available"


def test_delivery_copy_references_preserve_original_source_identity() -> None:
    # 仅验证本仓库的交付声明与文件/LFS 存根；外部生产仓库的 working-copy 仍需独立验收。
    for package_id in ("crusader_knight", "external_character_b"):
        manifest = _manifest(package_id)
        delivery_copy = (ROOT / manifest["source"]["model_path"]).resolve()
        original_source = (ROOT / manifest["provenance"]["source_uri"]).resolve()
        assert delivery_copy.is_relative_to(ACTIVE / package_id)
        assert original_source.is_relative_to(ROOT / "archive")
        assert delivery_copy != original_source
        assert delivery_copy.is_file(), f"missing delivery copy: {delivery_copy}"
        assert original_source.is_file(), f"missing archived original: {original_source}"
        assert manifest["source_model_path"] == f'res://{manifest["source"]["model_path"]}'
        digest = manifest["source"]["digest_sha256"].lower()
        assert manifest["provenance"]["package_digest"].lower() == digest
        # A delivery copy is a new file.  The manifest pins the delivered
        # runtime artifact; the archived source remains a separate provenance
        # input and may use a different file format or byte representation.
        assert _asset_digest(delivery_copy) == digest
        assert original_source.stat().st_size > 0


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
    assert set(manifest["locomotion_map"]) >= {"idle", "walk_forward", "run_forward", "jump_start", "jump_land"}
    assert "turn_left" not in manifest["locomotion_map"]
    assert "turn_right" not in manifest["locomotion_map"]
    assert manifest["actions_qualification_status"] in {"qualified", "qualified_with_fallback", "rejected"}


def test_female_t_exposes_shared_melee_and_weapon_slot_contract() -> None:
    manifest = _manifest("female_t_external")
    actions = {action["semantic_action_id"]: action for action in manifest["actions"]}
    assert set(actions) == {"action:melee.unarmed_punch", "action:melee.sword_slash"}
    assert actions["action:melee.unarmed_punch"]["clip_ref"] == "boxing"
    assert actions["action:melee.sword_slash"]["clip_ref"].lower() == "sword attack"
    assert set(manifest["required_slots"]) >= {"weapon_hand", "weapon_slot:sword", "weapon_hit_volume:sword"}
    assert manifest["slots"]["weapon_hand"]["canonical_bone"] == "right_hand"
    assert manifest["actions_qualification_status"] in {"qualified", "qualified_with_fallback"}


def test_female_t_glb_contains_weapon_socket_nodes() -> None:
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
    animation_names = {animation["name"] for animation in document["animations"]}
    assert "short punch" not in {name.lower() for name in animation_names}
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
    assert set(manifest["locomotion_map"]) >= {"idle", "walk_forward", "run_forward", "jump_start", "jump_land"}
    assert "turn_left" not in manifest["locomotion_map"]
    assert "turn_right" not in manifest["locomotion_map"]
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


def test_female_jk_melee_actions_preserve_boxing_and_sword_attack() -> None:
    manifest = _manifest("female_jk_external")
    actions = {action["semantic_action_id"]: action for action in manifest["actions"]}
    assert "action:melee.unarmed_punch" in actions
    assert actions["action:melee.unarmed_punch"]["clip_ref"] == "boxing"
    assert set(actions) == {"action:melee.unarmed_punch", "action:melee.sword_slash"}
    assert actions["action:melee.sword_slash"]["clip_ref"].lower() == "sword attack"


def test_female_jk_glb_contains_no_short_punch() -> None:
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
    animation_names = {animation["name"] for animation in document["animations"]}
    assert "short punch" not in {name.lower() for name in animation_names}


def test_female_jk_qualification_reports_only_shared_melee_actions() -> None:
    report = json.loads((REPORTS / "female_jk_external.json").read_text(encoding="utf-8"))
    assert report["status"] == "qualified"
    assert report["delivery_level"] == "concurrent_action"
    assert {item["semantic_action_id"] for item in report["actions"]} == {
        "action:melee.unarmed_punch",
        "action:melee.sword_slash",
    }
