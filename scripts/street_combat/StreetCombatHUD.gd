extends CanvasLayer

@onready var coordinator: Node = get_parent().get_node("CombatCoordinator")
@onready var status: Label = $ScoreStrip/Status
@onready var feed: Label = $CombatFeed/Feed
@onready var target: Label = $TargetCard/Target
@onready var distance: Label = $TargetCard/Distance
@onready var action: Label = $PlayerCard/Action
@onready var health_fill: ColorRect = $PlayerCard/HealthTrack/HealthFill
@onready var health_value: Label = $PlayerCard/HealthValue
@onready var stamina_fill: ColorRect = $StaminaBar/StaminaTrack/StaminaFill
@onready var stamina_value: Label = $StaminaBar/StaminaValue
@onready var agents: Label = $Agents
@onready var camera: Camera3D = get_parent().get_node("FollowCamera")
@onready var jk_marker: Control = $JKMarker
@onready var t_marker: Control = $TMarker
@onready var timer: Label = $ScoreStrip/Center

const ACTOR_NODES := {
	"street_bandage": "../PlayerCharacter",
	"char_a": "../AgentCharacterJK",
	"char_b": "../AgentCharacterT",
}
const ACTOR_NAMES := {
	"street_bandage": "BANDAGE",
	"char_a": "JK",
	"char_b": "T",
}
const MAX_HP := 100.0
const HEALTH_TRACK_WIDTH := 180.0
const STAMINA_TRACK_WIDTH := 237.0
const BASE_VIEWPORT := Vector2(1152.0, 648.0)
var _started_at_ms := 0

func _ready() -> void:
	_started_at_ms = Time.get_ticks_msec()
	get_viewport().size_changed.connect(_layout_to_viewport)
	_layout_to_viewport()
	$TargetCard.visible = false
	coordinator.state_changed.connect(_refresh)
	_refresh()


func _layout_to_viewport() -> void:
	var viewport_size := get_viewport().get_visible_rect().size
	var width := viewport_size.x
	var height := viewport_size.y
	var ui_scale := clampf(minf(width / BASE_VIEWPORT.x, height / BASE_VIEWPORT.y), 0.9, 1.35)
	$ScoreStrip.size = Vector2(width, 78.0)
	$ScoreStrip/TopPill.position = Vector2(width * 0.5 - 160.0, 5.0)
	$ScoreStrip/Center.position = Vector2(width * 0.5 - 140.0, 35.0)
	$ScoreStrip/Center.size = Vector2(280.0, 27.0)
	$ScoreStrip/Round.position = Vector2(width * 0.5 - 140.0, 9.0)
	$ScoreStrip/Round.size = Vector2(280.0, 26.0)
	$ScoreStrip/Status.position = Vector2(28.0, 19.0)
	$MiniMap.position = Vector2(width - 210.0, 22.0)
	$CombatFeed.position = Vector2(24.0, 92.0)
	$TargetCard.position = Vector2(width - 326.0, 274.0)
	$PlayerCard.position = Vector2(24.0, height - 156.0)
	$StaminaBar.position = Vector2(width * 0.5 - 130.0, height - 112.0)
	$SkillBar.position = Vector2(width - 326.0, height - 136.0)
	for node: Control in [$ScoreStrip/TopPill, $MiniMap, $CombatFeed, $TargetCard, $PlayerCard, $StaminaBar, $SkillBar]:
		node.scale = Vector2(ui_scale, ui_scale)

func _process(_delta: float) -> void:
	_refresh()

func _refresh() -> void:
	status.text = "● 后端已连接" if coordinator.connected else "● 后端未连接"
	status.modulate = Color(0.45, 0.92, 0.79) if coordinator.connected else Color(0.98, 0.45, 0.38)
	var visible_events: Array[String] = []
	for entry: String in coordinator.event_feed:
		if entry.begins_with("Backend"):
			continue
		visible_events.append(entry)
		if visible_events.size() == 3:
			break
	$CombatFeed.visible = coordinator.connected and not visible_events.is_empty()
	feed.text = "\n".join(visible_events)
	var elapsed_seconds := (Time.get_ticks_msec() - _started_at_ms) / 1000
	timer.text = "%02d:%02d" % [elapsed_seconds / 60, elapsed_seconds % 60]
	_refresh_player()
	_refresh_target()
	_refresh_agents()
	_refresh_marker(jk_marker, "char_a")
	_refresh_marker(t_marker, "char_b")

