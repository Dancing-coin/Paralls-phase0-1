# 当前项目 Siming Global Situation Layer 实施计划

> 对应规格：
> [2026-07-02-current-project-siming-global-situation-layer-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-siming-global-situation-layer-design.md)

**状态：** `implemented-and-verified`

**实际核对：** `siming-global-situation-layer` harness profile 已通过，报告为 `.harness/verification/siming-global-situation-layer-report.json`，覆盖 public L1/world/authority/evidence/VLA/multi-actor patch 输入、`siming_mm:*` 隔离和 advisory 不改写 world truth。

**目标：** 在现有 `SimingRuntime` 和 read model 之上补齐司命全局 patch、fusion、situation lifecycle 和 intervention evidence 接线。

## 阶段 A：Situation 模型

目标文件建议：

- `backend/app/services/siming_global_situation.py`
- `backend/tests/test_siming_global_situation_runtime.py`

任务：

- [x] 定义 `SimingGlobalSituationSnapshot`
- [x] 定义 visibility imbalance / fairness pressure / evidence chain fields
- [x] 定义 freshness/conflict/advisory metadata
- [x] 支持 open/update/stale/resolve

## 阶段 B：Global Patch Assembly

任务：

- [x] 从 L1 projected facts 组装 multi-actor patch
- [x] 合入 authority events/world results
- [x] 合入 environment/evidence events
- [x] 合入 VLA advisory global findings，但保留 advisory/conflict/source refs
- [x] 禁止读取 character private cache

验收：

- 多角色公共 patch 可生成
- context id 必须为 `siming_mm:*`
- VLA advisory global findings 可增强态势判断，但不能覆盖 authority/world truth

## 阶段 C：Fusion 与 Candidate 接线

目标文件建议：

- `backend/app/services/siming_event_pipeline.py`
- `backend/app/services/siming_runtime.py`

任务：

- [x] 将 global situation 输入 `FairnessStateSnapshot`
- [x] intervention candidate 携带 situation evidence refs
- [x] minimal catalyst path 可引用 situation pressure
- [x] workbench explanation 展示 source/conflict/freshness
- [x] VLA/L1/authority 冲突时保留 conflict refs，并产生 review/active perception 线索而不是直接改写态势真相

## 阶段 D：Trace/Harness

目标文件建议：

- `scripts/verification/verify_siming_global_situation_runtime.py`
- `.harness/profiles/siming-global-situation-layer.json`

验证命令：

```bash
python -m pytest -q backend/tests/test_siming_global_situation_runtime.py
python scripts/verification/verify_siming_global_situation_runtime.py
python scripts/verification/harness.py --profile siming-global-situation-layer
```

## 完成定义

完成后应能说：

> 司命具备独立 global situation layer，能从公共世界事实、authority 事件和 VLA advisory global findings 形成多角色态势，并把态势证据用于公平判断和干预候选，而不污染角色私有上下文、不覆盖 world truth。
