import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHARACTER = ROOT / "scripts" / "character"
ACTIVE = ROOT / "assets" / "active"
REPORTS = ROOT / "assets" / "characters" / "qualification_reports"
PRIMARY_PACKAGES = ("female_jk_external", "female_t_external", "female_bandage_external")
GODOT_CANDIDATES = (
    Path(r"D:\godot\Godot_v4.6.3-stable_win64.exe"),
    Path(r"E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe"),
)


def _source(name: str) -> str:
    return (CHARACTER / name).read_text(encoding="utf-8")


def _manifest(package_id: str) -> dict:
    return json.loads((ACTIVE / package_id / "manifest.json").read_text(encoding="utf-8"))


def _report(package_id: str) -> dict:
    return json.loads((REPORTS / f"{package_id}.json").read_text(encoding="utf-8"))


def _godot() -> Path | None:
    configured = os.environ.get("GODOT_EXE")
    candidates = (Path(configured),) if configured else GODOT_CANDIDATES
    return next((path for path in candidates if path.exists()), None)


def test_task8_registry_admits_only_qualified_female_primary_packages_with_provenance() -> None:
    registry = _source("CharacterEmbodimentAssetRegistry.gd")
    descriptor = _source("CharacterActionAssetDescriptor.gd")

    assert "PRIMARY_PACKAGE_IDS" in registry
    assert '"female_jk_external"' in registry
    assert '"female_t_external"' in registry
    assert '"female_bandage_external"' in registry
    assert '"crusader_knight"' not in registry
    assert "register_qualified_package" in registry
    assert "status == STATUS_REJECTED" in registry
    assert "qualification_report_ref" in registry
    assert "package_digest" in registry
    assert "source_clip_ref" in descriptor
    assert "derived_clip_ref" in descriptor
    assert "derived_from_clip_ref" in descriptor
    assert "canonical_bone_mask_ref" in descriptor

    for package_id in PRIMARY_PACKAGES:
        manifest = _manifest(package_id)
        report = _report(package_id)
        assert manifest["actions_qualification_status"] in {"qualified", "qualified_with_fallback"}
        assert report["status"] in {"qualified", "qualified_with_fallback"}
        assert report["provenance"]["package_digest"] == manifest["source"]["digest_sha256"]
        assert report["provenance"]["qualification_report_ref"].endswith(f"{package_id}.json")


def test_task8_registry_uses_concrete_resource_paths_for_primary_package_metadata() -> None:
    registry = _source("CharacterEmbodimentAssetRegistry.gd")

    assert "res://assets/active/%s/manifest.json" not in registry


def test_task8_profiles_preserve_explicit_full_body_fallback_and_weapon_bindings() -> None:
    registry = _source("CharacterEmbodimentAssetRegistry.gd")
    equipment = _source("CharacterEquipmentBindingProfile.gd")
    weapon = _source("CharacterWeaponActionProfile.gd")

    assert "func resolve(package_id: StringName, action_id: StringName, claims: Array[StringName])" in registry
    assert "full_body_exclusive" in registry
    assert "fallback_policy" in registry
    assert "resolve_slot" in equipment
    assert "weapon_hand" in equipment
    assert "weapon_slot:sword" in equipment
    assert "weapon_hit_volume:sword" in equipment
    assert "class_name CharacterWeaponActionProfile" in weapon
    assert '"melee"' in weapon
    assert '"hitscan"' in weapon
    assert "FORBIDDEN_TRUTH_FIELDS" in weapon

    for package_id in PRIMARY_PACKAGES:
        actions = _manifest(package_id)["actions"]
        sword_action = next(action for action in actions if action["semantic_action_id"] == "action:melee.sword_slash")
        assert sword_action["mode"] == "full_body_exclusive"
        assert sword_action["fallback_policy"] == "queue_until_compatible"
        assert set(sword_action["required_slots"]) == {
            "weapon_hand",
            "weapon_slot:sword",
            "weapon_hit_volume:sword",
        }


def test_task8_presentation_adapter_returns_playback_observations_without_gameplay_truth_writes() -> None:
    adapter = _source("RolePresentationAdapter.gd")

    assert "class_name RolePresentationAdapter" in adapter
    assert "func apply_input(input: Dictionary) -> Dictionary" in adapter
    assert "playback_observations" in adapter
    assert "semantic_action_id" in adapter
    assert "animation_clip_ref" not in adapter
    assert "FORBIDDEN_TRUTH_FIELDS" in adapter
    for forbidden_write in (
        r"global_position\\s*=",
        r"velocity\\s*=",
        r"damage\\s*=",
        r"hit\\s*=",
        r"inventory\\s*=",
        r"ActionAttempt",
        r"Gameplay",
        r"ESM",
    ):
        assert re.search(forbidden_write, adapter) is None


def test_task8_semantic_presentation_path_uses_qualified_profiles_for_skins() -> None:
    adapter = _source("RolePresentationAdapter.gd")
    playback = (ROOT / "scripts" / "interaction" / "EmbodiedActionPlaybackAdapter.gd").read_text(encoding="utf-8")
    generic_skin = _source("GenericRoleSkin.gd")
    knight_skin = _source("KnightRoleSkin.gd")

    assert "play_qualified_profile" in adapter
    assert "func begin_qualified_phase" in playback
    assert "play_qualified_profile" in playback
    assert "func play_qualified_profile(profile: Dictionary)" in generic_skin
    assert "func play_qualified_profile(profile: Dictionary)" in knight_skin
    semantic_path = playback.split("func begin_qualified_phase", 1)[1]
    assert "animation_clip_ref" not in semantic_path.split("func restore_local_ownership", 1)[0]


def test_task8_headless_registry_probe_resolves_profiles_and_blocks_rejected_registration() -> None:
    executable = _godot()
    if executable is None:
        return
    result = subprocess.run(
        [
            str(executable),
            "--headless",
            "--path",
            str(ROOT),
            "--script",
            "res://scripts/verification/Task8RegistryProbe.gd",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(next(line.removeprefix("TASK8_REGISTRY_PROBE=") for line in result.stdout.splitlines() if line.startswith("TASK8_REGISTRY_PROBE=")))
    for package_id in PRIMARY_PACKAGES:
        assert payload[package_id]["unarmed_profile"] == "action:melee.unarmed_punch:primary"
        assert payload[package_id]["full_body_status"] == "queued_until_compatible"
    assert payload["rejected_registration"] is True
    assert payload["validation_matrix"] == {
        "digest_mismatch": True,
        "canonical_mapping_missing": True,
        "manifest_status_mismatch": True,
        "atomic_sequence_nonempty": True,
        "required_slot_missing": True,
    }
