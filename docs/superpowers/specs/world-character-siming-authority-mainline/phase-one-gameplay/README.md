# Phase One Gameplay Specification Tree

Status: `implemented-and-verified for the bounded Phase One scope; matching evidence is tracked in the plan README`

Date: `2026-08-07`

## Purpose

本目录把 `docs/8月分析/第一阶段推进/` 转换为正式的第一阶段 spec tree。它只描述
第一阶段如何复用现有 `Character Gameplay Foundation` 和 world/ESM authority 路径，
不建立新的 runtime、event store、authority bus 或全局 scheduler。

核心跨玩法 contract 归父目录：

- [Gameplay Foundation Shared Contract Closure (P1A)](../character-gameplay-foundation/2026-08-07-gameplay-foundation-shared-contract-closure-design.md)

本目录负责这些有明确验收边界的第一阶段规格：

1. [P1B 通用 contract 的 Harness/replay/permission 证明](2026-08-07-p1b-contract-verification-and-evidence-design.md)，对应 [plan](../../../plans/world-character-siming-authority-mainline/phase-one-gameplay/2026-08-07-p1b-contract-verification-and-evidence-implementation-plan.md)；
2. [P1C V0 霜冻农田 contract sample](2026-08-07-p1c-frost-farm-contract-sample-design.md)，对应 [plan](../../../plans/world-character-siming-authority-mainline/phase-one-gameplay/2026-08-07-p1c-frost-farm-contract-sample-implementation-plan.md)；
3. [P1D Econ-1 单经营者面包店参考游戏](2026-08-07-p1d-econ1-bakery-reference-game-design.md)，对应 [plan](../../../plans/world-character-siming-authority-mainline/phase-one-gameplay/2026-08-07-p1d-econ1-bakery-reference-game-implementation-plan.md)；
4. Econ-1 的建造生产、生存、经济周期、组织与政府子域；
5. [P1E 第二个异质样板的泛化门禁](2026-08-07-p1e-generalization-gate-design.md)，对应 [plan](../../../plans/world-character-siming-authority-mainline/phase-one-gameplay/2026-08-07-p1e-generalization-gate-implementation-plan.md)。

对应实施计划见 [Phase One Gameplay Implementation Plan Tree](../../../plans/world-character-siming-authority-mainline/phase-one-gameplay/README.md)。

## Scope Boundary

### Included

- 只扩展现有 world runtime/ESM、Gameplay authorities、projection、Patch 和 event spine；
- 明确跨域 schema、owner、command、event、projection、revision、migration、rollback；
- 每个规格都有 focused tests、Harness profile 和 replay evidence 要求；
- Econ-1 第一版使用一个经营者、聚合顾客需求、固定供应商 quote 和参数化竞争 profile；
- 允许已有正式 `CharacterRecord` 通过 typed intent 参加受控多智能体测试。

### Excluded or deferred

- Population Simulation Authority；
- 员工、顾客、供应商、竞争对手的 NPC canonical state materialization；
- dynamic market、order book、auction、跨区贸易和宏观经济；
- 完整 Creator Control Plane UI/CLI/MCP、发布服务、资产市场和分润；
- 任意 Python/GDScript 内容包执行；
- 第二个异质样板的具体内容，除非 P1E matching plan 明确选择。

## Dependency Graph

```text
Character Gameplay Foundation P1A
  -> P1B contract/replay/permission proof
  -> P1C frost-farm contract sample
  -> P1D Econ-1 reference-game contract
       -> construction/production
       -> survival profile
       -> economy/period settlement
       -> organization/government
  -> P1D focused implementation and replay evidence
  -> P1E second heterogeneous sample/generalization gate
```

每个子 spec 只消费上游 contract，不得反向修改 P1A 的 owner 或定义平行 settlement path。

## Status Rules

- `awaiting-user-review`: 设计草案，可审阅，不授权 plan 或实现；
- `approved`: 用户批准边界后，才允许创建 matching plan；
- `implemented-and-verified`: 只有 focused tests、对应 Harness、前置 profiles 和新鲜
  evidence 全部通过后才能使用。

本轮用户已批准本目录的规格进入 plan 阶段。正式 plan 已放在同名的
`docs/superpowers/plans/world-character-siming-authority-mainline/phase-one-gameplay/`
子目录中，不能把八月分析文件直接当作 plan。

截至 2026-08-09，P1A/P1B/P1C、四个 Econ-1 domain child plan、P1D 和 P1E 均有 fresh
focused/Harness 证据。P1D 额外包含 profile-backed employee、failure/recovery、checkpoint-tail
和 Godot committed mirror；P1E 额外包含 scoped projection 与 stale/duplicate/permission/
custody/term zero-write matrix。该状态只覆盖本目录的 bounded Phase One scope，不解除
Population Simulation、dynamic market 或 Creator Control Plane 的 deferred 标记。

## Reading Order

1. [P1B Contract Verification And Evidence](2026-08-07-p1b-contract-verification-and-evidence-design.md)
2. [P1C Frost Farm Contract Sample](2026-08-07-p1c-frost-farm-contract-sample-design.md)
3. [P1D Econ-1 Bakery Reference Game](2026-08-07-p1d-econ1-bakery-reference-game-design.md)
4. [Econ-1 domain specifications](econ1/README.md)
5. [P1E Generalization Gate](2026-08-07-p1e-generalization-gate-design.md)
