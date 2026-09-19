extends Node3D
class_name PopulationPresenter

## 只显示已确认的公开人口投影；距离分档不参与后端仿真。
const MAX_VISIBLE := 160
const MAX_NEAR := 32

var authorized_population := 0
var latest_confirmed_tick := 0
var latest_revision := ""
var applied_count := 0
var _markers: Dictionary = {}
var _near_labels: Dictionary = {}
var _materials: Dictionary = {}
var _near_mesh := CapsuleMesh.new()
var _far_mesh := BoxMesh.new()
var _lod_dirty := true
var _camera_position := Vector3.INF


func _ready() -> void:
	_near_mesh.radius = 0.25
	_near_mesh.height = 1.1
	_far_mesh.size = Vector3(0.35, 0.7, 0.35)
	for tag: String in ["idle", "rest", "work"]:
		var material := StandardMaterial3D.new()
		material.albedo_color = {"idle": Color("63b3ed"), "rest": Color("a78bfa"), "work": Color("f6c85f")}[tag]
		_materials[tag] = material


func set_population(snapshot_or_delta: Dictionary) -> void:
	# 输入来自 adapter 的已验证完整快照，delta 已由共享 consumer 物化。
	var actor_ref: String = snapshot_or_delta["actor_ref"]
	var public: Dictionary = snapshot_or_delta["groups"]["population_public"]["payload"]
	var marker: MeshInstance3D = _markers.get(actor_ref)
	if marker == null:
		if _markers.size() >= MAX_VISIBLE:
			return
		marker = MeshInstance3D.new()
		marker.mesh = _far_mesh
		add_child(marker)
		_markers[actor_ref] = marker
	var point: Array = public["presentation_position"]
	marker.position = Vector3(float(point[0]), float(point[1]) + 0.55, float(point[2]))
	marker.material_override = _materials[public["animation_tag"]]
	marker.set_meta("public_view", public.duplicate(true))
	latest_confirmed_tick = int(public["confirmed_tick"])
	latest_revision = str(snapshot_or_delta["facade_revision"])
	applied_count += 1
	_lod_dirty = true


func remove_actor(actor_ref: String) -> void:
	_remove_label(actor_ref)
	var marker: MeshInstance3D = _markers.get(actor_ref)
	_markers.erase(actor_ref)
	if marker != null:
		# 先从树中移除，延迟释放期间也不能短暂显示两倍人口。
		remove_child(marker)
		marker.queue_free()
	_lod_dirty = true


func clear_population() -> void:
	for actor_ref: String in _markers.keys():
		remove_actor(actor_ref)
	authorized_population = 0
	latest_confirmed_tick = 0
	latest_revision = ""


func counts() -> Dictionary:
	return {"near": _near_labels.size(), "far": _markers.size() - _near_labels.size(),
		"invisible": maxi(0, authorized_population - _markers.size()), "active_marker_count": _markers.size()}


func _process(_delta: float) -> void:
	var camera := get_viewport().get_camera_3d()
	if camera == null:
		return
	var next_position := camera.global_position
	if not _lod_dirty and next_position.is_equal_approx(_camera_position):
		return
	_camera_position = next_position
	_lod_dirty = false
	# ponytail: 最多160个兴趣成员排序；只有实测这里成为热点才需要空间索引。
	var actors: Array = _markers.keys()
	actors.sort_custom(func(left: String, right: String):
		var a: float = (_markers[left] as Node3D).global_position.distance_squared_to(next_position)
		var b: float = (_markers[right] as Node3D).global_position.distance_squared_to(next_position)
		return left < right if a == b else a < b)
	var near_actors: Array = actors.slice(0, MAX_NEAR)
	# 先降级旧 near，之后创建任一新 near 时也不超过32个节点/mesh。
	for actor_ref: String in _near_labels.keys():
		if not near_actors.has(actor_ref):
			(_markers[actor_ref] as MeshInstance3D).mesh = _far_mesh
			_remove_label(actor_ref)
	for actor_ref: String in near_actors:
		var marker: MeshInstance3D = _markers[actor_ref]
		marker.mesh = _near_mesh
		var label: Label3D = _near_labels.get(actor_ref)
		if label == null:
			label = Label3D.new()
			label.font_size = 24
			label.pixel_size = 0.006
			label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			marker.add_child(label)
			label.position.y = 0.8
			_near_labels[actor_ref] = label
		var public: Dictionary = marker.get_meta("public_view")
		label.text = "%s · %d" % [public["actor_id"], int(public["confirmed_tick"])]


func _remove_label(actor_ref: String) -> void:
	var label: Label3D = _near_labels.get(actor_ref)
	_near_labels.erase(actor_ref)
	if label != null:
		label.get_parent().remove_child(label)
		label.queue_free()
