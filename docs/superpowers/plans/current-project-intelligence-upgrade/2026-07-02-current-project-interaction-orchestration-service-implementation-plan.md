# 当前项目 Interaction Orchestration Service 实施计划

> 对应规格：
> [2026-07-02-current-project-interaction-orchestration-service-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-interaction-orchestration-service-design.md)

**状态：** `implemented-and-verified`

**实际核对：** `interaction-orchestration-service` harness profile 已通过，报告为 `.harness/verification/interaction-orchestration-service-report.json`，覆盖 semantic-only、physical-only、mixed、constraint denied、active perception 和 authority confirmation paths。

**目标：** 将轻量 `orchestrate_interaction(...)` 扩展为 backend service/route/policy executor，连接 ESM semantic channel 与未来 physical channel。

**依赖/口径：**

- 本计划先于 `ESM Physical Channel World Actuation` 执行。
- 本计划完成的是 interaction orchestration service/route/policy 和 physical adapter seam。
- physical path 在本计划中可以是 adapter stub，不能据此宣称真实连续物理作用完成。

## 阶段 A：Service 与 Plan

目标文件建议：

- `backend/app/services/interaction_orchestration_service.py`
- `backend/tests/test_interaction_orchestration_runtime_service.py`

任务：

- [x] 定义 `InteractionOrchestrationPlan`
- [x] 定义 channel request/result envelopes
- [x] 实现 semantic-only 策略
- [x] 实现 physical-only 策略
- [x] 实现 semantic goal + physical effect mixed 策略
- [x] 实现 denied-by-constraint 策略
- [x] 实现 requires-active-perception 策略
- [x] 实现 requires-authority-confirmation 策略
- [x] 保留现有 helper 兼容层

验收：

- push/pull/carry 类意图可进入 physical 或 mixed plan
- 感知不足时返回 requires-active-perception，不直接假定成功或失败
- authority 未确认时返回 requires-authority-confirmation，不绕过 ESM/authority

## 阶段 B：Route 接入

目标文件建议：

- `backend/app/main.py`

任务：

- [x] 新增 structured interaction route 或 service entry
- [x] validate actor/target refs
- [x] 禁止 raw input 直入业务层
- [x] 返回 unified result family

## 阶段 C：Channel 调用与 Merge

任务：

- [x] semantic path 调用现有 ESM
- [x] physical path 调用 physical channel adapter stub
- [x] mixed path 合并 semantic goal 与 physical effect
- [x] requires-active-perception path 生成 active perception request/degrade reason
- [x] requires-authority-confirmation path 生成 authority confirmation request/degrade reason
- [x] constraint failure 结构化回传

验收：

- channel merge 不产生两套 world result
- requires-active-perception 不调用 physical effect application
- requires-authority-confirmation 不绕过 semantic authority

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

验证报告必须证明：

- semantic-only 仍走现有 ESM
- physical/mixed path 只通过 structured intent 进入
- denied-by-constraint 可结构化返回
- requires-active-perception 可结构化返回并可接入 PQF/provider 链路
- requires-authority-confirmation 可结构化返回并保持 authority 边界
- orchestration 不替角色做最终心智选择

## 完成定义

完成后应能说：

> 交互编排层已从 contract helper 成为 backend service，能接收结构化 intent、选择通道、调用语义/物理作用服务并返回统一结果，同时不替代角色心智或 ESM authority。

如果 physical path 仍是 stub，只能说：

> 交互编排层已提供 physical channel seam；真实物理作用由后续 ESM Physical Channel World Actuation 计划验证。
