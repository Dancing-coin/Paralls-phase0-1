extends RefCounted

class_name ThroneRoomLightingTuner

const BLUE_LIGHT_NAMES := [
	"PointLight142",
	"PointLight82",
	"PointLight72",
	"PointLight62",
	"PointLight23",
	"SpotLight602",
	"SpotLight582",
	"SpotLight562",
	"SpotLight423",
	"SpotLight32",
	"SpotLight22",
	"SpotLight42",
	"PointLight172",
	"PointLight252",
	"PointLight142",
]

const EMISSIVE_MATERIAL_NAMES := {
	"MI_Lamps01": 0.18,
	"MI_Lamps02": 0.18,
	"MI_Lamps03": 0.18,
	"MI_Lamps04": 0.18,
	"MI_Chandelier": 0.22,
	"MI_LargeWall01": 0.28,
}

const FABRIC_BACKLIGHT_MATERIALS := {
	"MI_HallFabric01": {"emission": Color(0.62, 0.12, 0.08, 1.0), "energy": 0.38},
	"MI_FabricAnim02": {"emission": Color(0.58, 0.1, 0.07, 1.0), "energy": 0.32},
	"MI_Curtain01": {"emission": Color(0.44, 0.08, 0.05, 1.0), "energy": 0.22}
}

const WARM_BALANCE := Color(0.92, 0.87, 0.78, 1.0)
const COOL_LIGHT_BLEND := 0.72
const OMNI_LIGHT_ENERGY_MULTIPLIER := 0.055
const SPOT_LIGHT_ENERGY_MULTIPLIER := 0.075
const DIRECTIONAL_TARGET_ENERGY := 0.22
const BLUE_LIGHT_ENERGY_MULTIPLIER := 0.1
const LIGHT_SPECULAR_SCALE := 0.55

static func apply_blender_approx(root: Node) -> void:
	if root == null:
		return
	if root.has_meta("blender_approx_lighting_applied"):
		return
	root.set_meta("blender_approx_lighting_applied", true)

	var debug_enabled := OS.get_environment("THRONE_LIGHTING_DEBUG") == "1"
	var scaled_lights := _scale_all_lights(root)
	var warmed_lights := _warm_cool_lights(root)
	var tuned_materials := _tune_emissive_materials(root, debug_enabled)
	var tuned_fabrics := _tune_fabric_backlight(root)

	var directional := root.find_child("DirectionalLight2", true, false)
	if directional is DirectionalLight3D:
		(directional as DirectionalLight3D).light_energy = DIRECTIONAL_TARGET_ENERGY

	for light_name in BLUE_LIGHT_NAMES:
		var candidate := root.find_child(light_name, true, false)
		if candidate is Light3D:
			var light := candidate as Light3D
			light.light_color = WARM_BALANCE
			light.light_energy *= BLUE_LIGHT_ENERGY_MULTIPLIER

	if debug_enabled:
		print("throne_lighting_tuner scaled_lights=%s warmed_lights=%s tuned_materials=%s tuned_fabrics=%s" % [scaled_lights, warmed_lights, tuned_materials, tuned_fabrics])

static func _scale_all_lights(root: Node) -> int:
	var count := 0
	for child in root.find_children("*", "", true, false):
		if child is Light3D:
			var light := child as Light3D
			if light is OmniLight3D:
				light.light_energy *= OMNI_LIGHT_ENERGY_MULTIPLIER
			elif light is SpotLight3D:
				light.light_energy *= SPOT_LIGHT_ENERGY_MULTIPLIER
			elif light is DirectionalLight3D:
				light.light_energy = min(light.light_energy, DIRECTIONAL_TARGET_ENERGY)
			if "light_specular" in light:
				light.light_specular *= LIGHT_SPECULAR_SCALE
			count += 1
	return count

static func _warm_cool_lights(root: Node) -> int:
	var count := 0
	for child in root.find_children("*", "", true, false):
		if not (child is Light3D):
			continue
		var light := child as Light3D
		if light.light_color.b <= light.light_color.r and light.light_color.b <= light.light_color.g:
			continue
		light.light_color = light.light_color.lerp(WARM_BALANCE, COOL_LIGHT_BLEND)
		count += 1
	return count

static func _tune_emissive_materials(root: Node, debug_enabled: bool) -> int:
	var count := 0
	for child in root.find_children("*", "", true, false):
		if not (child is MeshInstance3D):
			continue
		var mesh_instance := child as MeshInstance3D
		if mesh_instance.mesh == null:
			continue
		var surface_count := mesh_instance.mesh.get_surface_count()
		for surface_index in range(surface_count):
			var material := mesh_instance.get_active_material(surface_index)
			if material == null:
				continue
			if not (material is BaseMaterial3D):
				if debug_enabled and surface_index == 0:
					print("throne_lighting_tuner skip_non_base_material node=%s material_type=%s" % [mesh_instance.name, material.get_class()])
				continue
			var base_material := material as BaseMaterial3D
			var factor := _emissive_factor_for_material(base_material.resource_name)
			if factor >= 1.0:
				continue
			var tuned := base_material.duplicate() as BaseMaterial3D
			if tuned == null:
				continue
			if "emission_energy_multiplier" in tuned:
				if debug_enabled:
					print("throne_lighting_tuner tune_material node=%s material=%s emission_before=%s factor=%s" % [mesh_instance.name, tuned.resource_name, tuned.emission_energy_multiplier, factor])
				tuned.emission_energy_multiplier *= factor
			mesh_instance.set_surface_override_material(surface_index, tuned)
			count += 1
	return count

static func _tune_fabric_backlight(root: Node) -> int:
	var count := 0
	for child in root.find_children("*", "", true, false):
		if not (child is MeshInstance3D):
			continue
		var mesh_instance := child as MeshInstance3D
		if mesh_instance.mesh == null:
			continue
		var surface_count := mesh_instance.mesh.get_surface_count()
		for surface_index in range(surface_count):
			var material := mesh_instance.get_active_material(surface_index)
			if not (material is BaseMaterial3D):
				continue
			var base_material := material as BaseMaterial3D
			if not FABRIC_BACKLIGHT_MATERIALS.has(base_material.resource_name):
				continue
			var tuned := base_material.duplicate() as BaseMaterial3D
			if tuned == null:
				continue
			var config: Dictionary = FABRIC_BACKLIGHT_MATERIALS[base_material.resource_name]
			tuned.emission_enabled = true
			tuned.emission = config["emission"]
			if "emission_energy_multiplier" in tuned:
				tuned.emission_energy_multiplier = float(config["energy"])
			tuned.disable_ambient_light = false
			tuned.cull_mode = BaseMaterial3D.CULL_DISABLED
			mesh_instance.set_surface_override_material(surface_index, tuned)
			count += 1
	return count

static func _emissive_factor_for_material(material_name: String) -> float:
	if EMISSIVE_MATERIAL_NAMES.has(material_name):
		return EMISSIVE_MATERIAL_NAMES[material_name]
	return 1.0
