# Phase 1 L1 Full-Scope Checklist

这份文档把主项目 `Phase 1` 对 `System L1` 的实现要求，和当前 `paralls-phase-0-demo` 仓库里的实际实现做成一张可执行清单。

目的不是重讲架构，而是直接回答：

- `System L1` 在 `Phase 1` 里到底要做哪些东西
- 当前仓库已经做了哪些
- 哪些还没做
- 先做什么最值

## 使用口径

本清单只讨论：

- **System L1**
  - 也就是主项目整体架构里的“确定性空间层 / 运行时执行域”

不讨论：

- **Character Agent L1-L4**
  - 角色智能体内部四层心智链

## 总体判断

当前仓库已经足够作为 `System L1` 的继续实现基础。

它已经有：

- 统一事实上抛出口
- backend authority 接入
- reconnect / reseed / cycle / TTL 的最小运行时保障

但如果按主项目 `Phase 1` 的完整 `System L1` 要求来看，
当前只完成了：

- `System L1` 主干
- 少量事实上抛器
- 少量 `System L2` 感知入口桥接

还没有完成：

- 八类事实上抛器
- 视觉事实系统全簇
- `ESM` 全簇的 `Phase 1` 实现

## 清单表

| Phase 1 L1 全域项 | 当前状态 | 优先级 | 说明 |
| --- | --- | --- | --- |
| 统一 raw fact contract | 已做 | P0 | 已有 shared contract、`effect_kind`、`subject_key`、`ttl_ms` |
| 统一跨边界事实上抛出口 | 已做 | P0 | `FactEnvelopeBuilder.gd` + `RawFactEmitter.gd` 已成立 |
| 视觉事实上抛器最小链路 | 已做（部分） | P0 | `CharacterVisualFactEmitter`、`EnvironmentVisualFactEmitter` 已有 |
| 社交距离 / 空间行为上抛器最小链路 | 已做（部分） | P0 | `SpatialAccessFactEmitter` 已有 |
| reconnect / zone reseed / privacy reseed / environment cycle runtime proof | 已做 | P0 | `verify_l1_runtime_edges.py` 已验证 |
| `ttl_ms` 首条真实能力 | 已做（部分） | P1 | 目前只落在 `nearby_actor_refs` 上 |
| 候选感知事件对象层 | 已做（最小） | P1 | `CandidatePerceptEvent` 已存在 |
| `Per-Character` 过滤器边界 | 已做（最小） | P1 | `PerCharacterPerceptFilter` 已存在，但规则很薄 |
| 角色私有感知事件对象 | 已做（最小） | P1 | `CharacterPerceivedEvent` 已存在 |
| 角色私有感知事件真实消费路径 | 已做（最小） | P1 | 已有一条最小 consumer path，但还不是默认角色入口 |
| `ObjectVisualFactEmitter` | 未做 | P1 | 视觉事实系统四个一级源域之一 |
| `SpatialRelationVisualFactEmitter` | 未做 | P1 | 视觉事实系统四个一级源域之一 |
| `EvidenceProjectionEmitter` | 未做 | P1 | 视觉派生层，主项目明确存在 |
| 听觉事实上抛器 | 未做 | P1 | 主项目 `L1` 八类之一，会话/偷听闭环关键依赖 |
| 客户端交互系统的完整“事件上抛器”规范化 | 半做 | P1 | 当前有事实出口，但还没按主项目子系统化梳理全量交互事实 |
| `ESM` 动作结算与约束接口 | 未做（Phase 1 完整版） | P1 | 当前 repo 只有最小交互级结算 slice |
| `ESM` 状态机与材料模板 | 未做（完整版） | P1 | 当前只有最小状态变化路径 |
| `ESM` 区域环境场与传播规则 | 未做 | P1 | 主项目明确属于 `L1/ESM` 边界能力 |
| `ESM` 与事件总线正式契约 | 半做 | P1 | 现在能跑，但不是主项目文档簇要求的完整契约实现 |
| `ESM` 调试回放与工作台能力 | 未做（完整版） | P2 | 当前有 verification harness，但不是完整 ESM 工作台 |
| 触觉事实上抛器 | 未做 | P2 | `L1` 八类之一 |
| 热感事实上抛器 | 未做 | P2 | `L1` 八类之一 |
| 嗅觉事实上抛器 | 未做 | P2 | `L1` 八类之一 |
| 生理状态事实上抛器 | 未做 | P2 | `L1` 八类之一 |
| 角色状态事实上抛器 | 未做 | P2 | `L1` 八类之一 |
| 空间音频系统正式化（Steam Audio 侧） | 未做（完整版） | P2 | 主项目把它视为 `L1` 子系统，不只是未来扩展 |
| 八类事实上抛器最小字段集统一表 | 未做（显式） | P2 | 现在散在实现里，没有一份仓库内可执行对照表 |
| 多感官原始事实到候选感知编译的完整入口 | 未做 | P2 | 现在只有视觉 + spatial access 最小接入 |

## 该怎么排顺序

### 第一批必须继续做

这些是最像 `Phase 1 L1` 主干的部分，应该继续在当前仓库里长：

1. `ObjectVisualFactEmitter`
2. `SpatialRelationVisualFactEmitter`
3. `EvidenceProjectionEmitter`
4. 听觉事实上抛器
5. `ESM` 动作结算与约束接口
6. `ESM` 区域环境场与传播规则

理由：

- 这些东西最直接决定当前仓库能不能从“L1 主干”长成“Phase 1 的 L1 域”
- 而不是只做成一个视觉 + spatial access demo

### 第二批再做

1. 触觉 / 热感 / 嗅觉 / 生理 / 角色状态这五类事实上抛器
2. 空间音频系统正式化
3. `ESM` 工作台和更完整的回放能力

理由：

- 它们是主项目 `Phase 1` 目标的一部分
- 但不一定是最先决定最小闭环成立与否的部分

## 哪些不要继续堆在当前仓库里

当前仓库继续做 `System L1` 没问题，但不建议在这里继续无限扩展这些内容：

- 完整角色智能体 `L1-L4`
- 完整 `System L2` 全域
- 司命完整 Phase 1 实现
- 大规模 `L6` 正式化基础设施

原因：

- 当前仓库最适合的是把 `System L1` 做硬
- 再往上会开始和 `Phase 0` 兼容层、demo 语义、历史 glue code 相互干扰

## 一句话总结

如果现在要继续推进 `Phase 1`：

> 当前仓库最应该做的是把 `System L1` 从“最小事实骨架”继续扩展成“视觉事实系统 + ESM + 八类事实上抛器”的真正 `Phase 1 L1` 域；而不是过早把主要精力继续堆到完整角色智能体或更高层系统上。
