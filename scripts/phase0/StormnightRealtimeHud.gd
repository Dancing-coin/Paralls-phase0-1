extends CanvasLayer

class_name StormnightRealtimeHud

var _status: Label
var _phase: Label
var _evidence: Label
var _npc: Label


func _ready() -> void:
	var panel := ColorRect.new()
	panel.color = Color(0.02, 0.03, 0.06, 0.82)
	panel.position = Vector2(18, 18)
	panel.size = Vector2(430, 188)
	add_child(panel)
	var container := VBoxContainer.new()
	container.position = Vector2(16, 14)
	container.size = Vector2(400, 160)
	panel.add_child(container)
	_status = _label("Stormnight: press Enter to start")
	_phase = _label("Phase: not started")
	_evidence = _label("Evidence: none")
	_npc = _label("NPC: waiting")
	for node in [_status, _phase, _evidence, _npc]:
		container.add_child(node)


func show_projection(payload: Dictionary) -> void:
	var projection: Dictionary = payload.get("projection", {})
	_status.text = "Accepted" if bool(payload.get("accepted", false)) else "Rejected: %s" % str(payload.get("error_code", "unknown"))
	_phase.text = "Phase: %s" % str(projection.get("phase_ref", "not started"))
	_evidence.text = "Evidence: %s" % ", ".join(PackedStringArray(projection.get("committed_clue_refs", [])))
	var proposal: Dictionary = payload.get("npc_proposal", {})
	_npc.text = "NPC proposal: %s" % str(proposal.get("proposal_kind", "waiting"))


func show_pending(label: String) -> void:
	_status.text = "Requesting: %s" % label


func _label(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 16)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return label
