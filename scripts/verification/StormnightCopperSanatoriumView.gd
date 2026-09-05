extends Node

class_name StormnightCopperSanatoriumView

const VOICE_TEMPLATES := {
	"preparing": "调查即将开始。",
	"clue_found": "发现了新的证据。",
	"statement_conflict": "证言与已知事实存在矛盾。",
	"detected": "你已被发现。",
	"captured": "你已被控制。",
	"escaped": "你已成功脱离追捕。",
	"solved": "案件已解决。",
	"returned": "已恢复最近一次确认状态。",
	"rejected": "行动被拒绝，临时状态已清除。",
}

var committed_projection: Dictionary = {}
var speculative_projection: Dictionary = {}
var voice_state := "returned"


func apply_committed_projection(projection: Dictionary) -> void:
	committed_projection = projection.duplicate(true)
	speculative_projection.clear()
	voice_state = str(committed_projection.get("voice_state", "returned"))
	if not VOICE_TEMPLATES.has(voice_state):
		voice_state = "returned"


func apply_speculative_projection(projection: Dictionary) -> void:
	speculative_projection = projection.duplicate(true)


func reject_speculative_state(reason: String = "authority_rejected") -> Dictionary:
	speculative_projection.clear()
	voice_state = "rejected"
	return {"accepted": false, "reason": reason, "speculative_state_cleared": true}


func read_only_panel_state() -> Dictionary:
	return {
		"phase": committed_projection.get("phase_ref", ""),
		"clues": committed_projection.get("committed_clue_refs", []),
		"private_knowledge": committed_projection.get("private_fact_refs", []),
		"pursuit": committed_projection.get("pursuit", "none"),
		"accusation": committed_projection.get("accusation_status", "none"),
		"terminal_outcome": committed_projection.get("terminal_outcome", "none"),
		"voice_state": voice_state,
		"voice_template": VOICE_TEMPLATES[voice_state],
	}
