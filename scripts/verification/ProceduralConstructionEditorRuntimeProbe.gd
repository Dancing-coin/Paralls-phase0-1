extends Node

func _ready() -> void:
	var scene := load("res://scenes/phase0/ProceduralConstructionEditor.tscn")
	if scene == null:
		get_tree().quit(1)
		return
	var editor = scene.instantiate()
	add_child(editor)
	if not editor.preview_placement(Vector2i(0, 0), Vector2i(2, 1), 0):
		get_tree().quit(2)
		return
	var draft: Dictionary = editor.build_typed_draft("blueprint:probe@1", Vector2i(0, 0), Vector2i(2, 1), 0)
	if draft.get("orientation") != 0 or draft.get("footprint", {}).get("width") != 2:
		get_tree().quit(3)
		return
	editor.apply_backend_projection({"occupied_cells": [[2, 2]]})
	if not editor.speculative_cells.is_empty() or not editor.committed_cells.has(Vector2i(2, 2)):
		get_tree().quit(4)
		return
	editor.preview_placement(Vector2i(3, 3), Vector2i(1, 1), 0)
	editor.reject_backend_intent("probe-rejected")
	if not editor.speculative_cells.is_empty():
		get_tree().quit(5)
		return
	get_tree().quit(0)
