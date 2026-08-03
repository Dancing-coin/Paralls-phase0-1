extends RefCounted

class_name DefaultSceneActionAtomCatalog


## Reviewed local realization inventory for the default-scene reference path.
## This supplies descriptors to CharacterEmbodimentAssetRegistry; it is not a
## second lookup service and it has no authority or scene-state responsibilities.
static func reviewed_entries() -> Array[Dictionary]:
	return [
		{
			"reviewed": true,
			"controller_phase": "plan_approach",
			"registration_keys": ["start_move", "begin_locomotion"],
			"descriptor": {
				"action_tag": "start_move",
				"animation_clip_ref": "walk_guard",
				"root_motion_profile": "navigation_owned",
			},
		},
		{
			"reviewed": true,
			"controller_phase": "align",
			"registration_keys": ["turn_to_target", "look_at_target", "orient_to_space"],
			"descriptor": {
				"action_tag": "turn_to_target",
				"animation_clip_ref": "observe_watch",
				"root_motion_profile": "align_local_only",
			},
		},
		{
			"reviewed": true,
			"controller_phase": "prepare",
			"registration_keys": ["raise_hand", "focus_attention"],
			"descriptor": {
				"action_tag": "raise_hand",
				"animation_clip_ref": "inspect_relic",
				"root_motion_profile": "upper_body_local_only",
			},
		},
		{
			"reviewed": true,
			"controller_phase": "execute_contact",
			"registration_keys": ["tap_contact", "inspect_contact"],
			"descriptor": {
				"action_tag": "tap_contact",
				"animation_clip_ref": "inspect_relic",
				"root_motion_profile": "contact_local_only",
			},
		},
		{
			"reviewed": true,
			"controller_phase": "recover",
			"registration_keys": ["recover_balance", "return_idle"],
			"descriptor": {
				"action_tag": "recover_balance",
				"animation_clip_ref": "idle_guard",
				"root_motion_profile": "recovery_local_only",
			},
		},
	]


static func register_into(action_asset_registry: CharacterEmbodimentAssetRegistry) -> Dictionary:
	if action_asset_registry == null:
		return {"status": "action_assets_unavailable", "missing_action_keys": ["registry"]}
	return action_asset_registry.register_reviewed_action_catalog(reviewed_entries())
