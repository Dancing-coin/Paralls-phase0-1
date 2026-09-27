class_name CharacterRuntimeDebugOverlay
extends Node

var selected_snapshot: Dictionary = {}

func update_snapshot(snapshot: Dictionary) -> void:
	selected_snapshot = snapshot.duplicate(true)
