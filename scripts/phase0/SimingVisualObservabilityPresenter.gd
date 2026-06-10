extends Node

var applied_fact_ids: Array[String] = []

func _ready() -> void:
    var bus := _get_bus()
    if bus and bus.has_signal("siming_visual_observability_requested"):
        bus.siming_visual_observability_requested.connect(_on_siming_visual_observability_requested)

func _on_siming_visual_observability_requested(event: Dictionary) -> void:
    var payload: Dictionary = event.get("payload", {})
    var established_fact_id := str(payload.get("established_fact_id", ""))
    if established_fact_id.is_empty():
        _bus_log("siming_visual_observability_rejected:missing_established_fact_id")
        return

    applied_fact_ids.append(established_fact_id)
    var presentation_hint := str(payload.get("presentation_hint", ""))
    _bus_log("siming_visual_observability_applied:%s:%s" % [established_fact_id, presentation_hint])

func _get_bus() -> Node:
    return get_node_or_null("/root/LocalPresentationBus")

func _bus_log(message: String) -> void:
    var bus := _get_bus()
    if bus and bus.has_method("log_debug"):
        bus.log_debug(message)
