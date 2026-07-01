extends RefCounted

class_name VisualPatchProvider

var provider_kind := "visual_patch"
var provider_role := "sampling_only"
var heavy_inference_allowed := false
var heavy_scene_scan_allowed := false
var max_samples_per_second := 8

func build_query_input_ref(subject_id: String, camera_pose: Dictionary, target_ref: String = "") -> Dictionary:
	var camera_path := str(camera_pose.get("node_path", ""))
	var runtime_source_ref := "runtime://camera%s/frame/%s" % [camera_path, Time.get_ticks_msec()] if camera_path != "" else "runtime://camera/unresolved/frame/%s" % Time.get_ticks_msec()
	return {
		"provider_kind": provider_kind,
		"ref_id": runtime_source_ref,
		"summary": "actor-local visual patch sample",
		"retention": "debug_artifact" if camera_pose.has("viewport_artifact_ref") else "ref_only",
		"camera_pose": camera_pose,
		"target_ref": target_ref,
		"runtime_source_refs": [runtime_source_ref],
		"artifact_ref": str(camera_pose.get("viewport_artifact_ref", "")),
		"feeds_query_frame": true,
		"provider_role": provider_role,
	}


func build_camera_pose_ref(camera: Camera3D, artifact_ref: String = "") -> Dictionary:
	if camera == null:
		return {
			"node_path": "",
			"runtime_source_ref": "runtime://camera/unresolved",
			"viewport_artifact_ref": artifact_ref,
		}
	return {
		"node_path": str(camera.get_path()),
		"runtime_source_ref": "runtime://camera%s" % str(camera.get_path()),
		"global_position": [camera.global_position.x, camera.global_position.y, camera.global_position.z],
		"global_basis_z": [camera.global_basis.z.x, camera.global_basis.z.y, camera.global_basis.z.z],
		"fov": camera.fov,
		"viewport_artifact_ref": artifact_ref,
	}

func can_sample(now_msec: int, last_sample_msec: int) -> bool:
	var min_interval := int(1000.0 / float(max_samples_per_second))
	return now_msec - last_sample_msec >= min_interval
