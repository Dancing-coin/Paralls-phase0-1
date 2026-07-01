# Phase 1 L1 Full-Scope Checklist

这份文档把主项目 `Phase 1` 对 `System L1` 的实现要求，和当前 `paralls-phase-0-demo` 仓库里的实际实现做成一张可执行清单。

## Status

- Date: `2026-06-10`
- Scope: `d:\Users\User\Documents\paralls-phase-0-demo`
- Status rule:
  - `已做（已验证）`: 已落地且已通过当前回归面
  - `已做（部分/已验证）`: 已有真实实现，但仍未到 full-volume 终态
  - `已写待执行`: spec/plan 已写，但主体实现还没落地
  - `已做（已验证未提交）`: 代码已改且已验证，但当前工作树尚未提交

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

按当前仓库的 repo-local `Phase 1 / System L1` 收口目标来看，
当前已经完成了：

- `System L1` 主干
- 八类事实上抛器的显式仓库内落位
- `System L2` 感知入口所需的当前仓库桥接面
- 一条已验证闭环的 `ESM` authority settlement / runtime-facing writeback 链

但如果按主项目 full-volume 终态来看，当前仍没有完成：

- 八类事实上抛器的全量 runtime 深度
- `ESM` 调试回放 / 工作台面的更完整对齐
- 多感官到候选感知编译的明确全域策略

## 清单表

| Phase 1 L1 全域项 | 当前状态 | 优先级 | 说明 |
| --- | --- | --- | --- |
| 统一 raw fact contract | 已做（已验证） | P0 | 已有 shared contract、`effect_kind`、`subject_key`、`ttl_ms` |
| 统一跨边界事实上抛出口 | 已做（已验证） | P0 | `FactEnvelopeBuilder.gd` + `RawFactEmitter.gd` 已成立 |
| 视觉事实上抛器最小链路 | 已做（部分/已验证） | P0 | `CharacterVisualFactEmitter`、`EnvironmentVisualFactEmitter` 已有且可验证 |
| 社交距离 / 空间行为上抛器最小链路 | 已做（部分/已验证） | P0 | `SpatialAccessFactEmitter` 已有且可验证 |
| reconnect / zone reseed / privacy reseed / environment cycle runtime proof | 已做（已验证） | P0 | `verify_l1_runtime_edges.py` 已验证 |
| `ttl_ms` 首条真实能力 | 已做（部分/已验证） | P1 | 目前只落在 `nearby_actor_refs` 上 |
| 候选感知事件对象层 | 已做（最小/已验证） | P1 | `CandidatePerceptEvent` 已存在 |
| `Per-Character` 过滤器边界 | 已做（最小/已验证） | P1 | `PerCharacterPerceptFilter` 已存在，但规则很薄 |
| 角色私有感知事件对象 | 已做（已验证） | P1 | `CharacterPerceivedEvent` 与 `SelfBodyPerceivedEvent` 已存在 |
| 角色私有感知事件真实消费路径 | 已做（已验证） | P1 | 外部世界经 `CandidatePerceptEvent -> CharacterPerceivedEvent`，自身身体经 `BodyStateResult -> SelfBodyPerceivedEvent` |
| `ObjectVisualFactEmitter` | 已做（部分/已验证） | P1 | 已有显式 emitter 与对象状态上抛；仍未到完整视觉域终态 |
| `SpatialRelationVisualFactEmitter` | 已做（最小/已验证） | P1 | 已有显式 emitter 落位，但 runtime 深度仍有限 |
| `EvidenceProjectionEmitter` | 已做（部分/已验证） | P1 | 已有显式 emitter 落位，并已接入成功交互后的真实 runtime fact path；仍是 bounded slice |
| 听觉事实上抛器 | 已做（已验证） | P1 | `speaker_active`、`auditory_reachability_changed`、`ambient_noise_changed` 与显式 `L1-only` policy 已验证 |
| 客户端交互系统的完整“事件上抛器”规范化 | 已做（部分/已验证） | P1 | `focus_target_change`、`interact`、`action_request` 已进入真实链路，`move_intent` 也已有 runtime snapshot proof |
| `ESM` 动作结算与约束接口 | 已做（部分/已验证） | P1 | `ActionResolutionResult`、`ConstraintStateResult`、`BodyStateResult` 已真实接线，repo-local 已显式支持 `light_level_drop` / `light_level_restore` / `thermal_level_rise` / `smoke_density_rise` / `noise_level_rise` 五类环境请求，并对 unsupported 变体与未支持变体家族显式给出边界 |
| `ESM` 状态机与材料模板 | 已做（部分/已验证） | P1 | 已有 `state_machine_transition`、object/environment machine templates skeleton、材料模板 skeleton |
| `ESM` 区域环境场与传播规则 | 已做（部分/已验证） | P1 | 已有 `EnvironmentFieldState`、`light/noise/thermal/smoke/visibility` coarse field、环境场更新、邻区传播的 coarse slice |
| `ESM` 与事件总线正式契约 | 已做（部分/已验证） | P1 | `world_result` 已补 canonical envelope 字段；仍未到主项目 full contract 终态 |
| `ESM` 调试回放与工作台能力 | 已做（已验证未提交） | P2 | 当前已有 audit / replay-friendly result identity、minimal workbench snapshot、最近一条 environment request / resolution / result / transition 观察面，以及 bounded recent-history window；仍不是完整工作台 |
| 触觉事实上抛器 | 已做（已验证） | P2 | 已从成功交互结果触发最小 tactile fact |
| 热感事实上抛器 | 已做（已验证） | P2 | 已从 `env_lamp -> alerted` 结果触发最小 thermal fact |
| 嗅觉事实上抛器 | 已做（已验证） | P2 | 已从同一 bounded 环境代理触发最小 olfactory fact |
| 生理状态事实上抛器 | 已做（已验证） | P2 | 已从 jump / grounded runtime state 触发最小 physiology fact |
| 角色状态事实上抛器 | 已做（已验证） | P2 | 已从 `CharacterReplica` role-state 变更触发最小 role-state fact |
| 空间音频系统正式化（Steam Audio 侧） | 未做（完整版） | P2 | 当前是最小听觉事实上抛 slice，不是完整空间音频子系统 |
| 八类事实上抛器最小字段集统一表 | 已做（隐式） | P2 | 已散落在 emitter / test / audit 中，但尚未沉淀成单一对照表 |
| 多感官原始事实到候选感知编译的完整入口 | 未做（仅最小 slice） | P2 | 现在只有视觉 + spatial access 最小接入；听觉 upward policy 已明确冻结为 `L1-only` |

