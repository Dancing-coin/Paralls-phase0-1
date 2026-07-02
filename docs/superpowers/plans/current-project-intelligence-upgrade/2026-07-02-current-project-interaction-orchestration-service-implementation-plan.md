# 当前项目 Interaction Orchestration Service 实施计划

> 对应规格：
> [2026-07-02-current-project-interaction-orchestration-service-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-interaction-orchestration-service-design.md)

**状态：** `planned`

**目标：** 将轻量 `orchestrate_interaction(...)` 扩展为 backend service/route/policy executor，连接 ESM semantic channel 与未来 physical channel。

## 阶段 A：Service 与 Plan

目标文件建议：

- `backend/app/services/interaction_orchestration_service.py`
- `backend/tests/test_interaction_orchestration_runtime_service.py`

任务：

- [ ] 定义 `InteractionOrchestrationPlan`
- [ ] 定义 channel request/result envelopes
- [ ] 实现 semantic/physical/mixed/denied 策略
- [ ] 保留现有 helper 兼容层

## 阶段 B：Route 接入

目标文件建议：

- `backend/app/main.py`

任务：

- [ ] 新增 structured interaction route 或 service entry
- [ ] validate actor/target refs
- [ ] 禁止 raw input 直入业务层
- [ ] 返回 unified result family

## 阶段 C：Channel 调用与 Merge

任务：

- [ ] semantic path 调用现有 ESM
- [ ] physical path 调用 physical channel adapter stub
- [ ] mixed path 合并 semantic goal 与 physical effect
- [ ] constraint failure 结构化回传

## 阶段 D：Verification

目标文件建议：

- `scripts/verification/verify_interaction_orchestration_runtime_service.py`
- `.harness/profiles/interaction-orchestration-service.json`

验证命令：

```bash
python -m pytest -q backend/tests/test_interaction_orchestration_runtime_service.py
python scripts/verification/verify_interaction_orchestration_runtime_service.py
python scripts/verification/harness.py --profile interaction-orchestration-service
```

## 完成定义

完成后应能说：

> 交互编排层已从 contract helper 成为 backend service，能接收结构化 intent、选择通道、调用语义/物理作用服务并返回统一结果，同时不替代角色心智或 ESM authority。
