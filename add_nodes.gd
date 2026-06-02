extends Node

func _ready():
	# 添加Sprite2D节点
	var sprite = Sprite2D.new()
	sprite.name = "Sprite2D"
	add_child(sprite)

	# 添加Label节点
	var label = Label.new()
	label.name = "HelloLabel"
	label.text = "Hello World"
	add_child(label)

	print("✅ 已添加Sprite2D和Label节点")