## 已登记的当前实现状态

### 已完成并已验证

- 视觉事实系统的五个一级/派生 emitter 均已在仓库内显式落位
- `EvidenceProjectionEmitter` 已进入成功交互后的真实 runtime 证明面，并被 `phase1_slice` audit 显式要求
- 听觉最小域已具备显式 taxonomy、authority route、Godot emitter 与 `L1-only` candidate policy proof
- `ESM` 已形成真实的 `action_request -> resolution/constraint -> world_result/state_machine_transition` 链
- `move_intent` 已不再只是 `ack + local_motion`，而是已有 `character_runtime_state_snapshot` runtime proof
- `system-l1-client-interaction` 子计划的 repo-local 最小规范化目标已闭合；当前清单里该域仍记为“部分”仅因为主项目 full-volume interaction family 尚未完整实现
- `system-l1-visual-fact-system` 子计划的 repo-local 目标也已闭合；当前清单里视觉域若仍记为“部分”，含义仅是主项目 full-volume visual domain 尚未完整实现
- `system-l1-esm-full-domain` 子计划的 repo-local 目标也已闭合；当前清单里 `ESM` 若仍记为“部分”，含义仅是主项目 full production workbench / broader settlement matrix 尚未完整实现
- `ESM` 已对 repo-local unsupported `environment_request` 变体给出显式拒绝策略，而不是默认接受
- `ESMService` 已显式暴露 repo-local capability manifest，声明当前支持/不支持边界
- `ESMService` 已显式暴露 environment-request variant family policy
- `ESM` 已显式支持第二个环境请求变体 `thermal_level_rise`
- `ESM` 已显式支持第三个环境请求变体 `smoke_density_rise`
- `ESM` 已显式支持第四个环境请求变体 `noise_level_rise`
- `ESM` 已显式支持第五个环境请求变体 `light_level_restore`
- `ESM` 已对 runtime 使用中的 `light_source` / `heat_source` 暴露显式环境机模板
- `ESM` 已对 runtime 使用中的 `smoke_source` 暴露显式环境机模板
- `ESM` 已对 runtime 使用中的 `noise_source` 暴露显式环境机模板
- `ESMService` 已暴露 minimal repo-local workbench snapshot，可查询模板/material/environment-field 当前面
- `ESMService` workbench snapshot 已可查询最近一条 environment request / resolution
- `ESMService` workbench snapshot 已可查询最近一条 environment result / state transition
- `ESMService` workbench snapshot 已可查询最近几条 environment request / resolution / result / transition
- `EnvironmentFieldState` 已具备 `field_id`、`updated_at`、显式 `thermal_level` 和 coarse field propagation

### 已做（已验证未提交）

- `ESM` full-domain 的更深对齐与更完整 debug/workbench 面
  - 当前工作树已补 success-path `ObjectStateResult` / `BodyStateResult` / `EnvironmentStateResult` 对原始 `ActionRequest` 的 shared request lineage
  - 当前工作树已补 repo-local coarse `thermal_level` field contract 及其邻区传播
  - 当前 phase0 verification audit 已显式证明 `esm_request_lineage` 与 `esm_thermal_field`
  - 当前工作树已补 repo-local `ESM` capability manifest，显式声明支持/不支持边界
  - 当前工作树已补 environment-request variant family policy
  - 当前工作树已补第二个支持环境请求变体 `thermal_level_rise`
  - 当前工作树已补第三个支持环境请求变体 `smoke_density_rise`
  - 当前工作树已补第四个支持环境请求变体 `noise_level_rise`
  - 当前工作树已补第五个支持环境请求变体 `light_level_restore`
  - 当前工作树已补 runtime 使用中的 `light_source` / `heat_source` 环境机模板与 catalog
  - 当前工作树已补 runtime 使用中的 `smoke_source` 环境机模板与 catalog
  - 当前工作树已补 runtime 使用中的 `noise_source` 环境机模板与 catalog
  - 当前工作树已补 minimal repo-local workbench snapshot surface
  - 当前工作树已补 latest environment request / latest resolution workbench evidence surface
  - 当前工作树已补 latest environment result / latest transition workbench evidence surface
  - 当前工作树已补 bounded recent-history workbench evidence surface
  - focused tests、backend 全套、`verify_phase1_slice.py`、`verify_phase0.py`、`verify_l1_runtime_edges.py` 已串行通过

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
