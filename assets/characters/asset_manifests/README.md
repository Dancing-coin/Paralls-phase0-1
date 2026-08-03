# 角色表现资产清单

本目录用 YAML 管理角色资产索引，用 JSON 管理 Godot 可消费的表现绑定。它们
不由角色智能体、世界权威或 Siming 直接读取。

每个清单至少应覆盖：

- 角色模型、骨架绑定与兼容级别
- 服装、装备与手持道具槽位
- 动作、表情和动画语义
- 受控声线源资产引用与已批准 TTS 绑定引用

实际 GLB、贴图、材质、服装网格、道具网格和动画文件仍归入
`assets/artpacks/<资源包ID>/`。清单只保存稳定 ID、资源引用和绑定说明，以便
模型替换时维持 `actor_id`、运行时壳和业务协议稳定。

`char_a.example.yaml` 是资产档案格式示例。
`character_presentation_bindings.example.json` 是 Godot 运行时绑定示例，必须复制
所需条目到 `character_presentation_bindings.json`，并在验证完成后才将
`binding_status` 改为 `approved`。空白的正式清单不会改变当前运行时。

完整填写、验证和回退规则见 [自动应用流程](自动应用流程.md)。
