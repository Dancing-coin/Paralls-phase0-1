extends SceneTree

const RegistryRef = preload("res://scripts/character/CharacterEmbodimentAssetRegistry.gd")
const PACKAGE_IDS := ["female_bandage_external", "female_jk_external", "female_t_external"]
const ACTION_IDS := ["action:melee.unarmed_punch", "action:melee.sword_slash"]
const WRONG_DIGEST_PATH := "res://" + "wrong_digest.json"

func _initialize() -> void:
    call_deferred("_run")

func _run() -> void:
    var registry := RegistryRef.new()
    var unknown := registry.resolve(&"unknown_package", &"action:melee.unarmed_punch", [])
    var missing := registry.resolve(&"female_bandage_external", &"action:missing", [])
    var wrong_digest := registry.register_qualified_package(&"female_bandage_external", {"package_id": "female_bandage_external"}, {"status": "qualified", "package_id": "female_bandage_external"}, WRONG_DIGEST_PATH)
    var qualified_count := 0
    var action_count := 0
    for package_id in PACKAGE_IDS:
        var package_actions := 0
        for action_id in ACTION_IDS:
            var resolved: Dictionary = registry.resolve(StringName(package_id), StringName(action_id), [])
            if bool(resolved.get("accepted", false)):
                action_count += 1
                package_actions += 1
        if package_actions == ACTION_IDS.size():
            qualified_count += 1
    var passed := str(unknown.get("reason", "")) == "package_not_qualified" and str(missing.get("reason", "")) == "semantic_action_unavailable" and not wrong_digest and action_count == 6 and qualified_count == 3
    print("character_asset_admission_probe:%s" % JSON.stringify({"unknown": unknown, "missing": missing, "wrong_digest": wrong_digest, "qualified_packages": qualified_count, "semantic_actions": action_count, "passed": passed}))
    quit(0 if passed else 1)
