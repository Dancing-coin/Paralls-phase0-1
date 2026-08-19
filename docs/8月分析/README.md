# 线程主题分析索引

状态：`incremental guidance index; does not authorize implementation independently of formal spec/plan`

- 整理日期：2026-08-12
- 性质：基于现有实现的增量设计指导、架构判断与后续决策材料
- 事实约束：本文档不替代正式 spec、plan、代码和 Harness 报告；“当前实现”以仓库代码和 `.harness/verification/` 为准
- 体系分离：分析材料从 [分析与设计指导](分析与设计指导/README.md) 进入；阶段安排从 [阶段推进](阶段推进/README.md) 进入
- 实现收口：完整的逐文件实现映射见 [12-实现收口与证据映射.md](12-实现收口与证据映射.md)，该页记录了 2026-08-12 的验证基线和未完成边界
- 适用范围：本线程从通用智能体游戏底座、RPG 玩法、VLA/世界模型、呈现形态、创作者工具、算力复用、经济系统和闭源核心保护展开的全部讨论

## 权威边界

本目录是基于当前实现的增量设计指导、架构判断和决策材料，不是脱离仓库现实另起的执行面。发生冲突时，依次以：

1. 当前线程中的明确用户指令；
2. `docs/superpowers/specs/world-character-siming-authority-mainline/`；
3. `docs/superpowers/plans/world-character-siming-authority-mainline/`；
4. 代码、测试和 `.harness/verification/` 证据；

为准。本目录应持续把已有 owner、事件模型和验证证据带入后续设计；新增 owner、数据模型、优先级或控制面需要与正式 spec/plan 同步后，才能成为实现授权或执行顺序。

本目录提到的 `World Record Authority`、`Semantic Registry Authority`、`Settlement/Scheduler Authority`、
`ActiveWorldRevision`、`CreatorControlPlane` 等，如仓库尚无同名正式模块，一律视为 `planned`
逻辑边界。它们当前只能通过既有入口延展：`backend/app/world_runtime/*`、ESM、`raw_fact_event`
链、现有 Gameplay Authority、`GameplayEventStore.append_batch`、Patch/runtime 生命周期，以及现有
`/ws` 镜像 scope/投影路径。

## 两套体系

### 分析与设计指导

进入 [分析与设计指导/README.md](分析与设计指导/README.md)。这里集中放长期主题分析、领域增量指导、全域架构、创作运营设计、架构审计和实现映射。它回答“为什么”和“还缺什么”。

### 阶段推进

进入 [阶段推进/README.md](阶段推进/README.md)。这里集中放第一至第七阶段，以及 P5 后能力基础推进。它回答“先做什么、依赖什么、怎样验收”。

阶段推进文档不得替代领域设计指导；领域分析文档也不得单独授权实现。两套体系通过 formal spec/plan 和 Harness 证据衔接。

## 主题地图

### 新增主线修订工作区

[司命与群体世界补充设计](司命与群体世界补充设计/README.md) 是 2026-08-17 起草的未来主线修订候选：它按受控司命能力、知识图谱/记忆、群体连续性、真相到表现投影和性能证据拆分。该工作区当前全部为 `proposed`，必须在 matching `superpowers/specs`、plans、RED tests 和 Harness 通过后才可授权实现；它可以替代尚未执行的旧设计，但不会改写已验证历史证据。

| 文件 | 主题 | 核心问题 |
| --- | --- | --- |
| 00 | 增量工作台 | 对话概念如何落回既有 owner、正式 spec/plan 与 Harness 证据 |
| 01 | 产品定位与边界 | 项目现在究竟是什么，能不能直接成为完整 RPG |
| 02 | 角色核心 | 角色档案、运行态、心智、玩法状态如何分层，哪些应成为闭源核心 |
| 03 | 玩法与经济 | 玩法基础有哪些，经济如何与技能、背包、建造、生存、组织协作 |
| 04 | 世界模型与 VLA | AI 游戏和机器人沙盒能否共享同一套 harness |
| 05 | 多形态呈现 | 3D、VRM、2D、Live2D、VR 手套如何共享智能体而不强行共享表现层 |
| 06 | 创作者与 Codex | 创作者需要什么工具，如何让 Codex 直接控制底座，以及生态如何经营 |
| 07 | 算力与记忆 | 单局成本在哪里，如何通过小模型、记忆压缩和结果复用降低成本 |
| 08 | 产品路线 | 需要多少种底座，先做哪一个，如何从 RPG 走向通用智能体底座 |
| 09 | 决策清单 | 本线程最终沉淀出的架构原则和待办优先级 |
| 10 | 创作者权限 | `reader/editor/admin` 如何统一约束 UI、CLI、MCP 与闭源核心 |
| 11 | 全面闭源保护 | 跨角色、玩法、权威、Siming、客户端和部署的闭源保护矩阵 |
| 12 | 全域架构与分域导航 | 以 canonical owner 划分既有世界基础设施、角色与社会投影、分层玩法与创作运营 |
| 第一阶段推进 | 通用基础契约、V0 内部测试、Econ-1 完整参考游戏、异质样板与证据门禁 | 如何从当前 Gameplay Foundation 收口可泛化的第一组玩法契约 |
| 第二阶段推进 | 已有角色的多智能体组织协作、工作意图、经营窗口、工资证据与参考包门禁 | 如何在不创建 NPC 生态或平行 runtime 的前提下接入多个 CharacterAgent |
| 第三阶段推进 | Population Simulation、世界消费模式、角色激活、批量意图与连续性合并 | 如何让社会角色持续运行而不创建影子 NPC 状态 |
| 第四阶段推进 | 动态报价、跨组织结算、政府监管、有限信用和商业生态 | 如何扩展固定 quote 而不另建市场或金融真相系统 |
| 第五阶段推进 | 任务、证据、关系、知识、调查、潜行与冲突 | 如何在既有 Character Core 和 Gameplay authority 上形成 RPG 闭环 |
| P5后续能力基础推进 | 证据基线、语义规则、社会知识隐私、玩法包治理与验证门禁 | 如何为 P6、再为 P7 提供共享前置 |
| 第六阶段推进 | 创作者权限、UI/CLI/MCP 对齐、玩法包、激活、发布和回滚 | 如何开放创作而不暴露闭源 writer 或生产事实 |
| 第七阶段推进 | 文明能力、跨辖区、分支推演、世界模型和机器人安全 | 如何扩展世界规模而不让模型/研究客户端成为 authority |

## 总结判断

当前项目已经有：

- 角色心智核心的 L1-L4 主链、五池记忆、需求/情绪/目标运行态；
- Gameplay authority、事件溯源、回放、资源、状态、能力、背包、装备、产权与固定经济原语；
- 具身交互、结构化行动请求和 Godot 镜像/交付基础；
- 面向未来玩法扩展的 Patch、Rule IR 和受信任 capability 边界。

当前项目还不是：

- 完整动作 RPG；
- 完整动态经济或商业组织模拟；
- 一键把任意剧本自动编译成完成游戏的创作者产品；
- 世界模型直接生成并维护完整可交互世界的运行时；
- 已完成的创作者 CLI、资产市场和链上分账平台。

最准确的定位是：

> 一个以角色智能体、世界权威和可回放玩法结算为核心，当前优先服务 RPG/剧本杀的可扩展游戏运行时底座。
