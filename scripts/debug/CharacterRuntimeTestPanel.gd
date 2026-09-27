class_name CharacterRuntimeTestPanel
extends RefCounted

static func inject(proposal: Dictionary, controller: Object) -> Dictionary:
	var bounded := proposal.duplicate(true)
	bounded["source"] = "debug_fixture"
	bounded["correlation_id"] = "debug:%s" % Time.get_ticks_usec()
	bounded["expires_at_tick"] = int(bounded.get("expires_at_tick", 0))
	return controller.submit_intent(bounded)
