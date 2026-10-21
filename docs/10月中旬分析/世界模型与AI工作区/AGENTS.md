# 世界模型与 AI 工作区文档规则

本目录记录“开放世界 3D 运行时作为多模型 AI 工作区”的十月中旬分析。文档状态统一使用 `analysis/planned/non-authorizing`，除非明确标记 `[current]`、`[planned]`、`[deferred]` 或 `[forbidden]`。

## 边界

- 本目录不创建第二套 world truth、event store、clock、scheduler、authority、角色记忆库或物理引擎。
- Backend/既有 domain owner 继续拥有世界真相；Godot 继续拥有本地身体、输入、表现和近场物理；角色智能体继续拥有角色视角、目标和 typed intent。
- 任何 LLM、VLM、VLA、视觉世界模型、隐空间世界模型或世界动作模型都只能通过结构化 adapter 交换数据。
- `model output`、`prediction`、`preview` 和 `proposal` 不等于 `authority commit`。
- 生成的 GLB、场景、碰撞、导航、动作和材质必须经过资产或能力准入，不能因为模型生成就自动进入运行时。

## 文件命名

- `规格/` 只放 architecture spec。
- `计划/` 只放 implementation plan。
- `审查/` 只放当前实现、原始设计、外部研究和本批规格的映射与阻断。
- `回写/` 只登记对十月分析原文的补充、修正和待回写事项。
- 每份实质规格必须包含 Mermaid 架构图、主流程时序图和数据流图，并在图中区分 current/planned/deferred。

## 证据规则

- `[current]` 必须能指向现有代码、测试、Harness profile 或正式运行时文档。
- 外部论文、GitHub、模型主页只能作为 research input，不能作为本仓库运行时完成证据。
- 实施计划必须写明 adapter、输入输出合同、owner、测试、Harness 证据、回滚点和阻断条件。
