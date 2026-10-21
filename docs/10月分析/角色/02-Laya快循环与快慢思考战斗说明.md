# 02 Laya 快循环与快慢思考战斗说明

本说明对应 [02 设计](02-Laya快循环与快慢思考战斗设计.md)。

## 运行时接入

- L1 提供角色实际能看到、听到、感到和通过调查得到的信息。
- Laya 读取精简的战斗状态，不读取 authority 的完整 Boss 状态。
- L4 将 typed intent 映射到现有动作和执行契约。
- CharacterActor 负责连续动画、位移、打断和表现。
- authority 负责命中、伤害、硬直、死亡、掉落和阶段事实。

## 推荐 typed intent

```text
observe, probe, approach, reposition, dodge, block,
attack, punish, heal, disengage, retreat,
protect_ally, focus_target, hold_position, abort_maneuver
```

## 需要实现的调度接口

```text
FastDecisionContext
FastDecisionResult
CombatMemoryEntry
EscalationTrigger
PlanRevision
ExecutionContract
```

其中 `PlanRevision` 用于判断慢思考返回的计划是否仍然适用；旧版本计划不得覆盖新战斗状态。

## 验证重点

1. 一次连续战斗能否由 Laya 完成，而不是只验证单步选择。
2. 失败后是否改变战术，而不是重复同一动作。
3. 慢思考等待期间是否仍然能够自保。
4. 阶段变化后旧 intent 是否正确过期。
5. 模型不可用时是否进入显式 continuity floor。


## 本批规格与计划回写（2026-10-10）

本说明与角色02设计共同作为 Laya 快慢链来源。A→B→C 顺序、一次完整“动作＋目标”候选、包络内候选实验和新隔离场景属于本批收敛；原说明中的调度接口名不视为已存在 wire schema，需先映射现有 coordinator/gateway 并取得真实 provider 证据。

接入顺序固定为现有 admission/coordinator 的持久 L3 stage → driver/provider slot → gateway 专用 `/v1/systemone` adapter → `accept_l3` → `freeze_l3`/L4；连续感知/自身事件若需持久化，扩展同一 admission owner，不创建第二入站。显式取消、过期、旧 worker、重试和停机恢复分别取证；角色 stage receipt 不等于领域 authority receipt。详见 [规格01 §3.1.2](../规格/01-角色智能体心智运行时重构总规格.md#312-laya-与现有-gatewayadmission-的接入合同)。