func _refresh_player() -> void:
	var hp := clampf(float(coordinator.actor_hp.get("street_bandage", MAX_HP)), 0.0, MAX_HP)
	health_fill.size.x = HEALTH_TRACK_WIDTH * hp / MAX_HP
	health_value.text = "%03d/100" % int(hp)
	var stamina := clampf(float(coordinator.actor_stamina.get("street_bandage", 100)), 0.0, 100.0)
	stamina_fill.size.x = STAMINA_TRACK_WIDTH * stamina / 100.0
	stamina_value.text = "%d/100" % int(stamina)
	var player := get_node_or_null(str(ACTOR_NODES["street_bandage"]))
	var clip := "idle"
	if player != null:
		var skin := player.get_node_or_null("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin")
		if skin != null and skin.has_method("get_current_clip_name"):
			clip = str(skin.get_current_clip_name()).get_file()
	var clip_name := clip.to_lower()
	var display := "剑击" if clip_name.contains("sword attack") else "拳击" if clip_name.contains("boxing") else "跳跃" if clip_name.contains("jump") else "奔跑" if clip_name.contains("running") else "步行" if clip_name.contains("walking") else "待机"
	action.text = "当前动作 · %s" % display

func _refresh_target() -> void:
	var target_id := str(coordinator.target_actor_id)
	var target_hp := int(coordinator.actor_hp.get(target_id, MAX_HP))
	target.text = "%s  ·  HP %03d" % [str(ACTOR_NAMES.get(target_id, "目标")), target_hp]
	var player := get_node_or_null(str(ACTOR_NODES["street_bandage"])) as Node3D
	var target_actor := get_node_or_null(str(ACTOR_NODES.get(target_id, ""))) as Node3D
	var meters := player.global_position.distance_to(target_actor.global_position) if player != null and target_actor != null else -1.0
	distance.text = "距离  %.1f m  ·  TAB 切换" % meters if meters >= 0.0 else "距离  --  ·  TAB 切换"

func _refresh_agents() -> void:
	var jk_action := str(coordinator.agent_intents.get("char_a", "idle")).trim_prefix("action:")
	var t_action := str(coordinator.agent_intents.get("char_b", "idle")).trim_prefix("action:")
	agents.text = "JK  AGENT  ·  %s      T  AGENT  ·  %s" % [jk_action, t_action]


func _refresh_marker(marker: Control, actor_id: String) -> void:
	var actor := get_node_or_null(str(ACTOR_NODES[actor_id])) as Node3D
	if actor == null or camera == null:
		marker.visible = false
		return
	var world_position := actor.global_position + Vector3(0.0, 1.8, 0.0)
	if camera.is_position_behind(world_position):
		marker.visible = false
		return
	var screen := camera.unproject_position(world_position)
	var viewport_size := get_viewport().get_visible_rect().size
	marker.visible = screen.x >= 0.0 and screen.x <= viewport_size.x and screen.y >= 0.0 and screen.y <= viewport_size.y
	marker.position = screen - Vector2(90.0, 38.0)
	var fill := marker.get_node("HealthTrack/HealthFill") as ColorRect
	fill.size.x = 160.0 * clampf(float(coordinator.actor_hp.get(actor_id, 100)), 0.0, 100.0) / 100.0
	fill.color = Color(1.0, 0.7, 0.28) if coordinator.target_actor_id == actor_id else Color(0.18, 0.81, 0.93)
	var name_label := marker.get_node("Name") as Label
	var player := get_node_or_null(str(ACTOR_NODES["street_bandage"])) as Node3D
	var distance_m := player.global_position.distance_to(actor.global_position) if player != null else -1.0
	name_label.text = "◈ %s  %.1fm" % [str(ACTOR_NAMES[actor_id]), distance_m] if coordinator.target_actor_id == actor_id and distance_m >= 0.0 else str(ACTOR_NAMES[actor_id])
	name_label.add_theme_color_override("font_color", Color(1.0, 0.8, 0.38) if coordinator.target_actor_id == actor_id else Color(0.9, 0.98, 1.0))
	var ring := marker.get_node_or_null("Ring") as Panel
	if ring != null:
		ring.modulate = Color(1.0, 0.72, 0.24, 0.95) if coordinator.target_actor_id == actor_id else Color(0.18, 0.85, 1.0, 0.8)
