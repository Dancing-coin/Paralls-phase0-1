extends Node

class_name CharacterRuntimeFeedback

@onready var nameplate: Label3D = $"../Nameplate"

var combat_feedback_timer := 0.0
var combat_feedback_text := ""

func show_combat_feedback(text: String) -> void:
	combat_feedback_text = text
	combat_feedback_timer = 0.6

func tick(delta: float, actor_id: String, attention_active: bool, environment_attention: bool, source_visual_fact: bool, focus_visual_active: bool) -> void:
	if combat_feedback_timer > 0.0:
		combat_feedback_timer = max(combat_feedback_timer - delta, 0.0)
		if combat_feedback_timer <= 0.0:
			combat_feedback_text = ""
	update_nameplate(actor_id, attention_active, environment_attention, source_visual_fact, focus_visual_active)

func update_nameplate(actor_id: String, attention_active: bool, environment_attention: bool, source_visual_fact: bool, focus_visual_active: bool) -> void:
	if nameplate == null:
		return
	if combat_feedback_timer > 0.0:
		nameplate.text = "%s %s" % [actor_id.to_upper(), combat_feedback_text]
		nameplate.modulate = Color(1.0, 0.35, 0.25, 1.0) if combat_feedback_text == "SWING" else Color(0.3, 0.8, 1.0, 1.0)
		return
	if not attention_active:
		nameplate.text = actor_id.to_upper()
		nameplate.modulate = Color(1.0, 1.0, 1.0, 1.0)
		return
	if environment_attention and not focus_visual_active:
		nameplate.text = "%s ?" % actor_id.to_upper()
		nameplate.modulate = Color(1.0, 0.62, 0.28, 1.0)
		return
	if source_visual_fact and not focus_visual_active:
		nameplate.text = "%s ~" % actor_id.to_upper()
		nameplate.modulate = Color(0.55, 0.92, 1.0, 1.0)
		return
	nameplate.text = "%s !" % actor_id.to_upper()
	nameplate.modulate = Color(1.0, 0.92, 0.45, 1.0)
