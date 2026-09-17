extends Node3D

const CUTAWAY_SHELL_TOKENS := [
	"removable camera wall",
	"complete plaster panel",
]
const MAX_IMPORTED_OMNI_ENERGY := 8.0


func _ready() -> void:
	for light in find_children("*", "OmniLight3D", true, false):
		light.light_energy = min(light.light_energy, MAX_IMPORTED_OMNI_ENERGY)
	for mesh in find_children("*", "MeshInstance3D", true, false):
		for token in CUTAWAY_SHELL_TOKENS:
			if mesh.name.contains(token):
				mesh.visible = false
				break
		if mesh.name.contains("Window • pane"):
			_disable_window_emission(mesh)


func _disable_window_emission(mesh: MeshInstance3D) -> void:
	if mesh.mesh == null:
		return
	for surface_index in mesh.mesh.get_surface_count():
		var material := mesh.mesh.surface_get_material(surface_index)
		if material is StandardMaterial3D and material.emission_enabled:
			var adjusted := material.duplicate() as StandardMaterial3D
			adjusted.emission_enabled = false
			adjusted.emission_energy_multiplier = 0.0
			mesh.set_surface_override_material(surface_index, adjusted)
