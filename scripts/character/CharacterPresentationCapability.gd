extends RefCounted
class_name CharacterPresentationCapability

static func normalize(raw: Dictionary) -> Dictionary:
    var refs: Array[StringName] = []
    var values: Variant = raw.get("capability_refs", raw.get("capabilities", []))
    if values is Array:
        for value in values:
            var ref := StringName(str(value))
            if not String(ref).is_empty() and not refs.has(ref):
                refs.append(ref)
    return {"capability_refs": refs, "root_motion_policy": StringName(str(raw.get("root_motion_policy", "hold"))), "qualified": bool(raw.get("qualified", false))}

static func admits_drive_locomotion(profile: Dictionary) -> bool:
    return bool(profile.get("qualified", false)) and str(profile.get("root_motion_policy", "hold")) == "drive_locomotion"
