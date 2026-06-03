extends AudioStreamPlayer3D

func play_stub_voice(_payload: Dictionary) -> void:
    unit_size = 3.0
    max_distance = 15.0
    _bus_log("voice_stub_played:%s" % str(_payload.get("actor_id", "")))

func _bus_log(message: String) -> void:
    var bus := get_node_or_null("/root/LocalPresentationBus")
    if bus and bus.has_method("log_debug"):
        bus.log_debug(message)
