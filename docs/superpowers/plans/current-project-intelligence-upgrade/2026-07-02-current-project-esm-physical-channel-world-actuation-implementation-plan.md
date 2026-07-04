# 当前项目 ESM Physical Channel World Actuation 实施计划

> 对应规格：
> [2026-07-02-current-project-esm-physical-channel-world-actuation-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-esm-physical-channel-world-actuation-design.md)

**状态：** `planned`

**目标：** 在现有 ESM 语义结算和统一结果协议之上，补齐 physical interaction channel、连续接触、推拉/携带和 mixed result 回流。

**前置依赖：**

- `Interaction Orchestration Service` 已提供 structured intent route、channel plan、physical adapter seam 和 unified result merge 入口。
- 若该依赖未完成，本计划只能实现 isolated physical channel contract/probe，不能宣称 mixed runtime path 完成。

## 阶段 A：Physical Channel 协议

目标文件建议：

- `backend/app/services/physical_interaction_channel.py`
- `backend/tests/test_esm_physical_channel_runtime.py`

任务：

- [ ] 定义 physical request/result
- [ ] 定义 contact/push/pull/carry/blocking effect kinds
- [ ] 定义 constraint gate
- [ ] 映射统一 result family
- [ ] 定义 object/environment/body state observation refs
- [ ] 定义 L1/ESM 回流观察字段

## 阶段 B：Godot Adapter

目标文件建议：

- `scripts/interaction/PhysicalInteractionProbe.gd`
- `scripts/interaction/PhysicalInteractionAdapter.gd`

任务：

- [ ] 采样 contact/body/object refs
- [ ] 输出结构化 physical effect refs
- [ ] 输出 object/environment/body state observation refs
- [ ] 禁止 raw physics stream 直入业务层

## 阶段 C：Mixed Merge

任务：

- [ ] 接入 Interaction Orchestration Service
- [ ] semantic approves goal/constraint
- [ ] physical reports effect
- [ ] merge 为统一 result
- [ ] failed constraint prevents effect application

验收：

- mixed path 必须通过 Interaction Orchestration Service 入口触发
- constraint failure 必须阻止 physical effect application
- physical effect 必须回流统一 result family，不能产生第二套 world result
- object/environment/body state 可被 L1/ESM 回流观察
- semantic-only 行为不因 physical channel 接入而退化

## 阶段 D：Verification

目标文件建议：

- `scripts/verification/verify_esm_physical_channel_runtime.py`
- `.harness/profiles/esm-physical-channel-world-actuation.json`

验证命令：

```bash
python -m pytest -q backend/tests/test_esm_physical_channel_runtime.py
python scripts/verification/verify_esm_physical_channel_runtime.py
python scripts/verification/harness.py --profile esm-physical-channel-world-actuation
```

验证报告必须证明：

- semantic-only behavior remains unchanged
- physical effect has structured result
- mixed result has one unified output family
- constraint failure prevents physical application
- object/environment/body state observation refs are visible to L1/ESM feedback

## 完成定义

完成后应能说：

> ESM 双通道已具备 physical world-actuation path，连续物理作用通过受控 adapter 和统一结果协议回流，不绕过 semantic authority。

如果 Interaction Orchestration Service 尚未完成，只能说：

> physical channel contract/probe 已完成局部验证；mixed runtime path 仍等待 interaction orchestration service 接入。
