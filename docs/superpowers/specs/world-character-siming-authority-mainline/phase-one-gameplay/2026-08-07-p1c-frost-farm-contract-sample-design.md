# P1C Frost Farm Contract Sample Design

Status: `approved; matching plan authorized by user on 2026-08-07`

Date: `2026-08-07`

## Purpose

用一个小而完整的环境 effect 样板验证 P1A/P1B contract。霜冻农田是第一阶段推荐的
V0，因为它同时使用 Entity/Environment、material/property、effect/resistance、状态
变化、可选 Survival projection、因果 evidence、权限投影和 replay。

本文是 contract sample，不是完整农业系统，不建立天气 runtime、生态模拟、市场价格
发现或第二套 world loop。

## Scope

### Included

- 一个辖区、一块农田、一个作物状态；
- 一个天气/环境 fact 和一个 frost effect；
- 一个 crop resistance profile；
- 一个 crop state transition 和产量 projection；
- 一个可选角色 cold/fatigue projection，用于证明 state-group disabled semantics；
- 成功、抗性减损、目标不存在、权限不足、revision 冲突、重复命令和 replay。

### Excluded

- 完整天气、季节、生态、资源再生和灾害系统；
- 动态市场、农业供应链、NPC 农民和人口模拟；
- 用农田字段扩展通用 Entity schema；
- 让环境 authority 直接修改角色、经济或库存事实。

## Canonical Records

```text
FarmPlot
  plot_ref, jurisdiction_ref, material_refs, ownership_ref, crop_ref, status, revision

CropState
  crop_ref, plot_ref, growth_stage, health_band, expected_yield, revision

EnvironmentFact
  fact_ref, region_ref, kind, intensity, started_tick, duration, source_revision

FrostEffectInput
  effect_ref, source_fact_ref, target_refs, severity, semantic_revision

ResistanceProfile
  target_ref, effect_ref, resistance_kind, modifier, revision
```

农田/作物由 V0 domain authority 拥有；环境事实继续由现有 world/ESM 路径提供；
semantic/effect/resistance 由 P1A contract 约束；角色资源/状态由其既有 authority 写入。

## Settlement Flow

```text
environment fact
-> Entity/Environment reference resolution
-> SemanticSnapshot + ResistanceProfile
-> effect evaluation and RuleTrace
-> optional SettlementPlan
-> Farm/Crop authority event mapping
-> GameplayEventStore.append_batch
-> causal event/projection/Godot mirror
```

如果角色 Survival profile 已启用，角色后果只作为独立 domain proposal 进入自己的 owner；
不得在农田 batch 中直接写角色 hunger、health 或 fatigue。

## Required Events And Outcomes

- `environment.frost_observed`；
- `farm.crop_frost_evaluated`；
- `farm.crop_state_changed`；
- optional `survival.effect_projected` or equivalent typed proposal;
- structured failure without events for missing target, stale revision, permission denial or
  incompatible semantic revision。

事件 payload 必须包含 command/correlation/causation、pinned revisions、evidence refs、
privacy scope 和 source digest。任何农田专用字段只能出现在 V0 package schema。

## Acceptance

- frost effect 命中和 resistance 通过可重复；
- resistance 减损与完全拒绝有可解释 trace；
- target missing、permission、stale revision、duplicate 都是零部分提交；
- Survival disabled 时没有需求衰减、消费或身体惩罚；
- full replay 与 checkpoint+tail replay 一致；
- actor、creator-debug、public、Godot view 按 scope 过滤；
- 同一 P1A contract 可被后续 Econ-1 引用而不修改核心 schema。
