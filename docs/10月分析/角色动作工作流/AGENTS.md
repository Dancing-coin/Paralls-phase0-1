# 角色动作工作流文档规则

本目录继承仓库根目录 `AGENTS.md`。文档属于十月分析材料，默认是 `analysis/planned/non-authorizing`，不直接授权运行时、Godot、Blender 或 WebApp 实现。

每份实质设计必须：

- 区分 `[current]`、`[planned]`、`[deferred]`；
- 包含架构图、主流程时序图和数据流图；
- 明确 SkeletonProfile、RigDescriptor、RigBinding、ActionLibrary 与 AD 中介骨架的关系；
- 区分浏览器预览、Blender 正式烘焙和正式动作库登记；
- 不把 GLB、Blend、MP4、纹理、模型或其他生成素材写入仓库。

本目录不定义后端 authority，也不替代 `docs/superpowers/specs/` 下的正式实现规格。涉及统一动作库的内容必须链接现有中央动作库阶段 1–3 设计与验证入口。
